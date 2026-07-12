import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingConfigValidation:

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

    def _navigate_to_config_validation(self, page: Page, test_data: dict):
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Configuration complete")).to_be_visible()
        page.get_by_role("button", name="Validate Configuration").click()
        page.wait_for_timeout(1500)

    def test_config_validation_heading(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_config_validation(page, test_data)
        expect(page.get_by_text("Validate Configuration")).to_be_visible()

    def test_config_validation_success(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_config_validation(page, test_data)
        expect(page.get_by_text("Configuration is valid")).to_be_visible()

    def test_config_validation_proceed_button(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_config_validation(page, test_data)
        expect(page.get_by_role("button", name="Proceed to Processing")).to_be_visible()

    def test_config_validation_proceeds_to_processing(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._navigate_to_config_validation(page, test_data)
        page.get_by_role("button", name="Proceed to Processing").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Store List Input")).to_be_visible()
