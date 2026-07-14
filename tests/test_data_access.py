"""Tests for DataAccessStrategy module."""

import os
import tempfile
import threading
from unittest.mock import Mock, patch, PropertyMock

import pytest

from dav_tool.datasource.base import IDataSource
from dav_tool.workflow.data_access import (
    AccessStrategy, DataAccessor, DataAccessError,
    wrap_source, register_accessor, cleanup_all,
    _available_ram_mb, _available_disk_mb,
)


# ── Helpers ────────────────────────────────────────────────────

class _MockSource(IDataSource):
    """Minimal mock IDataSource that returns local temp files."""

    def __init__(self, direct_path=False, fail_count=0):
        self._connected = True
        self._direct_path = direct_path
        self._fail_count = fail_count
        self._call_count = 0
        self._temp_dir = tempfile.mkdtemp(prefix="das_test_")

    def connect(self):
        return True

    def disconnect(self):
        self._connected = False

    @property
    def is_connected(self):
        return self._connected

    @property
    def supports_direct_path(self):
        return self._direct_path

    def list_directory(self, path):
        return []

    def list_files(self, path):
        return [path]

    def read_sample(self, path, n=100):
        return ""

    def open_stream(self, path):
        self._call_count += 1
        if self._fail_count and self._call_count <= self._fail_count:
            raise ConnectionError(f"Simulated failure #{self._call_count}")
        return open(path, "rb")

    def download_if_required(self, path):
        self._call_count += 1
        if self._fail_count and self._call_count <= self._fail_count:
            raise ConnectionError(f"Simulated failure #{self._call_count}")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_test")
        tmp.write(b"mock,data\n1,2\n3,4\n")
        tmp.close()
        return tmp.name

    def exists(self, path):
        return True

    def stat(self, path):
        return {"size": 1024, "is_file": True, "is_dir": False}

    def get_server_info(self):
        return {}

    def get_connection_string(self):
        return "mock"

    def cleanup(self):
        import shutil
        shutil.rmtree(self._temp_dir, ignore_errors=True)


# ── Tests ──────────────────────────────────────────────────────

