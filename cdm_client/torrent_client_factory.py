from enum import Enum
from typing import Optional, TypedDict

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


class AdapterKwargs(TypedDict, total=False):
    username: str
    password: str
    host: str
    port: int


def _filter_none(
    username: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> AdapterKwargs:
    kwargs: AdapterKwargs = {}
    if username is not None:
        kwargs["username"] = username
    if password is not None:
        kwargs["password"] = password
    if host is not None:
        kwargs["host"] = host
    if port is not None:
        kwargs["port"] = port
    return kwargs


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
