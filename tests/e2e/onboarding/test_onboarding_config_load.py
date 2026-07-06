import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'
ONB_CONFIG_INPUT = 'input[aria-label="Optional: Load Config (JSON)"]'


class TestOnboardingConfigLoad:

    def _fill(self, page: Page, selector: str, value: str):
        page.locator(selector).fill(value)
        page.locator(selector).press("Tab")
        page.wait_for_timeout(2000)

    def test_config_load_delimited(self, onb_page: Page, config_test_data: dict):
        page = onb_page
        self._fill(page, ONB_FOLDER_INPUT, config_test_data["delim_dir"])
        page.wait_for_timeout(1000)
        self._fill(page, ONB_CONFIG_INPUT, config_test_data["delim_config"])
        page.wait_for_timeout(1000)
        expect(page.get_by_text("'Delimited Test' loaded")).to_be_visible()

    def test_config_load_multiline_delimited(self, onb_page: Page, config_test_data: dict):
        page = onb_page
        self._fill(page, ONB_FOLDER_INPUT, config_test_data["ml_dir"])
        page.wait_for_timeout(1000)
        self._fill(page, ONB_CONFIG_INPUT, config_test_data["ml_config"])
        page.wait_for_timeout(1000)
        expect(page.get_by_text("'ML Delimited Test' loaded")).to_be_visible()

    def test_config_load_hdr_fixed(self, onb_page: Page, config_test_data: dict):
        page = onb_page
        self._fill(page, ONB_FOLDER_INPUT, config_test_data["hdr_dir"])
        page.wait_for_timeout(1000)
        self._fill(page, ONB_CONFIG_INPUT, config_test_data["hdr_config"])
        page.wait_for_timeout(1000)
        expect(page.get_by_text("'HDR Fixed-Width Test' loaded")).to_be_visible()

    def test_config_load_shows_preview(self, onb_page: Page, config_test_data: dict):
        page = onb_page
        self._fill(page, ONB_FOLDER_INPUT, config_test_data["hdr_dir"])
        page.wait_for_timeout(1000)
        self._fill(page, ONB_CONFIG_INPUT, config_test_data["hdr_config"])
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Flattened Preview (from config)")).to_be_visible()

    def test_config_load_proceed_to_mapping(self, onb_page: Page, config_test_data: dict):
        page = onb_page
        self._fill(page, ONB_FOLDER_INPUT, config_test_data["hdr_dir"])
        page.wait_for_timeout(1000)
        self._fill(page, ONB_CONFIG_INPUT, config_test_data["hdr_config"])
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Proceed to Column Mapping")).to_be_visible()
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Phase 2: Column Mapping")).to_be_visible()
