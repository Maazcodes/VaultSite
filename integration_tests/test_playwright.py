from playwright.sync_api import sync_playwright
import pytest


# @pytest.mark.xfail(reason="environment probably doesn't have a browser available")
def test_dashboard_is_working(super_user, live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{live_server}/dashboard")
        assert page.title() == "Vault: Digital Repository & Preservation Service"
        browser.close()
