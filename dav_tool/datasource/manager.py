"""Connection Manager — singleton that manages the active data source."""
import logging
from dataclasses import dataclass, field
from typing import Optional

from dav_tool.datasource.base import IDataSource, DataSourceError
from dav_tool.datasource.local import LocalDataSource
from dav_tool.datasource.ssh import SSHDataSource

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    type: str = "local"
    host: str = ""
    port: int = 22
    username: str = ""
    auth_method: str = "password"
    key_file: str = ""


_ACTIVE_SOURCE: Optional[IDataSource] = None
_ACTIVE_CONFIG: Optional[ConnectionConfig] = None


def get_active_source() -> Optional[IDataSource]:
    return _ACTIVE_SOURCE


def get_active_config() -> Optional[ConnectionConfig]:
    return _ACTIVE_CONFIG


def is_connected() -> bool:
    if _ACTIVE_SOURCE is None:
        return False
    try:
        return _ACTIVE_SOURCE.is_connected
    except Exception:
        return False


def connect_local() -> IDataSource:
    global _ACTIVE_SOURCE, _ACTIVE_CONFIG
    disconnect()
    source = LocalDataSource()
    source.connect()
    _ACTIVE_SOURCE = source
    _ACTIVE_CONFIG = ConnectionConfig(type="local")
    logger.info("Connected to local file system")
    return source


def connect_ssh(
    host: str,
    port: int = 22,
    username: str = "",
    password: Optional[str] = None,
    key_file: Optional[str] = None,
    key_passphrase: Optional[str] = None,
    timeout: int = 15,
) -> IDataSource:
    global _ACTIVE_SOURCE, _ACTIVE_CONFIG
    disconnect()
    source = SSHDataSource(
        host=host,
        port=port,
        username=username,
        password=password,
        key_file=key_file,
        key_passphrase=key_passphrase,
        timeout=timeout,
    )
    source.connect()
    _ACTIVE_SOURCE = source
    _ACTIVE_CONFIG = ConnectionConfig(
        type="ssh",
        host=host,
        port=port,
        username=username,
        auth_method="key" if key_file else "password",
        key_file=key_file or "",
    )
    logger.info("Connected to SSH: %s@%s:%d", username, host, port)
    return source


def disconnect() -> None:
    global _ACTIVE_SOURCE, _ACTIVE_CONFIG
    if _ACTIVE_SOURCE is not None:
        try:
            _ACTIVE_SOURCE.disconnect()
        except Exception as e:
            logger.warning("Error during disconnect: %s", e)
        _ACTIVE_SOURCE = None
        _ACTIVE_CONFIG = None
        logger.info("Disconnected")
