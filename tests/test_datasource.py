"""Tests for the data source layer."""
import os
import tempfile

import pytest

from dav_tool.datasource.base import DataSourceError, DataSourceEntry
from dav_tool.datasource.local import LocalDataSource
from dav_tool.datasource.manager import (
    connect_local, disconnect, get_active_source, is_connected, connect_ssh,
)


class TestLocalDataSource:

    def setup_method(self):
        self.source = LocalDataSource()

    def test_connect(self):
        assert self.source.connect() is True

    def test_is_connected(self):
        assert self.source.is_connected is True

    def test_disconnect_noop(self):
        self.source.disconnect()

    def test_exists_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert self.source.exists(str(f)) is True
        assert self.source.exists(str(tmp_path / "nope.txt")) is False

    def test_exists_directory(self, tmp_path):
        assert self.source.exists(str(tmp_path)) is True

    def test_list_files_single_file(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3")
        files = self.source.list_files(str(f))
        assert files == [str(f)]

    def test_list_files_directory(self, tmp_path):
        (tmp_path / "a.csv").write_text("x")
        (tmp_path / "b.csv").write_text("y")
        files = self.source.list_files(str(tmp_path))
        assert len(files) == 2
        assert all(f.endswith(".csv") for f in files)

    def test_list_files_missing_path(self):
        with pytest.raises(DataSourceError):
            self.source.list_files("/nonexistent/path")

    def test_list_directory(self, tmp_path):
        (tmp_path / "file1.txt").write_text("hello")
        (tmp_path / "sub").mkdir()
        entries = self.source.list_directory(str(tmp_path))
        names = [e.name for e in entries]
        assert "file1.txt" in names
        assert "sub" in names
        for e in entries:
            assert isinstance(e, DataSourceEntry)
            assert e.path.startswith(str(tmp_path))

    def test_list_directory_sorts_dirs_first(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "z_dir").mkdir()
        entries = self.source.list_directory(str(tmp_path))
        assert entries[0].is_dir is True

    def test_list_directory_missing(self):
        with pytest.raises(DataSourceError):
            self.source.list_directory("/nonexistent")

    def test_read_sample(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("line1\nline2\nline3\nline4\nline5\n")
        sample = self.source.read_sample(str(f), n=3)
        assert sample == "line1\nline2\nline3\n"
        assert len(sample.split("\n")) == 4  # 3 lines + trailing

    def test_read_sample_less_than_n(self, tmp_path):
        f = tmp_path / "short.txt"
        f.write_text("only\n")
        sample = self.source.read_sample(str(f), n=100)
        assert sample == "only\n"

    def test_read_sample_missing_file(self):
        with pytest.raises(DataSourceError):
            self.source.read_sample("/missing.txt")

    def test_download_if_required_returns_same_path(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a,b,c")
        result = self.source.download_if_required(str(f))
        assert result == str(f)

    def test_stat_file(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text("data")
        info = self.source.stat(str(f))
        assert info["is_file"] is True
        assert info["is_dir"] is False
        assert info["size"] == 4

    def test_stat_directory(self, tmp_path):
        info = self.source.stat(str(tmp_path))
        assert info["is_dir"] is True
        assert info["is_file"] is False

    def test_stat_missing(self):
        with pytest.raises(DataSourceError):
            self.source.stat("/missing")

    def test_open_stream(self, tmp_path):
        f = tmp_path / "stream_test.bin"
        f.write_bytes(b"binary data")
        stream = self.source.open_stream(str(f))
        assert stream.read() == b"binary data"
        stream.close()

    def test_get_server_info(self):
        info = self.source.get_server_info()
        assert info["type"] == "local"
        assert "platform" in info

    def test_get_connection_string(self):
        assert self.source.get_connection_string() == "Local File System"


class TestConnectionManager:

    def teardown_method(self):
        disconnect()

    def test_connect_local(self):
        source = connect_local()
        assert source is not None
        assert is_connected() is True

    def test_get_active_source(self):
        connect_local()
        assert get_active_source() is not None

    def test_disconnect(self):
        connect_local()
        disconnect()
        assert is_connected() is False
        assert get_active_source() is None

    def test_double_disconnect_safe(self):
        disconnect()
        disconnect()

    def test_connect_ssh_missing_paramiko(self, monkeypatch):
        monkeypatch.setattr("dav_tool.datasource.ssh.paramiko", None)
        with pytest.raises(DataSourceError, match="paramiko is required"):
            connect_ssh(host="test", username="user", password="pass")

    def test_connect_ssh_params(self, monkeypatch):
        import types
        mock_paramiko = types.ModuleType("paramiko")

        class FakeSFTP:
            def chdir(self, path): pass
            def listdir_attr(self, path): return []
            def stat(self, path): return type("Attr", (), {"st_mode": 0o644, "st_size": 0, "st_mtime": 0})()

        class FakeClient:
            def set_missing_host_key_policy(self, policy): pass
            def connect(self, **kw): raise Exception("Connection refused")

        mock_paramiko.SSHClient = lambda: FakeClient()
        mock_paramiko.AutoAddPolicy = type("AutoAddPolicy", (), {})
        mock_paramiko.SFTPClient = FakeSFTP

        monkeypatch.setattr("dav_tool.datasource.ssh.paramiko", mock_paramiko)
        with pytest.raises(DataSourceError, match="SSH connection failed"):
            connect_ssh(host="badhost", username="user", password="pass")
