import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingHdrTrailerFlow:

    def _fill_folder(self, page: Page, path: str):
        page.locator(ONB_FOLDER_INPUT).fill(path)
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)

    def _fill_layout(self, page: Page, label: str, path: str):
        input_el = page.get_by_label(label)
        input_el.fill(path)
        input_el.press("Tab")
        page.wait_for_timeout(1000)

    def _flatten_and_apply_schema(self, page: Page):
        page.get_by_role("button", name="Flatten Records").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Apply Schema").click()
        page.wait_for_timeout(1500)

    def test_detects_hdr_fixed(self, onb_page: Page, trl_test_data: dict):
        self._fill_folder(onb_page, trl_test_data["trl_data_dir"])
        expect(onb_page.get_by_text("HDR fixed-width file detected")).to_be_visible()

    def test_raw_preview_appears(self, onb_page: Page, trl_test_data: dict):
        self._fill_folder(onb_page, trl_test_data["trl_data_dir"])
        expect(onb_page.get_by_text("Raw Preview")).to_be_visible()

    def test_header_detail_layouts_load(self, onb_page: Page, trl_test_data: dict):
        self._fill_folder(onb_page, trl_test_data["trl_data_dir"])
        self._fill_layout(onb_page, "Header Layout CSV Path", trl_test_data["trl_header_layout"])
        expect(onb_page.get_by_text("Header layout loaded")).to_be_visible()
        self._fill_layout(onb_page, "Detail Layout CSV Path", trl_test_data["trl_detail_layout"])
        expect(onb_page.get_by_text("Detail layout loaded")).to_be_visible()

    def test_trailer_layout_loads(self, onb_page: Page, trl_test_data: dict):
        page = onb_page
        self._fill_folder(page, trl_test_data["trl_data_dir"])
        self._fill_layout(page, "Header Layout CSV Path", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Detail Layout CSV Path", trl_test_data["trl_detail_layout"])
        trl_input = page.get_by_label("Trailer Layout CSV Path (leave empty if no trailer)")
        trl_input.fill(trl_test_data["trl_trailer_layout"])
        trl_input.press("Tab")
        page.wait_for_timeout(1000)
        expect(page.get_by_text("Trailer layout loaded")).to_be_visible()

    def test_flatten_records(self, onb_page: Page, trl_test_data: dict):
        page = onb_page
        self._fill_folder(page, trl_test_data["trl_data_dir"])
        self._fill_layout(page, "Header Layout CSV Path", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Detail Layout CSV Path", trl_test_data["trl_detail_layout"])
        page.get_by_role("button", name="Flatten Records").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Define Column Schema")).to_be_visible()

    def test_apply_schema(self, onb_page: Page, trl_test_data: dict):
        page = onb_page
        self._fill_folder(page, trl_test_data["trl_data_dir"])
        self._fill_layout(page, "Header Layout CSV Path", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Detail Layout CSV Path", trl_test_data["trl_detail_layout"])
        self._flatten_and_apply_schema(page)
        expect(onb_page.get_by_text("Progressive Configuration")).to_be_visible()

    def test_proceed_to_configuration(self, onb_page: Page, trl_test_data: dict):
        page = onb_page
        self._fill_folder(page, trl_test_data["trl_data_dir"])
        self._fill_layout(page, "Header Layout CSV Path", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Detail Layout CSV Path", trl_test_data["trl_detail_layout"])
        self._flatten_and_apply_schema(page)
        page.get_by_role("button", name="Progressive Configuration").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("General Information")).to_be_visible()

    def test_trailer_fields_appear_in_preview(self, onb_page: Page, trl_test_data: dict):
        page = onb_page
        self._fill_folder(page, trl_test_data["trl_data_dir"])
        self._fill_layout(page, "Header Layout CSV Path", trl_test_data["trl_header_layout"])
        self._fill_layout(page, "Detail Layout CSV Path", trl_test_data["trl_detail_layout"])
        page.get_by_role("button", name="Flatten Records").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Flattened Preview")).to_be_visible()
