"""Connection Manager UI — top-level component for managing data sources."""
import logging
import os

import streamlit as st

import polars as pl

from dav_tool.datasource.base import DataSourceError
from dav_tool.datasource.manager import (
    connect_local, connect_ssh, disconnect,
    get_active_source, is_connected, get_active_config,
)
from dav_tool._observability import log_phase
from dav_tool.workflow.discovery import detect_file, DiscoveryResult
from dav_tool._parsers import preview_raw_lines
from dav_tool.ui.helpers import get_file_list

logger = logging.getLogger(__name__)

_CONN_KEY = "_cm_connected"
_CONN_TYPE_KEY = "_cm_conn_type"
_BROWSE_PATH_KEY = "_cm_browse_path"
_BROWSE_HISTORY_KEY = "_cm_browse_history"
_SEARCH_KEY = "_cm_search"

_WORKFLOW_KEY = "_cm_workflow"
_SELECTED_PATH_KEY = "_cm_selected_path"
_BAU_PATH_KEY = "_cm_bau_path"
_TEST_PATH_KEY = "_cm_test_path"

_BAU_BROWSE_PATH_KEY = "_cm_bau_browse_path"
_BAU_BROWSE_HISTORY_KEY = "_cm_bau_browse_history"
_BAU_SEARCH_KEY = "_cm_bau_search"
_TEST_BROWSE_PATH_KEY = "_cm_test_browse_path"
_TEST_BROWSE_HISTORY_KEY = "_cm_test_browse_history"
_TEST_SEARCH_KEY = "_cm_test_search"


def _init_state():
    if _CONN_KEY not in st.session_state:
        st.session_state[_CONN_KEY] = False
    if _CONN_TYPE_KEY not in st.session_state:
        st.session_state[_CONN_TYPE_KEY] = "local"
    if _BROWSE_PATH_KEY not in st.session_state:
        st.session_state[_BROWSE_PATH_KEY] = "/"
    if _BROWSE_HISTORY_KEY not in st.session_state:
        st.session_state[_BROWSE_HISTORY_KEY] = []
    if _SEARCH_KEY not in st.session_state:
        st.session_state[_SEARCH_KEY] = ""
    if _WORKFLOW_KEY not in st.session_state:
        st.session_state[_WORKFLOW_KEY] = "onboarding"
    if _BAU_BROWSE_PATH_KEY not in st.session_state:
        st.session_state[_BAU_BROWSE_PATH_KEY] = "/"
    if _BAU_BROWSE_HISTORY_KEY not in st.session_state:
        st.session_state[_BAU_BROWSE_HISTORY_KEY] = []
    if _BAU_SEARCH_KEY not in st.session_state:
        st.session_state[_BAU_SEARCH_KEY] = ""
    if _TEST_BROWSE_PATH_KEY not in st.session_state:
        st.session_state[_TEST_BROWSE_PATH_KEY] = "/"
    if _TEST_BROWSE_HISTORY_KEY not in st.session_state:
        st.session_state[_TEST_BROWSE_HISTORY_KEY] = []
    if _TEST_SEARCH_KEY not in st.session_state:
        st.session_state[_TEST_SEARCH_KEY] = ""


def _setup_complete() -> bool:
    """Check whether the Connection Manager has completed its job."""
    if not is_connected():
        return False
    workflow = st.session_state.get(_WORKFLOW_KEY, "onboarding")
    if workflow == "onboarding":
        if not st.session_state.get(_SELECTED_PATH_KEY):
            return False
    else:
        if not st.session_state.get(_BAU_PATH_KEY) and not st.session_state.get(_TEST_PATH_KEY):
            return False
    return True


