import pytest
from playwright.sync_api import Page, expect

BAU_INPUT = 'input[aria-label="BAU Folder Path"]'
TEST_INPUT = 'input[aria-label="Test Folder Path"]'


class TestExistingHdrTrailerFlow:

    def _fill_paths(self, page: Page, bau_dir: str, test_dir: str):
        page.locator(BAU_INPUT).fill(bau_dir)
        page.locator(BAU_INPUT).press("Tab")
        page.wait_for_timeout(2000)
        page.locator(TEST_INPUT).fill(test_dir)
        page.locator(TEST_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def _fill_layout(self, page: Page, label: str, path: str):
        input_el = page.get_by_label(label)
        input_el.fill(path)
        input_el.press("Tab")
        page.wait_for_timeout(1000)

    def _flatten_and_apply_schema(self, page: Page):
        page.get_by_role("button", name="Flatten Records").click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Apply Schema").click()
        page.wait_for_timeout(1500)

    def test_detects_hdr_both_sides(self, ex_page: Page, trl_test_data: dict):
        page = ex_page
        self._fill_paths(page, trl_test_data["bau_trl_dir"], trl_test_data["test_trl_dir"])
        expect(page.get_by_text("Multi-line structured file detected")).to_be_visible()

    def test_hdr_prefix_shown(self, ex_page: Page, trl_test_data: dict):
        page = ex_page
        self._fill_paths(page, trl_test_data["bau_trl_dir"], trl_test_data["test_trl_dir"])
        expect(page.get_by_text("HDR prefix: HDR").first).to_be_visible()

    def test_header_detail_layouts_bau(self, ex_page: Page, trl_test_data: dict):
        page = ex_page
        self._fill_paths(page, trl_test_data["bau_trl_dir"], trl_test_data["test_trl_dir"])
        self._fill_layout(page, "BAU Header Layout CSV", trl_test_data["trl_header_layout"])
        expect(page.get_by_text("Header layout ready")).to_be_visible()
        self._fill_layout(page, "BAU Detail Layout CSV", trl_test_data["trl_detail_layout"])
        expect(page.get_by_text("Detail layout ready")).to_be_visible()

    def test_trailer_layout_bau(self, ex_page: Page, trl_test_data: dict):
        page = ex_page
        self._fill_paths(page, trl_test_data["bau_trl_dir"], trl_test_data["test_trl_dir"])
        self._fill_layout(page, "BAU Header Layout CSV", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "BAU Detail Layout CSV", trl_test_data["trl_detail_layout"])
        trl_input = page.get_by_label("BAU Trailer Layout CSV (optional)")
        trl_input.fill(trl_test_data["trl_trailer_layout"])
        trl_input.press("Tab")
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Trailer layout ready")).to_be_visible()

    def test_flatten_records(self, ex_page: Page, trl_test_data: dict):
        page = ex_page
        self._fill_paths(page, trl_test_data["bau_trl_dir"], trl_test_data["test_trl_dir"])
        self._fill_layout(page, "BAU Header Layout CSV", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "BAU Detail Layout CSV", trl_test_data["trl_detail_layout"])
        self._fill_layout(page, "Test Header Layout CSV", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Test Detail Layout CSV", trl_test_data["trl_detail_layout"])
        page.get_by_role("button", name="Flatten Records").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_text("Define Column Schema")).to_be_visible()

    def test_apply_schema(self, ex_page: Page, trl_test_data: dict):
        page = ex_page
        self._fill_paths(page, trl_test_data["bau_trl_dir"], trl_test_data["test_trl_dir"])
        self._fill_layout(page, "BAU Header Layout CSV", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "BAU Detail Layout CSV", trl_test_data["trl_detail_layout"])
        self._fill_layout(page, "Test Header Layout CSV", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Test Detail Layout CSV", trl_test_data["trl_detail_layout"])
        self._flatten_and_apply_schema(page)
        expect(page.get_by_text("Proceed to Column Mapping")).to_be_visible()

    def test_proceed_to_column_mapping(self, ex_page: Page, trl_test_data: dict):
        page = ex_page
        self._fill_paths(page, trl_test_data["bau_trl_dir"], trl_test_data["test_trl_dir"])
        self._fill_layout(page, "BAU Header Layout CSV", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "BAU Detail Layout CSV", trl_test_data["trl_detail_layout"])
        self._fill_layout(page, "Test Header Layout CSV", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Test Detail Layout CSV", trl_test_data["trl_detail_layout"])
        self._flatten_and_apply_schema(page)
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Phase 2: Column Mapping")).to_be_visible()
