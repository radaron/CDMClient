from enum import Enum
from typing import Any, Optional

from cdm_client.qbittorrent_adapter import QBitTorrentAdapter
from cdm_client.torrent_client_adapter_base import TorrentClientAdapterBase
from cdm_client.transmission_adapter import TransmissionAdapter


class TorrentClientType(Enum):
    TRANSMISSION = "transmission"
    QBITTORRENT = "qbittorrent"

    @classmethod
    def get_enum_from_value(cls, value: str) -> "TorrentClientType":
        for member in cls:
            if member.value == value:
                return member
        return cls.TRANSMISSION


def _filter_none(**kwargs: Any) -> dict:
    """Filter out None values from kwargs."""
    return {k: v for k, v in kwargs.items() if v is not None}


def create_torrent_client_adapter(
    client_type: TorrentClientType,
    username: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> TorrentClientAdapterBase:
    kwargs = _filter_none(username=username, password=password, host=host, port=port)

    if client_type == TorrentClientType.TRANSMISSION:
        return TransmissionAdapter(**kwargs)
    if client_type == TorrentClientType.QBITTORRENT:
        return QBitTorrentAdapter(**kwargs)
    else:
        raise ValueError(f"Unsupported torrent client type: {client_type}")
