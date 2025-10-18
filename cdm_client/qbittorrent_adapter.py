import logging
from time import sleep
from typing import Optional

from qbittorrentapi import Client, TorrentDictionary, TorrentState

from cdm_client.torrent_client_adapter_base import TorrentClientAdapterBase


class TorrentWrapper:
    def __init__(self, torrent_dict: TorrentDictionary) -> None:
        self._torrent_dict = torrent_dict

    @property
    def id(self) -> int:
        return int(self._torrent_dict.hash[:8], 16)


class QBitTorrentAdapter(TorrentClientAdapterBase):
    def __init__(
        self,
        username: Optional[str] = "admin",
        password: Optional[str] = "adminadmin",
        host: str = "127.0.0.1",
        port: int = 8080,
    ) -> None:
        self._client = Client(
            username=username, password=password, host=host, port=port
        )
        self._logger = logging.getLogger("cdm-client")

    def _hash_to_id(self, torrent_hash: str) -> int:
        """Convert torrent hash to integer ID using Python's hash function."""
        return int(torrent_hash[:8], 16)

    def _map_status(self, qbittorrent_status: TorrentState) -> str:
        status_mapping = {
            TorrentState.ERROR: "stopped",
            TorrentState.MISSING_FILES: "stopped",
            TorrentState.UPLOADING: "seeding",
            TorrentState.PAUSED_UPLOAD: "stopped",
            TorrentState.STOPPED_UPLOAD: "stopped",
            TorrentState.QUEUED_UPLOAD: "stopped",
            TorrentState.STALLED_UPLOAD: "seeding",
            TorrentState.CHECKING_UPLOAD: "checking",
            TorrentState.FORCED_UPLOAD: "seeding",
            TorrentState.ALLOCATING: "checking",
            TorrentState.DOWNLOADING: "downloading",
            TorrentState.METADATA_DOWNLOAD: "downloading",
            TorrentState.FORCED_METADATA_DOWNLOAD: "downloading",
            TorrentState.PAUSED_DOWNLOAD: "stopped",
            TorrentState.STOPPED_DOWNLOAD: "stopped",
            TorrentState.QUEUED_DOWNLOAD: "download pending",
            TorrentState.FORCED_DOWNLOAD: "downloading",
            TorrentState.STALLED_DOWNLOAD: "stopped",
            TorrentState.CHECKING_DOWNLOAD: "checking",
            TorrentState.CHECKING_RESUME_DATA: "checking",
            TorrentState.MOVING: "checking",
            TorrentState.UNKNOWN: "unknown",
        }
        return status_mapping.get(qbittorrent_status, "unknown")

    def _get_status_dict(self, torrent: TorrentDictionary) -> dict:
        return {
            "id": self._hash_to_id(torrent.hash),
            "name": torrent.name,
            "status": self._map_status(torrent.state),
            "progress": int(torrent.progress * 100),
            "downloadDir": torrent.save_path,
            "addedDate": torrent.added_on,
            "totalSize": torrent.size,
            "eta": torrent.eta,
        }

    def get_status(self) -> list[dict]:
        torrents = self._client.torrents_info()
        status = []
        for torrent in torrents:
            status.append(self._get_status_dict(torrent))
        self._logger.info("Retrieved status of %s torrents", len(status))
        return status

    def get_status_by_id(self, torrent_id: int) -> dict:
        return self._get_status_dict(self._get_torrent_by_id(torrent_id))

    def _get_torrent_by_id(self, torrent_id: int) -> TorrentDictionary:
        torrents = self._client.torrents_info()
        for torrent in torrents:
            if self._hash_to_id(torrent.hash) == torrent_id:
                return torrent
        raise ValueError(f"Torrent with ID {torrent_id} not found")

    def _get_latest_torrent(self) -> Optional[TorrentDictionary]:
        torrents = self._client.torrents_info(sort="added_on")
        self._logger.info(
            "Current torrents: %s", [(t.name, t.added_on) for t in torrents]
        )
        return torrents[-1] if len(torrents) > 0 else None

    def add_torrent(
        self, torrent: bytes, download_dir: str
    ) -> Optional[TorrentWrapper]:
        states_before = self._client.torrents_info()
        self._client.torrents_add(
            torrent_files=torrent, save_path=download_dir, is_sequential_download=True
        )
        for _ in range(20):  # Wait up to 10 seconds
            if self._client.torrents_info() == states_before:
                sleep(0.5)
            else:
                break
        if self._client.torrents_info() == states_before:
            return None
        if last_torrent := self._get_latest_torrent():
            self._logger.info(
                "Added torrent: %s to %s", last_torrent.name, download_dir
            )
            return TorrentWrapper(last_torrent)
        return None

    def pause_torrent(self, torrent_id: int) -> None:
        torrent = self._get_torrent_by_id(torrent_id)
        self._client.torrents_pause(torrent_hashes=[torrent.hash])

    def resume_torrent(self, torrent_id: int) -> None:
        torrent = self._get_torrent_by_id(torrent_id)
        self._client.torrents_resume(torrent_hashes=[torrent.hash])

    def remove_torrent(self, torrent_id: int) -> None:
        torrent = self._get_torrent_by_id(torrent_id)
        self._client.torrents_delete(torrent_hashes=[torrent.hash], delete_files=True)
