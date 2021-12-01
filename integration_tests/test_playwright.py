from playwright.sync_api import sync_playwright
import pytest

from vault.tests import super_user


def test_dashboard_is_working(super_user, live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{live_server}/dashboard")
        assert page.title() == "Vault: Digital Repository & Preservation Service"
        browser.close()
