"""Startup regression checks against a local frontend with isolated mock APIs.

Run after `npm run build` and `npm run preview -- --port 5175`.
No real account, backend or database is used.
"""
import argparse
import asyncio
import json
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect


EMAIL = "startup-test@example.com"
TOKEN = "startup-test-token"
ROW = dict(
    id=1, full_name="Startup Player", current_team="Test Club", photo_url=None,
    league=None, position="CF", age=21, market_value_eur=None,
    market_value_change_eur=None, market_value_change_pct=None,
    goals_last5=0, assists_last5=0, goals_season=0, assists_season=0,
    appearances_season=0, minutes_season=0, season_label=None,
    rating_avg=None, is_xg_covered=False, xg_season=None, xa_season=None,
    watchlist_notes=None, watchlist_tags=None, tag=None,
    last_synced_at=None, sync_status="pending", sync_attempted_at=None,
)


class Scenario:
    def __init__(self):
        self.me_status = 200
        self.login_status = 200
        self.tags_status = 200
        self.watchlist_status = 200
        self.legacy_login = False
        self.me_gate = None
        self.tags_gate = None
        self.paths = []

    async def route(self, route):
        path = urlparse(route.request.url).path
        self.paths.append(path)
        status, data = 200, []
        if path == "/api/auth/me":
            if self.me_gate:
                await self.me_gate.wait()
            status, data = self.me_status, {"email": EMAIL}
        elif path == "/api/auth/login":
            status, data = self.login_status, {"access_token": TOKEN}
            if not self.legacy_login:
                data["email"] = EMAIL
        elif path == "/api/watchlist":
            status, data = self.watchlist_status, [ROW]
        elif path == "/api/tags":
            if self.tags_gate:
                await self.tags_gate.wait()
            status = self.tags_status
        elif path.endswith("/unseen-count"):
            data = {"count": 0}
        elif path == "/api/health":
            data = {"status": "ok"}
        if status != 200:
            data = {"detail": "Simulated failure"}
        await route.fulfill(status=status, content_type="application/json", body=json.dumps(data))


async def new_page(browser, scenario, saved=True):
    context = await browser.new_context(viewport={"width": 390, "height": 844})
    if saved:
        await context.add_init_script(f"localStorage.setItem('wikiscout_token', {json.dumps(TOKEN)})")
    await context.route("**/api/**", scenario.route)
    await context.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page = await context.new_page()
    return context, page


async def submit(page):
    await page.get_by_label("Email", exact=True).fill(EMAIL)
    await page.get_by_label("Password", exact=True).fill("test-password")
    await page.get_by_role("button", name="Accedi", exact=True).click()


async def assert_dashboard(page):
    await expect(page.get_by_text("Startup Player", exact=True)).to_be_visible()


