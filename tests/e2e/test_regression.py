import re
import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


@pytest.mark.regression
class TestRegression:

    def test_navigation_between_pages(self, page: Page, streamlit_server: str):
        page.goto(streamlit_server)
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("button", name="Onboarding")).to_be_visible()
        expect(page.get_by_role("button", name="Existing")).to_be_visible()
        page.get_by_role("button", name="Onboarding").click()
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Phase 1: File Parsing & Preview")).to_be_visible()
        page.get_by_role("button", name="Existing").click()
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Phase 1: File Detection & Preview")).to_be_visible()

    def test_cannot_proceed_without_path(self, onb_page: Page):
        proceed_btn = onb_page.get_by_role("button", name="Proceed to Column Mapping")
        expect(proceed_btn).not_to_be_visible()

    def test_cannot_proceed_without_both_paths(self, ex_page: Page):
        proceed_btn = ex_page.get_by_role("button", name="Proceed to Column Mapping")
        expect(proceed_btn).not_to_be_visible()

    def test_developer_mode_toggle(self, onb_page: Page):
        dev_label = onb_page.locator("label").filter(has_text="Developer Mode")
        dev_label.click()
        onb_page.wait_for_timeout(500)
        expect(onb_page.get_by_text("Developer Diagnostics")).to_be_visible()
        dev_label.click()
        onb_page.wait_for_timeout(500)
        expect(onb_page.get_by_text("Developer Diagnostics")).not_to_be_visible()

    def test_detection_shows_status(self, onb_page: Page, test_data: dict):
        onb_page.locator(ONB_FOLDER_INPUT).fill(test_data["onboarding_dir"])
        onb_page.locator(ONB_FOLDER_INPUT).press("Tab")
        onb_page.wait_for_timeout(2000)
        expect(onb_page.get_by_text("Parsing complete")).to_be_visible()

    def test_invalid_path_shows_error(self, onb_page: Page):
        onb_page.locator(ONB_FOLDER_INPUT).fill("/nonexistent/path")
        onb_page.locator(ONB_FOLDER_INPUT).press("Tab")
        onb_page.wait_for_timeout(2000)
        expect(onb_page.get_by_text("Complete file detection")).to_be_visible()

    def test_processing_history_available(self, onb_page: Page, test_data: dict):
        page = onb_page
        page.locator(ONB_FOLDER_INPUT).fill(test_data["onboarding_dir"])
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)

        def _select_combobox_option(partial_label: str, option: str):
            page.locator(f'[aria-label*="{partial_label}"]').click()
            page.wait_for_timeout(300)
            page.get_by_role("option", name=option).click()
            page.wait_for_timeout(300)

        _select_combobox_option("Retailer Store Column", "Store")
        _select_combobox_option("UPC Column", "UPC")
        _select_combobox_option("Description Column", "Description")
        _select_combobox_option("Units Column", "Units")
        _select_combobox_option("Price Column", "Price")

        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.wait_for_timeout(3000)
        page.locator("label").filter(has_text="Compare Store List").click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Validate Onboarding").click()
        page.wait_for_timeout(3000)
        expect(page.get_by_text("Processing History")).to_be_visible()

    def test_missing_store_list_shows_error(self, onb_page: Page, test_data: dict):
        page = onb_page
        page.locator(ONB_FOLDER_INPUT).fill(test_data["onboarding_dir"])
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)

        def _select_combobox_option(partial_label: str, option: str):
            page.locator(f'[aria-label*="{partial_label}"]').click()
            page.wait_for_timeout(300)
            page.get_by_role("option", name=option).click()
            page.wait_for_timeout(300)

        _select_combobox_option("Retailer Store Column", "Store")
        _select_combobox_option("UPC Column", "UPC")
        _select_combobox_option("Description Column", "Description")
        _select_combobox_option("Units Column", "Units")
        _select_combobox_option("Price Column", "Price")

        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.wait_for_timeout(3000)
        page.get_by_role("button", name="Validate Onboarding").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_text("Store list file is required")).to_be_visible()
