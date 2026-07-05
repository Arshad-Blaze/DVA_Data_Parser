import re
import pytest
from playwright.sync_api import Page, expect

BAU_INPUT = 'input[aria-label="BAU Folder Path"]'
TEST_INPUT = 'input[aria-label="Test Folder Path"]'


class TestExistingDelimitedFlow:

    def _fill_paths(self, page: Page, bau_dir: str, test_dir: str):
        page.locator(BAU_INPUT).fill(bau_dir)
        page.locator(BAU_INPUT).press("Tab")
        page.wait_for_timeout(2000)
        page.locator(TEST_INPUT).fill(test_dir)
        page.locator(TEST_INPUT).press("Tab")
        page.wait_for_timeout(2000)

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

    def _navigate_to_validation(self, page: Page, test_data: dict):
        self._fill_paths(page, test_data["bau_dir"], test_data["test_dir"])
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.get_by_text("Phase 3: Validation").wait_for(timeout=120000)

    def test_detection_completes_for_both_sides(self, ex_page: Page, test_data: dict):
        self._fill_paths(ex_page, test_data["bau_dir"], test_data["test_dir"])
        expect(ex_page.get_by_text(re.compile(r"Delimited"))).to_have_count(2)

    def test_previews_appear(self, ex_page: Page, test_data: dict):
        self._fill_paths(ex_page, test_data["bau_dir"], test_data["test_dir"])
        expect(ex_page.get_by_text("BAU Preview")).to_be_visible()
        expect(ex_page.get_by_text("Test Preview")).to_be_visible()

    def test_proceed_to_column_mapping(self, ex_page: Page, test_data: dict):
        self._fill_paths(ex_page, test_data["bau_dir"], test_data["test_dir"])
        ex_page.get_by_role("button", name="Proceed to Column Mapping").click()
        ex_page.wait_for_timeout(1500)
        expect(ex_page.get_by_text("Phase 2: Column Mapping")).to_be_visible()

    def test_column_mapping_widgets_present(self, ex_page: Page, test_data: dict):
        self._fill_paths(ex_page, test_data["bau_dir"], test_data["test_dir"])
        ex_page.get_by_role("button", name="Proceed to Column Mapping").click()
        ex_page.wait_for_timeout(1500)
        expect(ex_page.get_by_text("Store (BAU)", exact=True)).to_be_visible()
        expect(ex_page.get_by_text("Units (BAU)", exact=True)).to_be_visible()
        expect(ex_page.get_by_text("Price (BAU)", exact=True)).to_be_visible()
        expect(ex_page.get_by_text("Store (Test)", exact=True)).to_be_visible()
        expect(ex_page.get_by_text("Units (Test)", exact=True)).to_be_visible()
        expect(ex_page.get_by_text("Price (Test)", exact=True)).to_be_visible()

    def test_full_existing_flow(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._fill_paths(page, test_data["bau_dir"], test_data["test_dir"])
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Column mapping confirmed")).to_be_visible()
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.wait_for_timeout(4000)
        expect(page.get_by_text("Phase 3: Validation")).to_be_visible()

    def test_validation_executes(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_validation(page, test_data)
        page.get_by_role("button", name="Validate").click()
        page.wait_for_timeout(4000)
        expect(page.get_by_text("Validation Results")).to_be_visible()

    def test_reports_available_existing(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_validation(page, test_data)
        page.get_by_role("button", name="Validate").click()
        page.wait_for_timeout(4000)
        expect(page.get_by_role("button", name="Download Store Validation")).to_be_visible()
        expect(page.get_by_role("button", name="Download Item Validation")).to_be_visible()
        expect(page.get_by_text("Execution Summary")).to_be_visible()

    def test_start_over_resets(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_validation(page, test_data)
        page.get_by_role("button", name="Validate").click()
        page.wait_for_timeout(3000)
        page.get_by_role("button", name="Start Over").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Phase 1: File Detection & Preview")).to_be_visible()
