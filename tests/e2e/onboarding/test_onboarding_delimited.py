import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingDelimitedFlow:

    def _fill_folder(self, page: Page, path: str):
        page.locator(ONB_FOLDER_INPUT).fill(path)
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def _complete_config_wizard(self, page: Page):
        for label in [
            "General Information",
            "File Format",
            "Schema & Columns",
            "Business Rules",
            "Validation Settings",
            "Output Settings",
        ]:
            page.get_by_role("button", name=f"Confirm {label}").click()
            page.wait_for_timeout(500)

    def test_detection_completes(self, onb_page: Page, test_data: dict):
        self._fill_folder(onb_page, test_data["onboarding_dir"])
        expect(onb_page.get_by_text("Parsing complete")).to_be_visible()

    def test_preview_appears(self, onb_page: Page, test_data: dict):
        self._fill_folder(onb_page, test_data["onboarding_dir"])
        expect(onb_page.get_by_text("Data Preview")).to_be_visible()

    def test_progressive_config_button_appears(self, onb_page: Page, test_data: dict):
        self._fill_folder(onb_page, test_data["onboarding_dir"])
        expect(onb_page.get_by_role("button", name="Progressive Configuration")).to_be_visible()

    def test_config_phase_loads(self, onb_page: Page, test_data: dict):
        self._fill_folder(onb_page, test_data["onboarding_dir"])
        onb_page.get_by_role("button", name="Progressive Configuration").click()
        onb_page.wait_for_timeout(1500)
        expect(onb_page.get_by_text("General Information")).to_be_visible()

    def test_config_wizard_completes(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Configuration complete")).to_be_visible()

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

    def _navigate_to_processing(self, page: Page, test_data: dict):
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Proceed to Processing").click()
        page.wait_for_timeout(1500)

    def test_processing_phase_widgets(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_processing(page, test_data)
        expect(onb_page.get_by_label("Retailer Store Column")).to_be_visible()

    def test_full_onboarding_flow(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_processing(page, test_data)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Column mapping confirmed")).to_be_visible()
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.wait_for_timeout(3000)
        expect(page.get_by_text("Validation")).to_be_visible()

    def _navigate_to_validation(self, page: Page, test_data: dict):
        self._navigate_to_processing(page, test_data)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing & Validation").click()
        page.wait_for_timeout(3000)

    def _uncheck_compare_store_list(self, page: Page):
        page.locator("label").filter(has_text="Compare Store List").click()
        page.wait_for_timeout(500)

    def test_validation_executes(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_validation(page, test_data)
        self._uncheck_compare_store_list(page)
        page.get_by_role("button", name="Validate Onboarding").click()
        page.wait_for_timeout(3000)
        expect(page.get_by_text("Onboarding Validation Results")).to_be_visible()

    def test_reports_available(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_validation(page, test_data)
        self._uncheck_compare_store_list(page)
        page.get_by_role("button", name="Validate Onboarding").click()
        page.wait_for_timeout(3000)
        expect(page.get_by_role("button", name="Download UPC Summary")).to_be_visible()

    def test_start_over_resets(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_validation(page, test_data)
        self._uncheck_compare_store_list(page)
        page.get_by_role("button", name="Validate Onboarding").click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Start Over").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Step 2: Discovery")).to_be_visible()
