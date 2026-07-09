import pytest
from playwright.sync_api import Page, expect

BAU_INPUT = 'input[aria-label="BAU Folder Path"]'
TEST_INPUT = 'input[aria-label="Test Folder Path"]'


class TestExistingConfigValidation:

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

    def _navigate_to_config_validation(self, page: Page, test_data: dict):
        self._fill_paths(page, test_data["bau_dir"], test_data["test_dir"])
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)
        self._complete_config_wizard(page)
        page.wait_for_timeout(1000)

    def test_config_validation_heading(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_config_validation(page, test_data)
        expect(page.get_by_text("Validate Configuration")).to_be_visible()

    def test_bau_validation_section(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_config_validation(page, test_data)
        expect(page.get_by_text("BAU Configuration")).to_be_visible()

    def test_test_validation_section(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_config_validation(page, test_data)
        expect(page.get_by_text("Test Configuration")).to_be_visible()

    def test_proceed_button_visible_when_valid(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_config_validation(page, test_data)
        expect(page.get_by_role("button", name="Proceed to Processing")).to_be_visible()

    def test_proceeds_to_processing(self, ex_page: Page, test_data: dict):
        page = ex_page
        self._navigate_to_config_validation(page, test_data)
        page.get_by_role("button", name="Proceed to Processing").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Store (BAU)", exact=True)).to_be_visible()
