"""Report arithmetic and data-source checks, using explicitly synthetic test inputs."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('carbon_report',Path(__file__).resolve().parents[1]/'scripts/carbon_report.py')
report=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(report)


def fixtures():
    scenario=dict(week_start='2026-11-09T00:00:00+05:30',cities=[],
                  owners=[dict(id='O1',name='Murugan & Sons'),dict(id='O2',name='<Transport>')],
                  trucks=[dict(id='T01',owner_id='O1'),dict(id='T02',owner_id='O2')])
    def plan(mode,empty):
        trucks=[]
        for tid in ('T01','T02'):
            legs=[dict(kind='empty',distance_km=empty,co2_kg=empty*.67),
                  dict(kind='loaded',distance_km=3000,co2_kg=2010)]
            trucks.append(dict(truck_id=tid,legs=legs))
        return dict(mode=mode,trucks=trucks,
                    metrics=dict(total_km=2*(empty+3000),empty_km=2*empty,co2_kg=2*(empty+3000)*.67))
    return plan('baseline',2000),plan('ai',500),scenario


class ReportTests(unittest.TestCase):
    def test_arithmetic_and_owner_reconciliation(self):
        result=report.calculate(*fixtures())
        self.assertAlmostEqual(result['saved_co2'],2010)
        self.assertAlmostEqual(result['saved_litres'],750)
        self.assertAlmostEqual(result['removed_empty'],3000)
        self.assertEqual(len(result['owners']),2)
        self.assertAlmostEqual(sum(r['saved_co2'] for r in result['owners']),result['saved_co2'])

    def test_increases_are_not_clipped(self):
        baseline,ai,scenario=fixtures()
        result=report.calculate(ai,baseline,scenario)
        self.assertAlmostEqual(result['saved_co2'],-2010)
        self.assertAlmostEqual(result['saved_litres'],-750)

    def test_invalid_mileage_and_inconsistent_totals(self):
        baseline,ai,scenario=fixtures()
        with self.assertRaises(ValueError):report.calculate(baseline,ai,scenario,0)
        ai['metrics']['co2_kg']+=100
        with self.assertRaisesRegex(ValueError,'reconcile'):report.calculate(baseline,ai,scenario)

    def test_unknown_owner_rejected(self):
        baseline,ai,scenario=fixtures();ai['trucks'][0]['truck_id']='T99'
        with self.assertRaisesRegex(ValueError,'attribute'):report.calculate(baseline,ai,scenario)

    def test_html_escaping_and_print_styles(self):
        html=report.render(report.calculate(*fixtures()),'Synthetic test <source>')
        self.assertIn('Murugan &amp; Sons',html)
        self.assertIn('&lt;Transport&gt;',html)
        self.assertIn('&lt;source&gt;',html)
        self.assertIn('@page { size: A4',html)
        self.assertIn('#FAF7F2',html)
        self.assertIn('2,010.0',html)

    def test_api_calls_compare_and_both_plans(self):
        baseline,ai,scenario=fixtures()
        comparison=dict(baseline=baseline['metrics'],ai=ai['metrics'])
        with patch.object(report,'request',side_effect=[comparison,baseline,ai,scenario]) as call:
            values=report.from_api('http://example.test',180)
        self.assertEqual(call.call_args_list[0].args[1],'/api/compare')
        self.assertEqual(call.call_args_list[1].args[1],'/api/plan')
        self.assertEqual(call.call_args_list[2].args[-1],dict(mode='ai'))
        self.assertEqual(values[0],baseline)

    def test_fixture_and_unavailable_paths(self):
        baseline,ai,scenario=fixtures()
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'plans.json').write_text(json.dumps(dict(baseline=baseline,ai=ai,scenario=scenario)))
            result=report.from_fixtures(folder,folder/'unused.json')
            self.assertEqual(result[0],baseline)
            self.assertIn('not live results',result[3])
            args=['--offline','--fixtures',str(folder),'--output',str(folder/'report.html')]
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(report.main(args),0)
                (folder/'plans.json').unlink()
                self.assertEqual(report.main(args),1)
            self.assertIn('No savings claimed',(folder/'report.html').read_text())


if __name__=='__main__':unittest.main()
