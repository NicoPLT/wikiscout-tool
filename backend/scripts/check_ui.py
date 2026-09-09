"""Local UI regression check with mocked APIs; requires a running frontend."""
import argparse
import asyncio
import json
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright, expect


async def main(base_url):
    row = dict(id=1, full_name="Test Player", current_team="Test Club", photo_url=None,
        league="Test League", position="CF", age=None, market_value_eur=1000000,
        market_value_change_eur=None, market_value_change_pct=None, goals_last5=0,
        assists_last5=0, goals_season=0, assists_season=0, appearances_season=0,
        minutes_season=0, season_label=None, rating_avg=None, is_xg_covered=False,
        xg_season=None, xa_season=None, watchlist_notes="Private note", watchlist_tags=None,
        tag=None, last_synced_at=None, sync_status="pending", sync_attempted_at=None,
        sync_state={}, date_of_birth=None, nationality=None, transfermarkt_id="1",
        api_football_id=None, sofascore_id=None, fotmob_id=None, stats_updated_at=None,
        market_value_updated_at=None, rating_updated_at=None, recent_matches=[],market_value_history=[])
    rows = [{**row, "id":i+1,"full_name":f"Test Player {i+1}"} for i in range(200)]
    profile_requests = 0
    profile_failed = True
    old_search_started = asyncio.Event()
    async def route_api(route):
        nonlocal profile_requests
        parsed = urlparse(route.request.url)
        path = parsed.path
        status = 200
        data = []
        if path.endswith('/auth/me'):
            data = {"email":"test@example.test"}
        elif path == '/api/watchlist':
            data = rows
        elif path.endswith('/unseen-count'):
            data = {"count":0}
        elif path.endswith('/export'):
            data = {"version":1,"tables":{"players":rows}}
        elif path == '/api/players/999':
            profile_requests += 1
            status = 500 if profile_failed else 200
            data = {"detail":"simulated outage"} if status == 500 else row
        elif path == '/api/players/search':
            query = parse_qs(parsed.query).get('q',[''])[0]
            if query == 'slow':
                old_search_started.set()
                await asyncio.sleep(0.8)
            data = [{**row,"source":"local","in_watchlist":True,"full_name":f"Result {query}"}]
        await route.fulfill(status=status, content_type='application/json', body=json.dumps(data),
            headers={'Access-Control-Allow-Origin':'*'})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width":390,"height":844},accept_downloads=True)
        await context.add_init_script("localStorage.setItem('wikiscout_token','local-ui-test')")
        await context.route('**/api/**',route_api)
        page = await context.new_page()
        errors = []
        requests = []
        page.on('pageerror',lambda error: errors.append(str(error)))
        page.on('request',lambda req: requests.append(req.url))
        await page.goto(base_url)
        await expect(page.get_by_text('Test Player 1',exact=True)).to_be_visible()
        assert not any('DesktopPlayersGrid' in url or 'ag-grid' in url for url in requests), requests
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        async with page.expect_download() as download_info:
            await page.get_by_role('button',name='Esporta dati').click()
        download = await download_info.value
        assert download.suggested_filename.startswith('wikiscout-')
        search = page.get_by_placeholder('Cerca giocatore...')
        await search.fill('slow')
        await asyncio.wait_for(old_search_started.wait(),timeout=10)
        await search.fill('fast')
        await expect(page.get_by_text('Result fast',exact=True)).to_be_visible()
        await asyncio.sleep(1)
        await expect(page.get_by_text('Result slow',exact=True)).to_have_count(0)
        await search.fill('')
        await page.set_viewport_size({"width":1440,"height":900})
        await expect(page.locator('.ag-root')).to_be_visible()
        assert any('DesktopPlayersGrid' in url for url in requests)
        await page.goto(base_url+'/players/999')
        await expect(page.get_by_role('button',name='Riprova',exact=True)).to_be_visible()
        profile_failed = False
        await page.get_by_role('button',name='Riprova',exact=True).click()
        await expect(page.get_by_role('heading',name='Test Player',exact=True)).to_be_visible()
        await expect(page.get_by_text('Stato delle fonti')).to_be_visible()
        assert not errors, errors
        print('PASS: mobile 200 players, no AG Grid download, export, search cancellation, desktop grid, profile error/retry, no uncaught browser errors')
        await browser.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:5175')
    args=parser.parse_args()
    asyncio.run(main(args.base_url.rstrip('/')))
