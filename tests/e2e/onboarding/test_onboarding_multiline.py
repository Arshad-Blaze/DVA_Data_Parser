import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingMultilineFlow:

    def _fill_folder(self, page: Page, path: str):
        page.locator(ONB_FOLDER_INPUT).fill(path)
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def _flatten_and_apply_schema(self, page: Page):
        page.get_by_role("button", name="Flatten Records").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Apply Schema").click()
        page.wait_for_timeout(1500)

    def test_detects_multiline(self, onb_page: Page, multiline_test_data: dict):
        self._fill_folder(onb_page, multiline_test_data["onboarding_ml_dir"])
        expect(onb_page.get_by_text("Multi-line structured file detected")).to_be_visible()

    def test_raw_preview_appears(self, onb_page: Page, multiline_test_data: dict):
        self._fill_folder(onb_page, multiline_test_data["onboarding_ml_dir"])
        expect(onb_page.get_by_text("Raw Preview (with record-type prefixes)")).to_be_visible()

    def test_flatten_records(self, onb_page: Page, multiline_test_data: dict):
        self._fill_folder(onb_page, multiline_test_data["onboarding_ml_dir"])
        onb_page.get_by_role("button", name="Flatten Records").click()
        onb_page.wait_for_timeout(1500)
        expect(onb_page.get_by_text("Define Column Schema")).to_be_visible()

    def test_apply_schema(self, onb_page: Page, multiline_test_data: dict):
        self._fill_folder(onb_page, multiline_test_data["onboarding_ml_dir"])
        self._flatten_and_apply_schema(onb_page)
        expect(onb_page.get_by_text("Proceed to Column Mapping")).to_be_visible()

    def test_proceed_to_column_mapping(self, onb_page: Page, multiline_test_data: dict):
        page = onb_page
        self._fill_folder(page, multiline_test_data["onboarding_ml_dir"])
        self._flatten_and_apply_schema(page)
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Phase 2: Column Mapping")).to_be_visible()
