import logging
import os
import stat as stat_module
import tempfile
from typing import List, BinaryIO, Optional

from dav_tool.datasource.base import IDataSource, DataSourceEntry, DataSourceError

logger = logging.getLogger(__name__)

try:
    import paramiko
except ImportError:
    paramiko = None


class SSHDataSource(IDataSource):

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: Optional[str] = None,
        key_file: Optional[str] = None,
        key_passphrase: Optional[str] = None,
        timeout: int = 15,
    ):
        if paramiko is None:
            raise DataSourceError(
                "paramiko is required for SSH connections. "
                "Install it with: pip install paramiko"
            )
        self.host = host
        self.port = port
        self.username = username
        self._password = password
        self.key_file = key_file
        self.key_passphrase = key_passphrase
        self.timeout = timeout
        self._client: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._cwd: str = "/"
        self._server_info: dict = {}

    def connect(self) -> bool:
        if paramiko is None:
            raise DataSourceError("paramiko not installed")
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self._password,
                key_filename=self.key_file,
                passphrase=self.key_passphrase,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            self._sftp = self._client.open_sftp()
            self._sftp.chdir("/")
            self._cwd = "/"
            self._gather_info()
            return True
        except Exception as e:
            self.disconnect()
            raise DataSourceError(f"SSH connection failed: {e}")

    def disconnect(self) -> None:
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    @property
    def is_connected(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.exec_command("echo connected", timeout=5)
            return True
        except Exception:
            return False

    def _gather_info(self) -> None:
        try:
            _, stdout, _ = self._client.exec_command(
                "uname -a; df -h / | tail -1; pwd", timeout=10
            )
            output = stdout.read().decode(errors="replace").strip()
            lines = output.split("\n")
            info = {"type": "ssh", "host": self.host, "port": self.port}
            if lines:
                info["platform"] = lines[0]
            if len(lines) > 1:
                info["disk"] = lines[1]
            self._server_info = info
        except Exception:
            self._server_info = {"type": "ssh", "host": self.host, "port": self.port}

    def _resolve(self, path: str) -> str:
        if not path:
            return self._cwd
        if path.startswith("/"):
            return path
        if self._cwd.endswith("/"):
            return self._cwd + path
        return self._cwd + "/" + path

    def list_directory(self, path: str) -> List[DataSourceEntry]:
        rpath = self._resolve(path)
        try:
            entries = []
            for attr in self._sftp.listdir_attr(rpath):
                is_dir = stat_module.S_ISDIR(attr.st_mode)
                entries.append(DataSourceEntry(
                    name=attr.filename,
                    path=rpath.rstrip("/") + "/" + attr.filename,
                    is_dir=is_dir,
                    size=attr.st_size if not is_dir else None,
                    modified=str(attr.st_mtime) if attr.st_mtime else None,
                ))
            return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))
        except Exception as e:
            raise DataSourceError(f"Cannot list directory {rpath}: {e}")

    def list_files(self, path: str) -> List[str]:
        rpath = self._resolve(path)
        try:
            attr = self._sftp.stat(rpath)
            if stat_module.S_ISREG(attr.st_mode):
                return [rpath]
            files = []
            for entry in self._sftp.listdir_attr(rpath):
                if stat_module.S_ISREG(entry.st_mode):
                    files.append(rpath.rstrip("/") + "/" + entry.filename)
            return sorted(files)
        except Exception as e:
            raise DataSourceError(f"Cannot list files at {rpath}: {e}")

    def read_sample(self, path: str, n: int = 100) -> str:
        rpath = self._resolve(path)
        try:
            with self._sftp.open(rpath, "r") as f:
                lines = []
                for _ in range(n):
                    try:
                        lines.append(next(f))
                    except StopIteration:
                        break
                return "".join(lines)
        except Exception as e:
            raise DataSourceError(f"Cannot read sample from {rpath}: {e}")

    def open_stream(self, path: str) -> BinaryIO:
        rpath = self._resolve(path)
        try:
            return self._sftp.open(rpath, "rb")
        except Exception as e:
            raise DataSourceError(f"Cannot open stream for {rpath}: {e}")

    def download_if_required(self, path: str) -> str:
        rpath = self._resolve(path)
        try:
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix="_" + os.path.basename(rpath)
            )
            self._sftp.get(rpath, tmp.name)
            logger.info("Downloaded %s to local temp %s", rpath, tmp.name)
            return tmp.name
        except Exception as e:
            raise DataSourceError(f"Cannot download {rpath}: {e}")

    def exists(self, path: str) -> bool:
        rpath = self._resolve(path)
        try:
            self._sftp.stat(rpath)
            return True
        except Exception:
            return False

    def stat(self, path: str) -> dict:
        rpath = self._resolve(path)
        try:
            attr = self._sftp.stat(rpath)
            return {
                "size": attr.st_size,
                "modified": attr.st_mtime,
                "is_dir": stat_module.S_ISDIR(attr.st_mode),
                "is_file": stat_module.S_ISREG(attr.st_mode),
            }
        except Exception as e:
            raise DataSourceError(f"Cannot stat {rpath}: {e}")

    def get_server_info(self) -> dict:
        return dict(self._server_info)

    def get_connection_string(self) -> str:
        return f"{self.username}@{self.host}:{self.port}"

    def navigate(self, path: str) -> str:
        rpath = self._resolve(path)
        attr = self._sftp.stat(rpath)
        if not stat_module.S_ISDIR(attr.st_mode):
            raise DataSourceError(f"Not a directory: {rpath}")
        self._cwd = rpath
        return self._cwd

    def getcwd(self) -> str:
        return self._cwd
