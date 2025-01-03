import logging
from typing import Optional
from transmission_rpc import Client


class TransmissionAdapter:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None) -> None:
        self._client = Client(username=username, password=password)
        self._logger = logging.getLogger("cdm-client")

    def get_status(self) -> list[dict]:
        torrents = self._client.get_torrents()
        status = []
        for torrent in torrents:
            status.append(
                {
                    "id": torrent.id,
                    "name": torrent.name,
                    "status": torrent.status.value,
                    "progress": int(torrent.progress),
                    "downloadDir": torrent.download_dir,
                    "addedDate": torrent.added_date.timestamp(),
                    "totalSize": torrent.total_size,
                    "eta": torrent.eta.total_seconds() if torrent.eta else None,
                }
            )
        self._logger.info("Retrieved status of %s torrents", len(status))
        return status

    def add_torrent(self, torrent: bytes, download_dir: str) -> None:
        self._client.add_torrent(torrent, download_dir=download_dir)
