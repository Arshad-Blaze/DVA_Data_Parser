import re
import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingConfigBuilder:

    def _fill_folder(self, page: Page, path: str):
        page.locator(ONB_FOLDER_INPUT).fill(path)
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def test_generate_config_button_appears(self, onb_page: Page, test_data: dict):
        self._fill_folder(onb_page, test_data["onboarding_dir"])
        expect(onb_page.get_by_role("button", name="Generate Configuration")).to_be_visible()

    def test_config_review_shows_after_generate(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Generate Configuration").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_text("Configuration Review")).to_be_visible()
        expect(page.get_by_text("Column Mapping")).to_be_visible()

    def test_config_shows_detected_columns(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Generate Configuration").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_label("Store Column")).to_be_visible()
        expect(page.get_by_label("UPC Column")).to_be_visible()
        expect(page.get_by_label("Description Column")).to_be_visible()
        expect(page.get_by_label("Units Column")).to_be_visible()
        expect(page.get_by_label("Price Column")).to_be_visible()

    def test_config_shows_validation_toggles(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Generate Configuration").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_text("Validation Configuration")).to_be_visible()
        expect(page.get_by_label("Store Level Validation")).to_be_visible()
        expect(page.get_by_label("Item Level Validation")).to_be_visible()

    def test_accept_config_locks_and_shows_success(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Generate Configuration").click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Accept Configuration").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_text("Configuration locked")).to_be_visible()

    def test_full_config_builder_flow_to_column_mapping(self, onb_page: Page, test_data: dict):
        page = onb_page
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Generate Configuration").click()
        page.wait_for_timeout(2000)

        expect(page.get_by_text("Configuration Review")).to_be_visible()

        page.get_by_role("button", name="Accept Configuration").click()
        page.wait_for_timeout(2000)

        expect(page.get_by_text("Configuration locked")).to_be_visible()

        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Phase 2: Column Mapping")).to_be_visible()
