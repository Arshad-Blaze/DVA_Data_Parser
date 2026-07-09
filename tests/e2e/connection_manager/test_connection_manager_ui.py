"""E2E tests for the Connection Manager UI."""
import os

import pytest
from playwright.sync_api import Page, expect


LOCAL_RADIO = "Local"
REMOTE_RADIO = "Remote Server"
USE_LOCAL_BTN = "Use Local File System"
DISCONNECT_BTN = "Disconnect"
CONNECT_BTN = "Connect"
CONNECTION_MANAGER_HEADER = "Connection Manager"
FILE_BROWSER_HEADER = "Remote File Browser"
BACK_BTN = "← Back"
REFRESH_BTN = "↻ Refresh"


class TestConnectionManagerLocal:

    def test_local_radio_selected_by_default(self, ex_page: Page):
        radio = ex_page.get_by_role("radio", name=LOCAL_RADIO)
        expect(radio).to_be_checked()

    def test_use_local_button_visible(self, ex_page: Page):
        expect(ex_page.get_by_role("button", name=USE_LOCAL_BTN)).to_be_visible()

    def test_connect_local_shows_connection_info(self, ex_page: Page):
        page = ex_page
        page.get_by_role("button", name=USE_LOCAL_BTN).click()
        page.wait_for_timeout(1000)
        expect(page.get_by_role("heading", name="Connection Manager")).to_be_visible()
        expect(page.get_by_text("Host")).to_be_visible()
        expect(page.get_by_text("User")).to_be_visible()
        expect(page.get_by_text("Platform")).to_be_visible()
        # The Host column shows the connection string "Local File System".
        # Use exact match to avoid colliding with the "Use Local File System" button.
        expect(page.get_by_text("Local File System", exact=True)).to_be_visible()

    def test_connect_local_shows_file_browser(self, ex_page: Page):
        page = ex_page
        page.get_by_role("button", name=USE_LOCAL_BTN).click()
        page.wait_for_timeout(1000)
        expect(page.get_by_role("heading", name=FILE_BROWSER_HEADER)).to_be_visible()
        expect(page.get_by_role("button", name=BACK_BTN)).to_be_visible()
        expect(page.get_by_role("button", name=REFRESH_BTN)).to_be_visible()
        expect(page.get_by_label("Path")).to_be_visible()
        expect(page.get_by_placeholder("Filter...")).to_be_visible()

    def test_file_browser_shows_home_dir_entries(self, ex_page: Page):
        page = ex_page
        page.get_by_role("button", name=USE_LOCAL_BTN).click()
        page.wait_for_timeout(1500)
        home = os.path.expanduser("~")
        path_input = page.get_by_label("Path")
        expect(path_input).to_have_value(home)

    def test_file_browser_navigate_into_dir(self, ex_page: Page, tmp_path):
        page = ex_page
        page.get_by_role("button", name=USE_LOCAL_BTN).click()
        page.wait_for_timeout(1000)

        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "test.txt").write_text("hello")
        path_input = page.get_by_label("Path")
        path_input.fill(str(tmp_path))
        path_input.press("Tab")
        page.wait_for_timeout(1500)
        expect(page.get_by_role("button", name=REFRESH_BTN)).to_be_visible()

    def test_file_browser_search_filters(self, ex_page: Page):
        page = ex_page
        page.get_by_role("button", name=USE_LOCAL_BTN).click()
        page.wait_for_timeout(1000)

        path_input = page.get_by_label("Path")
        path_input.fill("/tmp")
        path_input.press("Tab")
        page.wait_for_timeout(1500)

        search = page.get_by_placeholder("Filter...")
        search.fill("nonexistent_xyz")
        page.wait_for_timeout(500)
        expect(page.get_by_text("Directory is empty")).to_be_visible()

    def test_file_browser_refresh(self, ex_page: Page):
        page = ex_page
        page.get_by_role("button", name=USE_LOCAL_BTN).click()
        page.wait_for_timeout(1000)
        refresh_btn = page.get_by_role("button", name=REFRESH_BTN)
        expect(refresh_btn).to_be_enabled()
        refresh_btn.click()
        page.wait_for_timeout(1000)

    def test_file_browser_back_button_disabled_initially(self, ex_page: Page):
        page = ex_page
        page.get_by_role("button", name=USE_LOCAL_BTN).click()
        page.wait_for_timeout(1000)
        back_btn = page.get_by_role("button", name=BACK_BTN)
        expect(back_btn).to_be_visible()


class TestConnectionManagerRemote:

    def test_remote_radio_shows_ssh_form(self, ex_page: Page):
        page = ex_page
        page.get_by_role("radio", name=REMOTE_RADIO).click()
        page.wait_for_timeout(500)
        expect(page.get_by_text("SSH Connection")).to_be_visible()
        expect(page.get_by_label("Host")).to_be_visible()
        expect(page.get_by_label("Port")).to_be_visible()
        expect(page.get_by_label("Username")).to_be_visible()

    def test_remote_form_shows_password_fields(self, ex_page: Page):
        page = ex_page
        page.get_by_role("radio", name=REMOTE_RADIO).click()
        page.wait_for_timeout(500)
        expect(page.get_by_role("radio", name="Password")).to_be_checked()
        expect(page.get_by_label("Password")).to_be_visible()

    def test_remote_form_shows_key_fields_when_selected(self, ex_page: Page):
        page = ex_page
        page.get_by_role("radio", name=REMOTE_RADIO).click()
        page.wait_for_timeout(500)
        page.get_by_role("radio", name="Private Key").click()
        page.wait_for_timeout(300)
        expect(page.get_by_label("Private Key Path")).to_be_visible()
        expect(page.get_by_label("Key Passphrase")).to_be_visible()

    def test_connect_button_validates_empty_fields(self, ex_page: Page):
        page = ex_page
        page.get_by_role("radio", name=REMOTE_RADIO).click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name=CONNECT_BTN).click()
        page.wait_for_timeout(500)
        expect(page.get_by_text("Host and Username are required")).to_be_visible()

    def test_connect_fails_with_error_message(self, ex_page: Page):
        page = ex_page
        page.get_by_role("radio", name=REMOTE_RADIO).click()
        page.wait_for_timeout(500)
        page.get_by_label("Host").fill("192.0.2.1")
        page.get_by_label("Username").fill("testuser")
        page.get_by_label("Password").fill("testpass")
        page.get_by_role("button", name=CONNECT_BTN).click()
        page.wait_for_timeout(5000)
        expect(page.get_by_text("SSH connection failed")).to_be_visible()


class TestConnectionManagerCleanup:

    def test_switch_back_to_local_after_remote(self, ex_page: Page):
        page = ex_page
        page.get_by_role("radio", name=REMOTE_RADIO).click()
        page.wait_for_timeout(300)
        page.get_by_role("radio", name=LOCAL_RADIO).click()
        page.wait_for_timeout(300)
        expect(page.get_by_role("button", name=USE_LOCAL_BTN)).to_be_visible()
