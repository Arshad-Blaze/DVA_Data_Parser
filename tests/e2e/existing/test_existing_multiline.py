import pytest
from playwright.sync_api import Page, expect

BAU_INPUT = 'input[aria-label="BAU Folder Path"]'
TEST_INPUT = 'input[aria-label="Test Folder Path"]'


class TestExistingMultilineFlow:

    def _fill_paths(self, page: Page, bau_dir: str, test_dir: str):
        page.locator(BAU_INPUT).fill(bau_dir)
        page.locator(BAU_INPUT).press("Tab")
        page.wait_for_timeout(2000)
        page.locator(TEST_INPUT).fill(test_dir)
        page.locator(TEST_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def _flatten_and_apply_schema(self, page: Page):
        page.get_by_role("button", name="Flatten Records").click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Apply Schema").click()
        page.wait_for_timeout(1500)

    def test_detects_multiline_both_sides(self, ex_page: Page, multiline_test_data: dict):
        self._fill_paths(ex_page,
                         multiline_test_data["bau_ml_dir"],
                         multiline_test_data["test_ml_dir"])
        expect(ex_page.get_by_text("Multi-line structured file detected")).to_be_visible()

    def test_raw_previews_appear(self, ex_page: Page, multiline_test_data: dict):
        self._fill_paths(ex_page,
                         multiline_test_data["bau_ml_dir"],
                         multiline_test_data["test_ml_dir"])
        expect(ex_page.get_by_text("BAU Multiline")).to_be_visible()
        expect(ex_page.get_by_text("Test Multiline")).to_be_visible()

    def test_flatten_records(self, ex_page: Page, multiline_test_data: dict):
        self._fill_paths(ex_page,
                         multiline_test_data["bau_ml_dir"],
                         multiline_test_data["test_ml_dir"])
        ex_page.get_by_role("button", name="Flatten Records").click()
        ex_page.wait_for_timeout(2000)
        expect(ex_page.get_by_text("Define Column Schema")).to_be_visible()

    def test_apply_schema(self, ex_page: Page, multiline_test_data: dict):
        self._fill_paths(ex_page,
                         multiline_test_data["bau_ml_dir"],
                         multiline_test_data["test_ml_dir"])
        self._flatten_and_apply_schema(ex_page)
        expect(ex_page.get_by_text("Proceed to Column Mapping")).to_be_visible()

    def test_proceed_to_column_mapping(self, ex_page: Page, multiline_test_data: dict):
        page = ex_page
        self._fill_paths(page,
                         multiline_test_data["bau_ml_dir"],
                         multiline_test_data["test_ml_dir"])
        self._flatten_and_apply_schema(page)
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Phase 2: Column Mapping")).to_be_visible()