class TestAccessStrategySelection:
    """Strategy selection logic under various resource profiles."""

    def test_local_source_uses_direct_stream(self):
        source = _MockSource(direct_path=True)
        da = DataAccessor(source)
        paths = da.resolve(["/local/file.csv"])
        assert da.strategy == AccessStrategy.DIRECT_STREAM
        assert paths == ["/local/file.csv"]
        assert "direct_stream" in da.decision

    def test_remote_low_ram_uses_chunk_stream(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 100)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        da.resolve(["/remote/file.csv"])
        assert da.strategy == AccessStrategy.CHUNK_STREAM

    def test_remote_small_files_use_batch_copy(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        da.resolve(["/remote/small.csv"])
        assert da.strategy == AccessStrategy.BATCH_COPY

    def test_remote_medium_files_use_sequential_copy(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)

        with patch.object(source, "stat", return_value={"size": 200 * 1024 * 1024}):
            da = DataAccessor(source)
            da.resolve(["/remote/medium.csv"])
            assert da.strategy == AccessStrategy.SEQUENTIAL_COPY

    def test_remote_large_files_use_chunk_stream(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)

        with patch.object(source, "stat", return_value={"size": 1024 * 1024 * 1024}):
            da = DataAccessor(source)
            da.resolve(["/remote/large.csv"])
            assert da.strategy == AccessStrategy.CHUNK_STREAM

    def test_low_disk_forces_chunk_stream(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 50)
        source = _MockSource(direct_path=False)
        with patch.object(source, "stat", return_value={"size": 100 * 1024 * 1024}):
            da = DataAccessor(source)
            da.resolve(["/remote/file.csv"])
            assert da.strategy == AccessStrategy.CHUNK_STREAM


class TestBatchCopy:
    """BATCH_COPY downloads all files and returns local paths."""

    def test_batch_download_resolves_paths(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        paths = da.resolve(["/remote/a.csv", "/remote/b.csv"])
        assert da.strategy == AccessStrategy.BATCH_COPY
        assert len(paths) == 2
        for p in paths:
            assert os.path.exists(p)
            assert os.path.getsize(p) > 0

    def test_batch_copy_supports_direct_path(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        da.resolve(["/remote/a.csv"])
        assert da.supports_direct_path is True

    def test_cleanup_removes_batch_files(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        paths = da.resolve(["/remote/clean.csv"])
        assert all(os.path.exists(p) for p in paths)
        da.cleanup()
        assert all(not os.path.exists(p) for p in paths)


class TestSequentialCopy:
    """SEQUENTIAL_COPY downloads one file at a time via open_stream."""

    def test_open_stream_downloads_and_opens(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)

        with patch.object(source, "stat", return_value={"size": 200 * 1024 * 1024}):
            da = DataAccessor(source)
            da.resolve(["/remote/seq.csv"])
            assert da.strategy == AccessStrategy.SEQUENTIAL_COPY
            stream = da.open_stream("/remote/seq.csv")
            data = stream.read()
            assert b"mock,data" in data
            stream.close()


class TestChunkStream:
    """CHUNK_STREAM delegates to source.open_stream with retry."""

    def test_open_stream_delegates(self):
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        da._strategy = AccessStrategy.CHUNK_STREAM
        # Create local file for open_stream
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"testdata")
        tmp.close()
        stream = da.open_stream(tmp.name)
        assert stream.read() == b"testdata"
        stream.close()
        os.unlink(tmp.name)

    def test_stream_failure_retries_then_raises(self):
        source = _MockSource(direct_path=False, fail_count=10)
        da = DataAccessor(source)
        da._strategy = AccessStrategy.CHUNK_STREAM
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"data")
        tmp.close()
        os.unlink(tmp.name)
        with pytest.raises(DataAccessError):
            da.open_stream("/nonexistent/file.csv")


class TestRetryLogic:
    """Retry decorator handles transient failures."""

    def test_retry_succeeds_after_transient_failure(self):
        source = _MockSource(direct_path=False, fail_count=2)
        da = DataAccessor(source)
        da._strategy = AccessStrategy.CHUNK_STREAM
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"data")
        tmp.close()
        stream = da.open_stream(tmp.name)
        assert stream.read() == b"data"
        stream.close()
        os.unlink(tmp.name)

    def test_download_if_required_retries(self):
        source = _MockSource(direct_path=False, fail_count=1)
        da = DataAccessor(source)
        da._strategy = AccessStrategy.CHUNK_STREAM
        path = da.download_if_required("/remote/retry.csv")
        assert os.path.exists(path)
        os.unlink(path)


class TestCleanup:
    """Cleanup lifecycle management."""

    def test_cleanup_is_idempotent(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        da.resolve(["/remote/safe.csv"])
        da.cleanup()
        da.cleanup()

    def test_closed_accessor_raises_on_resolve(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        da.cleanup()
        with pytest.raises(DataAccessError, match="closed"):
            da.resolve(["/remote/x.csv"])

    def test_register_and_cleanup_all(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=False)
        da = DataAccessor(source)
        da.resolve(["/remote/reg.csv"])
        register_accessor(da)
        cleanup_all()
        # verify cleanup ran without error


class TestWrapSource:
    """Convenience wrap_source helper."""

    def test_wrap_source_with_none_returns_none(self):
        result, paths = wrap_source(None, ["/a.csv"])
        assert result is None
        assert paths == ["/a.csv"]

    def test_wrap_source_returns_accessor(self, monkeypatch):
        monkeypatch.setattr("dav_tool.workflow.data_access._available_ram_mb", lambda: 4096)
        monkeypatch.setattr("dav_tool.workflow.data_access._available_disk_mb", lambda: 10000)
        source = _MockSource(direct_path=True)
        result, paths = wrap_source(source, ["/a.csv"])
        assert isinstance(result, DataAccessor)
        assert result.strategy == AccessStrategy.DIRECT_STREAM


class TestResourceChecks:
    """System resource utilities."""

    def test_ram_mb_returns_positive(self):
        ram = _available_ram_mb()
        assert ram > 0

    def test_disk_mb_returns_positive(self):
        disk = _available_disk_mb()
        assert disk > 0


class TestDirectStream:
    """DIRECT_STREAM for local sources."""

    def test_open_stream_opens_local_file(self):
        source = _MockSource(direct_path=True)
        da = DataAccessor(source)
        da.resolve(["/dev/null"])
        da._strategy = AccessStrategy.DIRECT_STREAM
        stream = da.open_stream("/dev/null")
        assert stream is not None
        stream.close()

    def test_download_if_required_returns_same_path(self):
        source = _MockSource(direct_path=True)
        da = DataAccessor(source)
        result = da.download_if_required("/local/path.csv")
        assert result == "/local/path.csv"

    def test_supports_direct_path_true_for_local(self):
        source = _MockSource(direct_path=True)
        da = DataAccessor(source)
        da.resolve(["/local/x.csv"])
        assert da.supports_direct_path is True
