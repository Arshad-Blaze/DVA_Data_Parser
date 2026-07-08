import json
import os
import re
import pytest
from playwright.sync_api import Page, expect

ONB_FOLDER_INPUT = 'input[aria-label="Folder Path"]'


class TestOnboardingConfigSave:

    def _fill_folder(self, page: Page, path: str):
        page.locator(ONB_FOLDER_INPUT).fill(path)
        page.locator(ONB_FOLDER_INPUT).press("Tab")
        page.wait_for_timeout(2000)

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

    def _navigate_to_column_mapping(self, page: Page, test_data: dict):
        self._fill_folder(page, test_data["onboarding_dir"])
        page.get_by_role("button", name="Proceed to Column Mapping").click()
        page.wait_for_timeout(1500)

    def test_save_config_button_visible_after_mapping(self, onb_page: Page, test_data: dict, tmp_path):
        page = onb_page
        self._navigate_to_column_mapping(page, test_data)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Column mapping confirmed")).to_be_visible()
        expect(page.get_by_label("Save config to (optional)")).to_be_visible()

    def test_save_config_writes_json(self, onb_page: Page, test_data: dict, tmp_path):
        page = onb_page
        self._navigate_to_column_mapping(page, test_data)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)

        config_path = os.path.join(str(tmp_path), "test_config.json")
        page.get_by_label("Save config to (optional)").fill(config_path)
        page.get_by_label("Save config to (optional)").press("Tab")
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Save Config").click()
        page.wait_for_timeout(1000)

        assert os.path.exists(config_path), "Config file was not written"
        with open(config_path) as f:
            data = json.load(f)
        assert "file_type" in data
        assert data.get("store_col") == "Store"
        assert data.get("upc_col") == "UPC"

    def test_saved_config_can_be_loaded(self, onb_page: Page, test_data: dict, tmp_path):
        page = onb_page
        self._navigate_to_column_mapping(page, test_data)
        self._select_columns(page)
        page.get_by_role("button", name="Confirm Mapping").click()
        page.wait_for_timeout(1500)

        config_path = os.path.join(str(tmp_path), "reload_config.json")
        page.get_by_label("Save config to (optional)").fill(config_path)
        page.get_by_label("Save config to (optional)").press("Tab")
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Save Config").click()
        page.wait_for_timeout(1000)

        page.get_by_role("button", name="Start Over").click()
        page.wait_for_timeout(1500)
        expect(page.get_by_text("Phase 1: File Parsing & Preview")).to_be_visible()

        self._fill_folder(page, test_data["onboarding_dir"])
        page.wait_for_timeout(500)
        page.locator('input[aria-label="Optional: Load Config (JSON)"]').fill(config_path)
        page.locator('input[aria-label="Optional: Load Config (JSON)"]').press("Tab")
        page.wait_for_timeout(2000)
        expect(page.get_by_text(re.compile(r"Config.*loaded"))).to_be_visible()