def _status_summary() -> str:
    """Build a one-line status summary for the collapsed CM header."""
    source = get_active_source()
    workflow = st.session_state.get(_WORKFLOW_KEY, "onboarding")
    parts = []
    if source:
        try:
            parts.append(source.get_connection_string()[:30])
        except Exception:
            parts.append("Connected")
    if workflow == "onboarding":
        path = st.session_state.get(_SELECTED_PATH_KEY, "")
        if path:
            parts.append(f"📁 {os.path.basename(path.rstrip('/'))}")
    else:
        bau = st.session_state.get(_BAU_PATH_KEY, "")
        test = st.session_state.get(_TEST_PATH_KEY, "")
        if bau:
            parts.append(f"BAU: {os.path.basename(bau.rstrip('/'))}")
        if test:
            parts.append(f"Test: {os.path.basename(test.rstrip('/'))}")
    discovery = st.session_state.get("_cm_discovery") or st.session_state.get("_cm_bau_discovery")
    if discovery:
        if discovery.file_type:
            parts.append(f"Type: {discovery.file_type}")
        if discovery.delimiter:
            parts.append(f"Delim: {discovery.delimiter}")
    return " | ".join(parts) if parts else "Setup complete"


def render_connection_manager():
    _init_state()

    if "_cm_expanded" not in st.session_state:
        st.session_state["_cm_expanded"] = True

    setup_done = _setup_complete()

    if setup_done and not st.session_state["_cm_expanded"]:
        with st.container(border=True):
            cols = st.columns([4, 1])
            with cols[0]:
                conn_str = _status_summary()
                st.markdown(f"**🔌 Connection Manager** — {conn_str}")
                st.caption("Click Expand to change connection, paths, or re-run detection.")
            with cols[1]:
                if st.button("Expand", use_container_width=True):
                    st.session_state["_cm_expanded"] = True
                    st.rerun()
    else:
        with st.container(border=True):
            _render_cm_content()
            if setup_done:
                if st.button("Collapse Connection Manager", use_container_width=True):
                    st.session_state["_cm_expanded"] = False
                    st.rerun()


def _render_cm_content():
    st.markdown("### Connection Manager")
    col1, col2 = st.columns([1, 3])

    with col1:
        conn_type = st.radio(
            "Connection Type",
            options=["Local", "Remote Server"],
            index=0 if st.session_state[_CONN_TYPE_KEY] == "local" else 1,
            key="cm_type_radio",
            horizontal=True,
        )
        st.session_state[_CONN_TYPE_KEY] = conn_type.lower().replace(" ", "_")

    with col2:
        if conn_type == "Local":
            _render_local()
        else:
            _render_remote_connect()

    if is_connected():
        _render_connection_info()
        _render_workflow_selector()
        _render_selected_preview()


def _render_local():
    if st.button("Use Local File System", use_container_width=True, type="primary"):
        with st.spinner("Connecting to local file system..."):
            try:
                connect_local()
                st.session_state[_CONN_KEY] = True
                st.session_state[_BROWSE_PATH_KEY] = os.path.expanduser("~")
                st.rerun()
            except DataSourceError as e:
                st.error(str(e))


def _render_remote_connect():
    cfg = get_active_config()
    connected = is_connected()

    if connected and cfg and cfg.type == "ssh":
        if st.button("Disconnect", use_container_width=True):
            _clear_paths()
            disconnect()
            st.session_state[_CONN_KEY] = False
            st.rerun()
        return

    with st.expander("SSH Connection", expanded=not connected):
        host = st.text_input("Host", value="", key="cm_host", placeholder="e.g. 192.168.1.100")
        port = st.number_input("Port", min_value=1, max_value=65535, value=22, key="cm_port")
        username = st.text_input("Username", value="", key="cm_user", placeholder="e.g. retailer")

        auth_method = st.radio(
            "Authentication",
            options=["Password", "Private Key"],
            horizontal=True,
            key="cm_auth",
        )

        password = None
        key_file = None
        key_passphrase = None

        if auth_method == "Password":
            password = st.text_input(
                "Password", type="password", key="cm_password",
                placeholder="Enter password",
                help="Password is kept in session memory only, never stored",
            )
        else:
            key_file = st.text_input(
                "Private Key Path", value="", key="cm_key",
                placeholder="e.g. /home/user/.ssh/id_rsa",
            )
            key_passphrase = st.text_input(
                "Key Passphrase", type="password", key="cm_keypass",
                placeholder="(optional)",
            )

        if st.button("Connect", use_container_width=True, type="primary"):
            if not host or not username:
                st.error("Host and Username are required")
                return
            with st.spinner(f"Connecting to {username}@{host}:{port}..."):
                try:
                    connect_ssh(
                        host=host, port=int(port), username=username,
                        password=password if auth_method == "Password" else None,
                        key_file=key_file if auth_method == "Private Key" else None,
                        key_passphrase=key_passphrase,
                    )
                    st.session_state[_CONN_KEY] = True
                    st.session_state[_BROWSE_PATH_KEY] = "/"
                    st.rerun()
                except DataSourceError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Connection failed: {e}")
                    logger.error("SSH connection error", exc_info=True)


