#!/usr/bin/env python3
"""Best-effort LoopLoad Chromium recorder; --dry-run inspects selectors only."""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'demo'
VIEWPORT = {'width': 1440, 'height': 900}

# Test IDs are preferred; accessible names and visible text are fallbacks.
TARGETS = {
    'map': (None, ('region', r'(freight|india|trip).*map|map'), None),
    'baseline': (None, ('button', r'^baseline$'), r'^baseline$'),
    'ai': ('ai-plan-button', ('button', r'^AI Plan$'), r'^AI Plan$'),
    'truck': ('truck-row-T01', ('button', r'\bT01\b'), r'\bT01\b'),
    'drawer': ('truck-drawer', ('dialog', r'T01|truck'), None),
    'close': ('truck-drawer-close', ('button', r'close( truck)?( drawer)?|dismiss'), r'^close$'),
    'cancel': ('cancel-load-button', ('button', r'Simulate:\s*cancel a load'), r'Simulate:\s*cancel a load'),
    'toast': ('replan-toast', ('status', r'replan|cancel|plan'), r'replanned|replanning|load cancelled'),
    'forecast_nav': ('nav-forecast', ('link', r'forecast'), r'^forecast$'),
    'forecast': ('hot-lanes-list', ('heading', r'forecast|demand'), r'forecast|hot lanes'),
    'driver': ('driver-phone', ('heading', r'T01|driver'), r'\bT01\b'),
    'kannada': ('lang-kn', ('button', r'ಕನ್ನಡ|Kannada|^KN$'), r'ಕನ್ನಡ|Kannada|^KN$'),
    'language': (None, ('combobox', r'language|ಭಾಷೆ'), None),
}


def log(message):
    print(message, flush=True)


def safe(label, action):
    """A missing UI control, failed navigation, or screenshot never aborts the tour."""
    try:
        return action()
    except Exception as error:
        log(f'WARN {label}: {error}')
        return None


def candidates(page, key):
    test_id, role, text = TARGETS[key]
    if test_id:
        yield f'data-testid={test_id}', page.get_by_test_id(test_id)
    if role:
        yield f'role={role[0]} name=/{role[1]}/', page.get_by_role(role[0], name=re.compile(role[1], re.I))
    if text:
        yield f'text=/{text}/', page.get_by_text(re.compile(text, re.I))
    if key == 'map':
        yield 'map canvas (readiness unconfirmed)', page.locator('.maplibregl-canvas, .mapboxgl-canvas, canvas')
    if key == 'drawer':
        yield 'dialog', page.get_by_role('dialog')
    if key == 'language':
        yield 'select[name=language]', page.locator('select[name="language"], select[aria-label*="anguage"]')


def locate(page, key, timeout=4000, attached=False):
    """Poll all fallbacks within one deadline, preferring test IDs each pass."""
    deadline = time.monotonic() + timeout / 1000
    while True:
        for description, locator in candidates(page, key):
            try:
                for index in range(min(locator.count(), 10)):
                    element = locator.nth(index)
                    if attached or element.is_visible():
                        log(f'FOUND {key}: {description}' + (' [attached]' if attached else ''))
                        return element
            except Exception:
                continue
        if time.monotonic() >= deadline:
            log(f'MISSING {key}: ' + (f'data-testid={TARGETS[key][0]}' if TARGETS[key][0] else 'accessible/text/canvas fallbacks') + '; continuing')
            return None
        page.wait_for_timeout(150)


def click(page, key):
    target = locate(page, key)
    if target is None:
        return False
    target.click(timeout=5000)
    return True


def navigate(page, url):
    response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
    if response is not None and response.status >= 400:
        log(f'WARN navigation returned HTTP {response.status}: {url}')


def screenshot(page, name):
    safe(f'screenshot {name}', lambda: page.screenshot(path=str(OUTPUT / f'{name}.png'), timeout=10000))


def pause(page, seconds):
    safe(f'pause {seconds}s', lambda: page.wait_for_timeout(seconds * 1000))


def reset_demo(api_url):
    def run():
        result = subprocess.run(['bash', str(ROOT / 'scripts/demo_reset.sh'), api_url],
                                cwd=ROOT, capture_output=True, text=True, timeout=300)
        if result.stdout.strip():
            log(result.stdout.strip())
        if result.stderr.strip():
            log(result.stderr.strip())
        if result.returncode:
            log(f'WARN reset exited {result.returncode}; recording continues with the current scenario')
    safe('seed-42 reset', run)


def dry_run(page, base_url):
    """Navigate only: no reset, clicks, dropdown selection, video, or screenshots."""
    for route, keys in [('/', ('map','baseline','ai','truck','drawer','close','cancel','toast','forecast_nav')),
                        ('/forecast', ('forecast',)),
                        ('/driver/T01', ('driver','kannada','language'))]:
        log(f'\nDRY RUN {base_url + route}')
        safe(f'open {route}', lambda route=route: navigate(page, base_url + route))
        for key in keys:
            safe(f'check {key}', lambda key=key: locate(page, key, timeout=1500))
    log('Dry run complete. Drawer controls may be absent because dry run never opens the drawer.')
    log('replan-toast may be absent because dry run never triggers cancellation.')
    log('Kannada uses lang-kn, with an accessible native language select as fallback.')


