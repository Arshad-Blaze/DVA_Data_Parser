import pytest
from playwright.sync_api import Page, expect

BAU_INPUT = 'input[aria-label="BAU Folder Path"]'
TEST_INPUT = 'input[aria-label="Test Folder Path"]'


class TestExistingReports:

    def _fill_paths(self, page: Page, bau_dir: str, test_dir: str):
        page.locator(BAU_INPUT).fill(bau_dir)
        page.locator(BAU_INPUT).press("Tab")
        page.wait_for_timeout(2000)
        page.locator(TEST_INPUT).fill(test_dir)
        page.locator(TEST_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def _complete_config_wizard(self, page: Page):
        for label in [
            "General Information", "File Format", "Schema & Columns",
            "Business Rules", "Validation Settings", "Output Settings",
        ]:
            btn = page.get_by_role("button", name=f"Confirm {label}")
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)

    def _select_combobox_option(self, page: Page, partial_label: str, option: str):
        page.locator(f'[aria-label*="{partial_label}"]').click()
        page.wait_for_timeout(300)
        page.get_by_role("option", name=option).click()
        page.wait_for_timeout(300)

    def _select_columns(self, page: Page):
        self._select_combobox_option(page, "Store (BAU)", "Store")
        self._select_combobox_option(page, "Units (BAU)", "Units")
        self._select_combobox_option(page, "Price (BAU)", "Price")
        self._select_combobox_option(page, "UPC (BAU)", "UPC")
        self._select_combobox_option(page, "Description (BAU)", "Description")
        self._select_combobox_option(page, "Store (Test)", "Store")
        self._select_combobox_option(page, "Units (Test)", "Units")
        self._select_combobox_option(page, "Price (Test)", "Price")
        self._select_combobox_option(page, "UPC (Test)", "UPC")
        self._select_combobox_option(page, "Description (Test)", "Description")

    def _navigate_to_reports(self, page: Page, test_data: dict):
        self._fill_paths(page, test_data["bau_dir"], test_data["test_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Validate Configurations").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing").click()
        page.wait_for_timeout(1500)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.wait_for_timeout(3000)
        page.get_by_role("button", name="Validate").click()
        page.wait_for_timeout(3000)

    def test_reports_heading(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_reports(page, test_data)
        expect(page.get_by_text("Step 7: Reports")).to_be_visible()

    def test_execution_summary_displayed(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_reports(page, test_data)
        expect(page.get_by_text("Execution Summary")).to_be_visible()

    def test_processing_history_displayed(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_reports(page, test_data)
        expect(page.get_by_text("Processing History")).to_be_visible()

    def test_download_buttons_visible(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_reports(page, test_data)
        expect(page.get_by_role("button", name="Download Store Validation")).to_be_visible()
        expect(page.get_by_role("button", name="Download Item Validation")).to_be_visible()

    def test_start_over_from_reports(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_reports(page, test_data)
        page.get_by_role("button", name="Start Over").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Step 2: Discovery")).to_be_visible()
