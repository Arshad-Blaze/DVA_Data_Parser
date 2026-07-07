"""Connection Manager UI — top-level component for managing data sources."""
import logging
import os

import streamlit as st

from dav_tool.datasource.base import DataSourceError
from dav_tool.datasource.manager import (
    connect_local, connect_ssh, disconnect,
    get_active_source, is_connected, get_active_config,
)
from dav_tool._observability import log_phase

logger = logging.getLogger(__name__)

_CONN_KEY = "_cm_connected"
_CONN_TYPE_KEY = "_cm_conn_type"
_BROWSE_PATH_KEY = "_cm_browse_path"
_BROWSE_HISTORY_KEY = "_cm_browse_history"
_SEARCH_KEY = "_cm_search"


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


def render_connection_manager():
    _init_state()

    with st.container(border=True):
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
            _render_file_browser()


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


def _render_file_browser():
    source = get_active_source()
    if source is None:
        return

    st.markdown("### Remote File Browser")

    nav_cols = st.columns([1, 1, 4, 1])
    with nav_cols[0]:
        if st.button("← Back", use_container_width=True):
            history = st.session_state[_BROWSE_HISTORY_KEY]
            if history:
                st.session_state[_BROWSE_PATH_KEY] = history.pop()
                st.rerun()
    with nav_cols[1]:
        if st.button("↻ Refresh", use_container_width=True):
            st.rerun()
    with nav_cols[2]:
        st.text_input(
            "Path", value=st.session_state[_BROWSE_PATH_KEY],
            key="cm_browse_input",
            label_visibility="collapsed",
            on_change=_navigate_to_path,
        )
    with nav_cols[3]:
        st.text_input(
            "Search", value="", key=_SEARCH_KEY,
            placeholder="Filter...",
            label_visibility="collapsed",
        )

    try:
        entries = source.list_directory(st.session_state[_BROWSE_PATH_KEY])
    except DataSourceError as e:
        st.error(str(e))
        return

    search = st.session_state.get(_SEARCH_KEY, "").lower()
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
            if st.button(label, key=f"browse_{entry.path}", use_container_width=True):
                history = st.session_state[_BROWSE_HISTORY_KEY]
                history.append(st.session_state[_BROWSE_PATH_KEY])
                st.session_state[_BROWSE_PATH_KEY] = entry.path
                st.rerun()
        else:
            st.markdown(f"{label}")


def _navigate_to_path():
    path = st.session_state.get("cm_browse_input", "").strip()
    if path:
        st.session_state[_BROWSE_PATH_KEY] = path


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