def wait_for_map(page):
    canvas = page.locator('.maplibregl-canvas, .mapboxgl-canvas, canvas').first
    canvas.wait_for(state='visible', timeout=30000)
    # No frontend map-ready test ID is provided: wait for rendering and quiet requests.
    page.wait_for_function("""() => [...document.querySelectorAll('canvas')]
        .some(canvas => canvas.width > 0 && canvas.height > 0)""", timeout=10000)
    safe('wait for map requests to settle', lambda: page.wait_for_load_state('networkidle', timeout=10000))
    log('FOUND visible map canvas; rendered map readiness is best effort')


def tour(page, base_url):
    safe('open home', lambda: navigate(page, base_url + '/'))
    safe('wait for map', lambda: wait_for_map(page))
    safe('select Baseline', lambda: click(page, 'baseline'))
    pause(page, 3)
    screenshot(page, '01_baseline')

    safe('click AI Plan', lambda: click(page, 'ai'))
    pause(page, 4)
    screenshot(page, '02_ai_plan')

    safe('open truck T01', lambda: click(page, 'truck'))
    safe('wait for truck drawer', lambda: locate(page, 'drawer'))
    pause(page, 4)
    screenshot(page, '03_truck_T01')
    closed = safe('close truck drawer', lambda: click(page, 'close'))
    if not closed:
        safe('close drawer with Escape', lambda: page.keyboard.press('Escape'))
    safe('wait for drawer close', lambda: page.get_by_test_id('truck-drawer').wait_for(state='hidden', timeout=5000))
    screenshot(page, '04_drawer_closed')

    cancelled = safe('simulate cancel a load (optional)', lambda: click(page, 'cancel'))
    if cancelled:
        safe('wait for replan toast', lambda: locate(page, 'toast'))
    pause(page, 4)
    screenshot(page, '05_cancel_load')

    opened = safe('click forecast navigation', lambda: click(page, 'forecast_nav'))
    if not opened:
        safe('open forecast directly', lambda: navigate(page, base_url + '/forecast'))
    safe('wait for forecast', lambda: locate(page, 'forecast'))
    pause(page, 4)
    screenshot(page, '06_forecast')

    safe('open driver T01', lambda: navigate(page, base_url + '/driver/T01'))
    safe('wait for driver', lambda: locate(page, 'driver'))
    screenshot(page, '07_driver_T01')
    def kannada():
        button = locate(page, 'kannada', timeout=2000)
        if button is not None:
            button.click(timeout=5000)
            return
        select = locate(page, 'language', timeout=2000)
        if select is not None:
            select.select_option(value='kn', timeout=5000)
    safe('switch language to Kannada', kannada)
    pause(page, 3)
    screenshot(page, '08_driver_kannada')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='inspect selectors; do not reset or record')
    parser.add_argument('--url', default='http://localhost:5173', help='frontend origin')
    parser.add_argument('--api-url', default='http://localhost:8000', help='API origin for demo reset')
    parser.add_argument('--headed', action='store_true', help='show Chromium while inspecting or recording')
    args = parser.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log('ERROR Install Playwright and Chromium first; see scripts/RECORD.md')
        return 1
    try:
        # Reset is completed before any browser opens. Dry run never invokes reset.
        if not args.dry_run:
            OUTPUT.mkdir(parents=True, exist_ok=True)
            reset_demo(args.api_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = None
            video = None
            try:
                options = dict(viewport=VIEWPORT)
                if not args.dry_run:
                    options.update(record_video_dir=str(OUTPUT), record_video_size=VIEWPORT)
                context = browser.new_context(**options)
                page = context.new_page()
                page.set_default_timeout(5000)
                if not args.dry_run:
                    video = page.video
                if args.dry_run:
                    dry_run(page, args.url.rstrip('/'))
                else:
                    tour(page, args.url.rstrip('/'))
            finally:
                # Playwright flushes video on context.close, before save_as.
                if context is not None:
                    safe('close browser context', context.close)
                if video is not None:
                    destination = OUTPUT / 'loopload_demo.webm'
                    def save_video():
                        video.save_as(str(destination))
                        log(f'Saved {destination}')
                        video.delete()  # Remove the auto-named copy only after saving.
                    safe('save video (auto-named source retained on failure)', save_video)
                safe('close Chromium', browser.close)
        return 0
    except KeyboardInterrupt:
        log('Interrupted; any completed captures remain in demo/.')
        return 130
    except Exception as error:
        log(f'ERROR Recorder could not start or complete: {error}. See scripts/RECORD.md')
        return 1


if __name__ == '__main__':
    sys.exit(main())