def _clear_paths():
    for key in [_SELECTED_PATH_KEY, _BAU_PATH_KEY, _TEST_PATH_KEY]:
        st.session_state.pop(key, None)


def _render_connection_info():
    source = get_active_source()
    if source is None:
        return
    try:
        info = source.get_server_info()
        conn_str = source.get_connection_string()
    except Exception:
        return

    with st.container(border=True):
        cols = st.columns(4)
        with cols[0]:
            st.markdown(f"**Host**  \n{info.get('host', conn_str)}")
        with cols[1]:
            st.markdown(f"**User**  \n{info.get('username', 'N/A')}")
        with cols[2]:
            platform = info.get("platform", info.get("type", "N/A"))
            st.markdown(f"**Platform**  \n{platform[:40] if platform else 'N/A'}")
        with cols[3]:
            disk = info.get("disk", "N/A")
            st.markdown(f"**Disk**  \n{disk[:50] if disk else 'N/A'}")

        if session_id := st.session_state.get("session_id"):
            log_phase("Connection: " + conn_str, session_id)


def _render_workflow_selector():
    workflow = st.radio(
        "Workflow",
        options=["Onboarding", "Format Change"],
        index=0 if st.session_state.get(_WORKFLOW_KEY, "onboarding") == "onboarding" else 1,
        horizontal=True,
        key="cm_workflow_radio",
    )
    new_wf = workflow.lower().replace(" ", "_")
    old_wf = st.session_state.get(_WORKFLOW_KEY, "onboarding")

    if new_wf != old_wf:
        if new_wf == "onboarding":
            st.session_state.pop(_BAU_PATH_KEY, None)
            st.session_state.pop(_TEST_PATH_KEY, None)
        else:
            st.session_state.pop(_SELECTED_PATH_KEY, None)

    st.session_state[_WORKFLOW_KEY] = new_wf

    if new_wf == "onboarding":
        _render_file_browser(
            browse_key=_BROWSE_PATH_KEY,
            history_key=_BROWSE_HISTORY_KEY,
            search_key=_SEARCH_KEY,
            selected_key=_SELECTED_PATH_KEY,
            button_label="Use This Path for Onboarding",
        )
    else:
        _render_paired_file_browsers()


def _render_file_browser(
    browse_key="_cm_browse_path",
    history_key="_cm_browse_history",
    search_key="_cm_search",
    selected_key="_cm_selected_path",
    button_label="Use This Path",
    heading=None,
):
    source = get_active_source()
    if source is None:
        return

    if heading:
        st.markdown(heading)

    select_cols = st.columns([4, 1])
    with select_cols[0]:
        pass
    with select_cols[1]:
        if st.button(button_label, use_container_width=True, type="primary", key=f"use_{selected_key}"):
            st.session_state[selected_key] = st.session_state[browse_key]
            st.session_state["_cm_expanded"] = False
            st.rerun()

    nav_cols = st.columns([1, 1, 4, 1])
    with nav_cols[0]:
        if st.button("← Back", use_container_width=True, key=f"back_{selected_key}"):
            history = st.session_state[history_key]
            if history:
                st.session_state[browse_key] = history.pop()
                st.rerun()
    with nav_cols[1]:
        if st.button("↻ Refresh", use_container_width=True, key=f"refresh_{selected_key}"):
            st.rerun()
    with nav_cols[2]:
        st.text_input(
            "Path", value=st.session_state[browse_key],
            key=f"browse_input_{selected_key}",
            label_visibility="collapsed",
            on_change=lambda: _navigate_to_path(browse_key, f"browse_input_{selected_key}"),
        )
    with nav_cols[3]:
        st.text_input(
            "Search", value="", key=search_key,
            placeholder="Filter...",
            label_visibility="collapsed",
        )

    try:
        entries = source.list_directory(st.session_state[browse_key])
    except DataSourceError as e:
        st.error(str(e))
        return

    search = st.session_state.get(search_key, "").lower()
    if search:
        entries = [e for e in entries if search in e.name.lower()]

    if not entries:
        st.info("Directory is empty")
        return

    for entry in entries:
        icon = "📁" if entry.is_dir else "📄"
        size_str = f" ({_fmt_size(entry.size)})" if entry.size is not None else ""
        label = f"{icon} {entry.name}{size_str}"

        if entry.is_dir:
            if st.button(label, key=f"dir_{selected_key}_{entry.path}", use_container_width=True):
                history = st.session_state[history_key]
                history.append(st.session_state[browse_key])
                st.session_state[browse_key] = entry.path
                st.rerun()
        else:
            st.markdown(f"{label}")


