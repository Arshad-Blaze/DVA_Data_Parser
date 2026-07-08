import re
import pytest
from playwright.sync_api import Page, expect

BAU_INPUT = 'input[aria-label="BAU Folder Path"]'
TEST_INPUT = 'input[aria-label="Test Folder Path"]'


class TestExistingValidationConfig:

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

    def test_validation_checkboxes_visible(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_validation(page, test_data)
        expect(page.get_by_text("Store Level Validation")).to_be_visible()
        expect(page.get_by_text("Item Level Validation")).to_be_visible()
        expect(page.get_by_text("Compare Store List")).to_be_visible()
        expect(page.get_by_text("Summary (requires Item)")).to_be_visible()
        expect(page.get_by_text("File Review Report")).to_be_visible()

    def test_can_toggle_individual_validations(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_validation(page, test_data)
        page.locator("label").filter(has_text="File Review Report").click()
        page.wait_for_timeout(300)
        page.locator("label").filter(has_text="Compare Store List").click()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Validate").click()
        page.wait_for_timeout(5000)
        expect(page.get_by_text("Validation Results")).to_be_visible()
