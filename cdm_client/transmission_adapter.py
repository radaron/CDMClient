import logging
from typing import Optional

from transmission_rpc import Client, Torrent

from cdm_client.torrent_client_adapter_base import TorrentClientAdapterBase


class TransmissionAdapter(TorrentClientAdapterBase):
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 9091,
    ) -> None:
        self._client = Client(
            username=username, password=password, host=host, port=port
        )
        # The sequential download setting is not working somehow :(
        self._client.set_session(rename_partial_files=False, sequential_download=True)
        self._logger = logging.getLogger("cdm-client")

    def _get_status_dict(self, torrent: Torrent) -> dict:
        return {
            "id": torrent.id,
            "name": torrent.name,
            "status": torrent.status.value,
            "progress": int(torrent.progress),
            "downloadDir": torrent.download_dir,
            "addedDate": torrent.added_date.timestamp(),
            "totalSize": torrent.total_size,
            "eta": torrent.eta.total_seconds() if torrent.eta else None,
        }

    def get_status(self) -> list[dict]:
        torrents = self._client.get_torrents()
        status = []
        for torrent in torrents:
            status.append(self._get_status_dict(torrent))
        self._logger.info("Retrieved status of %s torrents", len(status))
        return status

    def get_status_by_id(self, torrent_id: int) -> dict:
        torrent = self._client.get_torrent(torrent_id)
        return self._get_status_dict(torrent)

    def add_torrent(self, torrent: bytes, download_dir: str) -> Torrent:
        return self._client.add_torrent(torrent, download_dir=download_dir)

    def pause_torrent(self, torrent_id: int) -> None:
        return self._client.stop_torrent(ids=[torrent_id])

    def resume_torrent(self, torrent_id: int) -> None:
        return self._client.start_torrent(ids=[torrent_id])

    def remove_torrent(self, torrent_id: int) -> None:
        return self._client.remove_torrent(ids=[torrent_id], delete_data=True)