def _render_paired_file_browsers():
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**BAU Production Data**")
        _render_file_browser(
            browse_key=_BAU_BROWSE_PATH_KEY,
            history_key=_BAU_BROWSE_HISTORY_KEY,
            search_key=_BAU_SEARCH_KEY,
            selected_key=_BAU_PATH_KEY,
            button_label="Use This Path for BAU",
        )
    with c2:
        st.markdown("**Test/Comparison Data**")
        _render_file_browser(
            browse_key=_TEST_BROWSE_PATH_KEY,
            history_key=_TEST_BROWSE_HISTORY_KEY,
            search_key=_TEST_SEARCH_KEY,
            selected_key=_TEST_PATH_KEY,
            button_label="Use This Path for Test",
        )


def _render_selected_preview():
    """Show a quick data preview for paths already selected in the CM."""
    source = get_active_source()
    if source is None:
        return

    workflow = st.session_state.get(_WORKFLOW_KEY, "onboarding")

    if workflow == "onboarding":
        path = st.session_state.get(_SELECTED_PATH_KEY)
        if path:
            _show_path_preview(path, source, label="Onboarding Data Preview")
    else:
        bau_path = st.session_state.get(_BAU_PATH_KEY)
        test_path = st.session_state.get(_TEST_PATH_KEY)
        if bau_path or test_path:
            c1, c2 = st.columns(2)
            with c1:
                if bau_path:
                    _show_path_preview(bau_path, source, label="BAU Preview",
                                       discovery_key="_cm_bau_discovery")
            with c2:
                if test_path:
                    _show_path_preview(test_path, source, label="Test Preview",
                                       discovery_key="_cm_test_discovery")


def _show_path_preview(path, source, label="Data Preview", discovery_key="_cm_discovery"):
    """Detect file type via Discovery service and show a RAW preview for a selected path.

    The preview displays exactly what exists inside the source file — no parsing,
    no canonical conversion, no delimiter splitting, no flattening, no column mapping.
    This is intended only for understanding source data format.
    """
    with st.expander(label, expanded=False):
        file_paths = get_file_list(path, source=source)
        if not file_paths:
            st.caption(f"No files found at `{path}`")
            return

        try:
            discovery = detect_file(file_paths, source=source)
        except Exception:
            st.caption("Could not detect file type")
            return

        if discovery.error:
            st.caption(f"Detection error: {discovery.error}")
            return

        if not discovery.file_type:
            st.caption("Could not detect file type")
            return

        # Ensure file_paths are always carried in the discovery result
        discovery.file_paths = file_paths
        st.session_state[discovery_key] = discovery

        # RAW Preview — display raw lines without any parsing
        raw_lines = preview_raw_lines(file_paths, n_rows=10, source=source)
        if raw_lines:
            raw_preview_data = {"raw_record": raw_lines}
            st.dataframe(pl.DataFrame(raw_preview_data).to_pandas(), height=200)
            st.caption(f"{discovery.file_type} — {len(file_paths)} file(s) — {discovery.file_type} detected, delimiter={discovery.delimiter!r}")


def _navigate_to_path(browse_key, input_key):
    path = st.session_state.get(input_key, "").strip()
    if path:
        st.session_state[browse_key] = path


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
