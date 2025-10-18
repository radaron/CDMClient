from abc import ABC, abstractmethod
from typing import Any


class TorrentClientAdapterBase(ABC):
    @abstractmethod
    def __init__(self) -> None: ...

    @abstractmethod
    def get_status(self) -> list[dict]: ...

    @abstractmethod
    def get_status_by_id(self, torrent_id: int) -> dict: ...

    @abstractmethod
    def add_torrent(self, torrent: bytes, download_dir: str) -> Any: ...

    @abstractmethod
    def pause_torrent(self, torrent_id: int) -> None: ...

    @abstractmethod
    def resume_torrent(self, torrent_id: int) -> None: ...

    @abstractmethod
    def remove_torrent(self, torrent_id: int) -> None: ...
