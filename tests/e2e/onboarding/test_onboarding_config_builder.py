import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingConfigBuilder:

    def _fill_folder(self, page: Page, path: str):
        page.locator(ONB_FOLDER_INPUT).fill(path)
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def test_progressive_config_button_appears(self, onb_page: Page, test_data: dict):
        self._fill_folder(onb_page, test_data["onboarding_dir"])
        expect(onb_page.get_by_role("button", name="Progressive Configuration")).to_be_visible()

    def test_config_wizard_shows_after_click(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("General Information", exact=True)).to_be_visible()

    def test_config_shows_detected_columns(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        for label in [
            "General Information",
            "File Format",
            "Schema & Columns",
            "Business Rules",
            "Validation Settings",
            "Output Settings",
        ]:
            btn = page.get_by_role("button", name=f"Confirm {label}")
            expect(btn).to_be_visible()
            btn.click()
            page.wait_for_timeout(500)
        expect(page.get_by_text("Configuration complete")).to_be_visible()

    def test_accept_config_shows_success(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        for label in [
            "General Information", "File Format", "Schema & Columns",
            "Business Rules", "Validation Settings", "Output Settings",
        ]:
            page.get_by_role("button", name=f"Confirm {label}").click()
            page.wait_for_timeout(500)
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Configuration complete")).to_be_visible()

    def test_full_config_builder_flow_to_processing(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        for label in [
            "General Information", "File Format", "Schema & Columns",
            "Business Rules", "Validation Settings", "Output Settings",
        ]:
            page.get_by_role("button", name=f"Confirm {label}").click()
            page.wait_for_timeout(500)
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Configuration complete")).to_be_visible()
        page.get_by_role("button", name="Validate Configuration").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Proceed to Processing").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Retailer Store Column")).to_be_visible()
