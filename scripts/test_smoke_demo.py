"""Contract fixtures verify the deployment tools without requiring integrated engines."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

SPEC = importlib.util.spec_from_file_location('smoke_demo', Path(__file__).with_name('smoke_demo.py'))
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)
ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')

    def handle_request(self, method):
        parsed = urlsplit(self.path); path = parsed.path
        self.server.calls.append((method, path))
        body = json.loads(self.rfile.read(int(self.headers['Content-Length']))) if method == 'POST' else {}
        code = 200
        scenario = self.server.scenario
        if path == self.server.fail_path:
            code, value = 500, {'detail': 'planted failure'}
        elif path == '/api/health':
            value = {'ok': True}
        elif path == '/api/scenario/regenerate':
            self.server.reset_bodies.append(body)
            if not self.server.stale_cache:
                self.server.plans.clear()
            value = scenario
        elif path == '/api/scenario':
            value = scenario
        elif path == '/api/plan' or path == '/api/replan':
            mode = body.get('mode', 'ai')
            value = copy.deepcopy(self.server.plan)
            value.update(mode=mode, plan_id=f'{mode}-{len(self.server.calls)}')
            self.server.plans[value['plan_id']] = value
        elif path.startswith('/api/plan/'):
            value = self.server.plans.get(path.rsplit('/', 1)[-1])
            if value is None:
                code, value = 404, {'detail': 'Plan not found'}
        elif path == '/api/compare':
            value = dict(baseline=self.server.metrics, ai=self.server.metrics,
                         delta={k: 0 for k in ('empty_km','empty_pct','profit_inr','co2_kg','loads_served')})
        elif path == '/api/forecast':
            lane = parse_qs(parsed.query).get('lane')
            value = [v for v in self.server.forecasts if not lane or v['lane'] == lane[0]]
        elif path == '/api/hot-lanes':
            value = self.server.forecasts[:8]
        elif path == '/api/trucks/T01/week':
            value = dict(truck=scenario['trucks'][0], plan=self.server.plan['trucks'][0])
        elif path == '/api/owners/O1/summary':
            value = dict(owner=scenario['owners'][0], metrics=self.server.metrics, trucks=self.server.plan['trucks'])
        elif path.startswith('/api/compliance/'):
            value = dict(ok=True, issues=[])
        else:
            code, value = 404, {'detail': 'Unknown route'}
        encoded = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class ToolTests(unittest.TestCase):
    def setUp(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server = server
        server.calls = []; server.plans = {}; server.reset_bodies = []
        server.fail_path = None; server.stale_cache = False
        server.scenario = json.loads((ROOT/'backend/data/scenario.json').read_text())
        server.forecasts = json.loads((ROOT/'backend/forecast/forecast.json').read_text())
        server.metrics = {key: 0 for key in smoke.METRICS}
        server.metrics.update(total_km=100, loaded_km=100, loads_served=1, loads_total=140, trucks_used=1)
        leg = dict(truck_id='T01', seq=0, kind='loaded', load_id='L001',
                   depart_h=2, arrive_h=60, distance_km=100, **{'from':'TPR','to':'DEL'},
                   path=[[77.34,11.11],[77.21,28.61]], compliance=dict(ok=True,issues=[]))
        server.plan = dict(plan_id='ai-fixture',mode='ai',created_at='2026-11-02T00:00:00+05:30',
                           solve_time_s=.1, unassigned_loads=[],metrics=server.metrics,
                           trucks=[dict(truck_id='T01',legs=[leg],totals=server.metrics)])
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def run_smoke(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = smoke.main(['--base-url', self.origin, '--timeout', '2'])
        return code, output.getvalue()

    def test_all_endpoints_and_summary(self):
        code, output = self.run_smoke()
        self.assertEqual(code, 0, output)
        self.assertIn('19 checks passed; 0 failed.', output)
        self.assertIn("T01's AI week", output)
        self.assertIn('profit INR', output)
        self.assertEqual({path for method,path in self.server.calls}, {
            '/api/health','/api/scenario','/api/scenario/regenerate','/api/plan',
            *[path for method,path in self.server.calls if path.startswith('/api/plan/')],
            '/api/compare','/api/replan','/api/trucks/T01/week','/api/owners/O1/summary',
            '/api/forecast','/api/hot-lanes','/api/compliance/L001'})
        self.assertEqual(sum(path == '/api/replan' for _,path in self.server.calls),3)

    def test_http_failure_keeps_checking_and_fails(self):
        self.server.fail_path = '/api/compare'
        code, output = self.run_smoke()
        self.assertEqual(code,1)
        self.assertIn('FAIL GET /api/compare', output)
        self.assertIn(('GET','/api/hot-lanes'),self.server.calls)

    def test_invalid_payload_fails(self):
        self.server.metrics['empty_pct'] = 101
        code, output = self.run_smoke()
        self.assertEqual(code,1)
        self.assertIn('empty percentage outside', output)


if __name__ == '__main__':
    unittest.main()