async def main(base_url):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        # A temporary auth outage preserves the token and can be retried.
        scenario = Scenario()
        scenario.me_status = 503
        context, page = await new_page(browser, scenario)
        await page.goto(base_url)
        await expect(page.get_by_role("alert")).to_contain_text("temporaneamente")
        assert await page.evaluate("localStorage.getItem('wikiscout_token')") == TOKEN
        assert "/api/watchlist" not in scenario.paths
        scenario.me_status = 200
        await page.get_by_role("button", name="Riprova", exact=True).click()
        await assert_dashboard(page)
        await context.close()
        print("PASS: auth 503 preserves session, protects data, retry opens dashboard")

        # Native XHR timeouts are shortened only in this test browser.
        scenario = Scenario()
        scenario.me_gate = asyncio.Event()
        context, page = await new_page(browser, scenario)
        await context.add_init_script("""
          const descriptor = Object.getOwnPropertyDescriptor(XMLHttpRequest.prototype, 'timeout');
          Object.defineProperty(XMLHttpRequest.prototype, 'timeout', {
            ...descriptor, set(value) { descriptor.set.call(this, value === 120000 ? 250 : value); }
          });
        """)
        await page.goto(base_url)
        await expect(page.get_by_role("alert")).to_contain_text("troppo tempo")
        assert await page.evaluate("localStorage.getItem('wikiscout_token')") == TOKEN
        scenario.me_gate.set()
        await page.get_by_role("button", name="Riprova", exact=True).click()
        await assert_dashboard(page)
        await context.close()
        print("PASS: auth timeout preserves session and recovers on retry")

        # An actually expired session still requires login.
        scenario = Scenario()
        scenario.me_status = 401
        context, page = await new_page(browser, scenario)
        await page.goto(base_url)
        await expect(page.get_by_role("button", name="Accedi", exact=True)).to_be_visible()
        assert await page.evaluate("localStorage.getItem('wikiscout_token')") is None
        assert "/api/watchlist" not in scenario.paths
        await context.close()
        print("PASS: rejected session clears token and redirects to login")

        # New login does not wait for a redundant /me; old backends still work.
        for legacy in (False, True):
            scenario = Scenario()
            scenario.legacy_login = legacy
            context, page = await new_page(browser, scenario, saved=False)
            await page.goto(base_url + "/login")
            await submit(page)
            await assert_dashboard(page)
            assert scenario.paths.count("/api/auth/me") == int(legacy)
            assert "/api/health" in scenario.paths
            await context.close()
        print("PASS: single-request login, health warmup, compatibility with old backend")

        scenario = Scenario()
        scenario.login_status = 503
        context, page = await new_page(browser, scenario, saved=False)
        await page.goto(base_url + "/login")
        await submit(page)
        await expect(page.get_by_role("alert")).to_contain_text("temporaneamente")
        await expect(page.get_by_role("alert")).not_to_contain_text("password")
        scenario.login_status = 401
        await submit(page)
        await expect(page.get_by_role("alert")).to_contain_text("password")
        scenario.login_status = 200
        await submit(page)
        await assert_dashboard(page)
        await context.close()
        print("PASS: login distinguishes server failures from rejected credentials")

        scenario = Scenario()
        scenario.tags_gate = asyncio.Event()
        context, page = await new_page(browser, scenario)
        await page.goto(base_url)
        await assert_dashboard(page)
        await expect(page.get_by_role("button", name="Gestisci tag")).to_be_disabled()
        scenario.tags_status = 503
        scenario.tags_gate.set()
        await expect(page.get_by_role("alert")).to_contain_text("tag")
        await assert_dashboard(page)
        scenario.tags_status = 200
        await page.get_by_role("button", name="Riprova", exact=True).click()
        await expect(page.get_by_role("button", name="Gestisci tag")).to_be_enabled()
        await expect(page.get_by_role("alert")).to_have_count(0)
        await context.close()
        print("PASS: slow or failed tags do not block watchlist, retry recovers tags")

        scenario = Scenario()
        scenario.watchlist_status = 503
        context, page = await new_page(browser, scenario)
        await page.goto(base_url)
        await expect(page.get_by_role("alert")).to_contain_text("watchlist")
        scenario.watchlist_status = 200
        await page.get_by_role("button", name="Riprova", exact=True).click()
        await assert_dashboard(page)
        await context.close()
        print("PASS: failed watchlist has working retry")

        # Missing lazy JS (e.g. stale deploy) shows recovery instead of a blank page.
        scenario = Scenario()
        context, page = await new_page(browser, scenario, saved=False)
        await context.route("**/assets/DashboardPage-*.js", lambda route: route.abort())
        await page.goto(base_url + "/login")
        await submit(page)
        await expect(page.get_by_role("button", name="Ricarica pagina")).to_be_visible()
        await context.unroute("**/assets/DashboardPage-*.js")
        await page.get_by_role("button", name="Ricarica pagina").click()
        await assert_dashboard(page)
        assert await page.evaluate("localStorage.getItem('wikiscout_token')") == TOKEN
        await context.close()
        print("PASS: failed lazy import displays recovery; reload keeps login and opens dashboard")
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5175")
    args = parser.parse_args()
    asyncio.run(main(args.base_url.rstrip("/")))
