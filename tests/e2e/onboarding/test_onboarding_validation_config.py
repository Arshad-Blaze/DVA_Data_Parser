import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingValidationConfig:

    def _fill_folder(self, page: Page, path: str):
        page.locator(ONB_FOLDER_INPUT).fill(path)
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def _complete_config_wizard(self, page: Page):
        for label in [
            "General Information", "File Format", "Schema & Columns",
            "Business Rules", "Validation Settings", "Output Settings",
        ]:
            page.get_by_role("button", name=f"Confirm {label}").click()
            page.wait_for_timeout(500)

    def _select_combobox_option(self, page: Page, partial_label: str, option: str):
        page.locator(f'[aria-label*="{partial_label}"]').click()
        page.wait_for_timeout(300)
        page.get_by_role("option", name=option).click()
        page.wait_for_timeout(300)

    def _select_columns(self, page: Page):
        self._select_combobox_option(page, "Retailer Store Column", "Store")
        self._select_combobox_option(page, "UPC Column", "UPC")
        self._select_combobox_option(page, "Description Column", "Description")
        self._select_combobox_option(page, "Units Column", "Units")
        self._select_combobox_option(page, "Price Column", "Price")

    def _navigate_to_validation(self, page: Page, test_data: dict):
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Proceed to Processing").click()
        page.wait_for_timeout(1500)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.wait_for_timeout(3000)

    def test_validation_checkboxes_visible(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_validation(page, test_data)
        expect(page.get_by_text("Compare Store List")).to_be_visible()
        expect(page.get_by_text("Generate Unique UPC Summary")).to_be_visible()
        expect(page.get_by_text("File Review Report")).to_be_visible()

    def test_can_uncheck_compare_store_list(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_validation(page, test_data)
        chk = page.locator("label").filter(has_text="Compare Store List").locator("..").locator("input")
        chk.uncheck()
        page.wait_for_timeout(300)
        assert not chk.is_checked()

    def test_validation_runs_without_compare_store_list(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_validation(page, test_data)
        page.locator("label").filter(has_text="Compare Store List").click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Validate Onboarding").click()
        page.wait_for_timeout(5000)
        expect(page.get_by_text("Onboarding Validation Results")).to_be_visible()
        expect(page.get_by_text("Execution Summary")).to_be_visible()

    def test_validation_runs_with_only_file_review(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_validation(page, test_data)
        page.locator("label").filter(has_text="Compare Store List").click()
        page.wait_for_timeout(300)
        page.locator("label").filter(has_text="Generate Unique UPC Summary").click()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Validate Onboarding").click()
        page.wait_for_timeout(5000)
        expect(page.get_by_text("Onboarding Validation Results")).to_be_visible()
        expect(page.get_by_text("File Review Report")).to_be_visible()
