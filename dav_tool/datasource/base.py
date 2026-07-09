from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, BinaryIO


class DataSourceError(Exception):
    """Base exception for data source operations."""


@dataclass
class DataSourceEntry:
    name: str
    path: str
    is_dir: bool = False
    size: Optional[int] = None
    modified: Optional[str] = None


class IDataSource(ABC):

    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    def supports_direct_path(self) -> bool:
        """Whether files can be accessed directly via local file paths.
        
        Local filesystems return True; remote sources (SSH, cloud) return False.
        When True, the Aggregation Engine can use Polars' native streaming
        instead of the chunked reader to get better performance.
        """
        return False

    @abstractmethod
    def list_directory(self, path: str) -> List[DataSourceEntry]:
        ...

    @abstractmethod
    def list_files(self, path: str) -> List[str]:
        ...

    @abstractmethod
    def read_sample(self, path: str, n: int = 100) -> str:
        ...

    @abstractmethod
    def open_stream(self, path: str) -> BinaryIO:
        ...

    @abstractmethod
    def download_if_required(self, path: str) -> str:
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        ...

    @abstractmethod
    def stat(self, path: str) -> dict:
        ...

    @abstractmethod
    def get_server_info(self) -> dict:
        ...

    @abstractmethod
    def get_connection_string(self) -> str:
        ...
