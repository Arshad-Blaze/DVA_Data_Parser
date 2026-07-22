import glob
import logging
import os
import platform
from typing import List, BinaryIO

from dav_tool.datasource.base import IDataSource, DataSourceEntry, DataSourceError

logger = logging.getLogger(__name__)


class LocalDataSource(IDataSource):

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def supports_direct_path(self) -> bool:
        return True

    def list_directory(self, path: str) -> List[DataSourceEntry]:
        path = os.path.abspath(os.path.normpath(path))
        if not os.path.exists(path):
            raise DataSourceError(f"Path does not exist: {path}")
        entries = []
        try:
            for name in os.listdir(path):
                full = os.path.join(path, name)
                try:
                    st = os.stat(full)
                except OSError as e:
                    logger.debug("Could not stat %s: %s", full, e)
                    st = None
                entries.append(DataSourceEntry(
                    name=name,
                    path=full,
                    is_dir=os.path.isdir(full),
                    size=st.st_size if st else None,
                    modified=str(st.st_mtime) if st else None,
                ))
        except OSError as e:
            raise DataSourceError(f"Cannot list directory {path}: {e}")
        return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))

    def list_files(self, path: str) -> List[str]:
        path = os.path.abspath(os.path.normpath(path))
        if os.path.isfile(path):
            return [path]
        elif os.path.isdir(path):
            return sorted(glob.glob(os.path.join(path, "*")))
        raise DataSourceError(f"Path not found: {path}")

    def read_sample(self, path: str, n: int = 100) -> str:
        path = os.path.abspath(os.path.normpath(path))
        try:
            with open(path, "r", errors="ignore") as f:
                lines = []
                for _ in range(n):
                    try:
                        lines.append(next(f))
                    except StopIteration:
                        break
                return "".join(lines)
        except OSError as e:
            raise DataSourceError(f"Cannot read sample from {path}: {e}")

    def open_stream(self, path: str) -> BinaryIO:
        path = os.path.abspath(os.path.normpath(path))
        try:
            return open(path, "rb")
        except OSError as e:
            raise DataSourceError(f"Cannot open {path}: {e}")

    def download_if_required(self, path: str) -> str:
        return os.path.abspath(os.path.normpath(path))

    def exists(self, path: str) -> bool:
        return os.path.exists(os.path.abspath(os.path.normpath(path)))

    def stat(self, path: str) -> dict:
        path = os.path.abspath(os.path.normpath(path))
        try:
            st = os.stat(path)
            return {
                "size": st.st_size,
                "modified": st.st_mtime,
                "is_dir": os.path.isdir(path),
                "is_file": os.path.isfile(path),
            }
        except OSError as e:
            raise DataSourceError(f"Cannot stat {path}: {e}")

    def get_server_info(self) -> dict:
        return {
            "type": "local",
            "platform": platform.system(),
            "hostname": platform.node(),
        }

    def get_connection_string(self) -> str:
        return "Local File System"
