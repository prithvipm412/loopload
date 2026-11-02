#!/usr/bin/env python3
"""Export pitch numbers and four 1600x1000 transparent PNG charts.

Run only once the API is ready:
  backend/.venv/bin/python -m pip install matplotlib
  backend/.venv/bin/python scripts/pitch_numbers.py
  backend/.venv/bin/python scripts/pitch_numbers.py --fixture

--fixture permits JSON fallback from frontend/src/mocks when API requests fail.
Fixture outputs are explicitly labelled; no numbers are invented if data is absent.
No backend requirements files are changed. Default outputs are demo/pitch_numbers.md
and demo/charts/{empty_km,profit,co2,loads_served}.png.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
METRICS = ('total_km', 'empty_km', 'empty_pct', 'loads_served', 'loads_total', 'profit_inr', 'co2_kg')
BASELINE_COLOR = '#454545'
AI_COLOR = '#9AB397'


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def validate_plan(plan, mode):
    if not isinstance(plan, dict) or plan.get('mode') != mode or not isinstance(plan.get('trucks'), list):
        raise ValueError(f'Expected a contract {mode} Plan JSON')
    values = {key: finite(plan['metrics'][key], key) for key in METRICS}
    values['solve_time_s'] = finite(plan['solve_time_s'], 'solve_time_s')
    if any(values[key] < 0 for key in METRICS if key != 'profit_inr'):
        raise ValueError(f'{mode} has negative distance, emissions, percentage, or load count')
    if not 0 <= values['empty_pct'] <= 100 or values['empty_km'] > values['total_km']:
        raise ValueError(f'{mode} has inconsistent empty distance or percentage')
    if values['loads_served'] > values['loads_total'] or values['solve_time_s'] < 0:
        raise ValueError(f'{mode} has invalid served loads or solve time')
    if any(not values[key].is_integer() for key in ('loads_served', 'loads_total')):
        raise ValueError('Load counts must be whole numbers')
    return values


def api_json(origin, path, timeout, body=None):
    request = Request(origin.rstrip('/') + path,
                      data=json.dumps(body).encode() if body is not None else None,
                      method='POST' if body is not None else 'GET',
                      headers={'Accept': 'application/json', 'Content-Type': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f'{path} returned HTTP {response.status}')
        return json.load(response)


def from_api(origin, timeout):
    comparison = api_json(origin, '/api/compare', timeout)
    plans = {mode: api_json(origin, '/api/plan', timeout, {'mode': mode}) for mode in ('baseline', 'ai')}
    for mode, plan in plans.items():
        values = validate_plan(plan, mode)
        for key in METRICS:
            if not math.isclose(values[key], finite(comparison[mode][key], key), abs_tol=.2, rel_tol=1e-6):
                raise ValueError(f'/api/compare and {mode} Plan disagree on {key}; retry with stable caches')
    return plans, f'Live API: {origin}'


def plan_objects(value):
    if isinstance(value, dict):
        if 'metrics' in value and 'trucks' in value:
            yield value
        else:
            for child in value.values():
                yield from plan_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from plan_objects(child)


def from_fixtures(directory):
    plans = {}; files = {}
    for path in sorted(Path(directory).rglob('*.json')):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        for plan in plan_objects(value):
            mode = plan.get('mode')
            if mode in ('baseline', 'ai'):
                validate_plan(plan, mode)
                plans[mode] = plan; files[mode] = path.name
    if not all(mode in plans for mode in ('baseline', 'ai')):
        raise ValueError(f'Baseline and AI Plan JSON fixtures are missing from {directory}')
    return plans, f"FIXTURE DATA — synthetic, not live results: {files['baseline']} / {files['ai']}"


def headline_values(plans, mileage):
    mileage = finite(mileage, 'mileage_kmpl')
    if mileage <= 0:
        raise ValueError('mileage_kmpl must be positive')
    values = {}
    for mode in ('baseline', 'ai'):
        row = validate_plan(plans[mode], mode)
        row['diesel_litres'] = row['total_km'] / mileage
        row['co2_t'] = row['co2_kg'] / 1000
        values[mode] = row
    if values['baseline']['loads_total'] != values['ai']['loads_total']:
        raise ValueError('Baseline and AI must describe the same number of scenario loads')
    return values


def markdown(values, source, mileage):
    baseline, ai = values['baseline'], values['ai']
    rows = [
        ('Empty km', 'empty_km', ',.1f'), ('Empty %', 'empty_pct', '.1f'),
        ('Loads served', 'loads_served', ',.0f'), ('Profit (₹)', 'profit_inr', ',.0f'),
        ('Diesel (litres)', 'diesel_litres', ',.1f'), ('CO₂ (tonnes)', 'co2_t', ',.3f'),
        ('Solve time (s)', 'solve_time_s', '.2f'),
    ]
    table = '\n'.join(f"| {label} | {format(baseline[key], spec)} | {format(ai[key], spec)} |" for label, key, spec in rows)
    def change(delta, unit, reduction=True, spec=',.1f'):
        if delta == 0:
            return f'unchanged ({format(0, spec)} {unit})'
        positive_word, negative_word = ('lower', 'higher') if reduction else ('higher', 'lower')
        return f"{format(abs(delta), spec)} {unit} {positive_word if delta > 0 else negative_word}"
    empty_delta = baseline['empty_km'] - ai['empty_km']
    co2_delta = baseline['co2_t'] - ai['co2_t']
    litres_delta = baseline['diesel_litres'] - ai['diesel_litres']
    profit_delta = ai['profit_inr'] - baseline['profit_inr']
    claims = [
        f"AI empty running is {change(empty_delta, 'km')}, moving from {baseline['empty_pct']:.1f}% to {ai['empty_pct']:.1f}% empty km.",
        f"AI serves {ai['loads_served']:.0f} loads versus {baseline['loads_served']:.0f}, with profit {change(profit_delta, '₹', reduction=False, spec=',.0f')}.",
        f"AI operational CO₂ is {change(co2_delta, 'tonnes', spec=',.3f')} and estimated diesel use is {change(litres_delta, 'litres')}.",
    ]
    safe_source = source.replace('\n', ' ').replace('|', '\\|')
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    return f'''# LoopLoad pitch numbers

Source: {safe_source}  
Generated: {timestamp}

| Headline | Baseline | AI |
| --- | ---: | ---: |
{table}

Pitch claims (for this demo scenario):

''' + '\n'.join(f'- {claim}' for claim in claims) + f'''

Diesel is estimated from total distance at {mileage:g} km/L, matching the contract assumption. CO₂ tonnes = plan CO₂ kg ÷ 1,000. Profit is net profit in INR. These are scenario results, not measured real-world savings; fixture outputs are synthetic. Solve times are reported per plan.
'''


def charts(values, directory, fixture=False):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter, MaxNLocator
    except ImportError as error:
        raise RuntimeError('Install chart tools: backend/.venv/bin/python -m pip install matplotlib') from error
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 18, 'text.color': '#111111',
                         'axes.labelcolor': '#111111', 'xtick.color': '#111111', 'ytick.color': '#707070'})
    definitions = [
        ('empty_km', 'empty_km', 'Empty kilometres', 'km', ',.0f'),
        ('profit', 'profit_inr', 'Fleet profit', '₹', ',.0f'),
        ('co2', 'co2_t', 'Operational CO₂', 'tonnes', ',.3f'),
        ('loads_served', 'loads_served', 'Loads served', 'loads', ',.0f'),
    ]
    for name, key, title, unit, spec in definitions:
        fig, ax = plt.subplots(figsize=(16, 10), dpi=100)
        try:
            fig.patch.set_alpha(0); ax.patch.set_alpha(0)
            fig.subplots_adjust(left=.15, right=.94, bottom=.17, top=.80)
            heights = [values[mode][key] for mode in ('baseline', 'ai')]
            bars = ax.bar(['Baseline', 'AI'], heights, width=.48,
                          color=[BASELINE_COLOR, AI_COLOR], edgecolor='none', zorder=3)
            ax.set_title(title, loc='left', fontsize=32, fontweight='bold', pad=50)
            ax.set_ylabel(unit, labelpad=20, fontsize=18)
            ax.spines[['top', 'right', 'left']].set_visible(False)
            ax.spines['bottom'].set_color('#999999')
            ax.tick_params(axis='both', length=0, pad=14)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=(key == 'loads_served')))
            ax.yaxis.set_major_formatter(FuncFormatter(
                lambda number, position: format(number, ',.1f' if key == 'co2_t' else ',.0f')))
            ax.grid(axis='y', color='#B8B8B8', linewidth=.8, alpha=.55, zorder=0)
            ax.axhline(0, color='#777777', linewidth=1)
            spread = max(abs(v) for v in heights) or 1
            low = min(0, min(heights))
            high = max(0, max(heights))
            ax.set_ylim(low - (.20*spread if low < 0 else 0), high + .24*spread)
            for bar, height in zip(bars, heights):
                ax.annotate(format(height, spec), xy=(bar.get_x()+bar.get_width()/2, height),
                            xytext=(0, 14 if height >= 0 else -14), textcoords='offset points',
                            ha='center', va='bottom' if height >= 0 else 'top', fontsize=25, fontweight='bold')
            caption = 'LoopLoad · synthetic fixture data' if fixture else 'LoopLoad · demo scenario comparison'
            fig.text(.15, .055, caption, color='#707070', fontsize=15)
            # No tight bounding box: retain exact 1600×1000 output dimensions.
            fig.savefig(directory / f'{name}.png', dpi=100, transparent=True, facecolor='none')
        finally:
            plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--fixture', action='store_true', help='allow frontend JSON fixtures if API requests fail')
    parser.add_argument('--fixture-dir', type=Path, default=ROOT / 'frontend/src/mocks')
    parser.add_argument('--mileage-kmpl', type=float, default=4)
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError('--timeout must be positive and finite')
        fixture = False
        try:
            plans, source = from_api(args.base_url, args.timeout)
        except (OSError, ValueError, KeyError, TypeError) as error:
            if not args.fixture:
                raise RuntimeError(f'API unavailable or inconsistent: {error}. Use --fixture to allow mock JSON fallback.') from error
            print(f'API unavailable or inconsistent ({error}); using fixture fallback.', file=sys.stderr)
            plans, source = from_fixtures(args.fixture_dir)
            fixture = True
        values = headline_values(plans, args.mileage_kmpl)
        text = markdown(values, source, args.mileage_kmpl)
        target = ROOT / 'demo/charts'
        target.mkdir(parents=True, exist_ok=True)
        # Build all charts before publishing the numbers or replacing prior charts.
        with tempfile.TemporaryDirectory(prefix='.pitch-', dir=target) as staging:
            staged = Path(staging)
            charts(values, staged, fixture)
            for path in staged.glob('*.png'):
                path.replace(target / path.name)
            note = staged / 'pitch_numbers.md'
            note.write_text(text, encoding='utf-8')
            note.replace(ROOT / 'demo/pitch_numbers.md')
        print(f'Wrote {ROOT / "demo/pitch_numbers.md"} and four charts to {target}')
        print(source)
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f'Pitch export failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
