import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from transmission_rpc import Torrent

from cdm_client.database_adapter import DatabaseAdapter
from cdm_client.qbittorrent_adapter import QBitTorrentAdapter
from cdm_client.torrent_client_adapter_base import TorrentClientAdapterBase
from cdm_client.torrent_client_factory import (
    TorrentClientType,
    create_torrent_client_adapter,
)
from cdm_client.transmission_adapter import TransmissionAdapter


@dataclass
class TorrentMigrationItem:
    source_id: int
    hash_value: str
    name: str
    download_dir: str
    magnet_link: Optional[str]
    payload_bytes: Optional[bytes]


@dataclass
class MigrationStats:
    migrated: int = 0
    skipped_duplicate: int = 0
    failed_add: int = 0
    failed_lookup: int = 0
    failed_db_update: int = 0
    source_removed: int = 0


def _hash_to_id(torrent_hash: str) -> int:
    return int(torrent_hash[:8], 16)


def _normalize_hash(torrent_hash: str) -> str:
    return torrent_hash.lower()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate torrents between Transmission and qBittorrent."
    )
    parser.add_argument(
        "--source-type",
        required=True,
        choices=[
            TorrentClientType.TRANSMISSION.value,
            TorrentClientType.QBITTORRENT.value,
        ],
    )
    parser.add_argument(
        "--target-type",
        required=True,
        choices=[
            TorrentClientType.TRANSMISSION.value,
            TorrentClientType.QBITTORRENT.value,
        ],
    )

    parser.add_argument("--source-host")
    parser.add_argument("--source-port", type=int)
    parser.add_argument("--source-username")
    parser.add_argument("--source-password")

    parser.add_argument("--target-host")
    parser.add_argument("--target-port", type=int)
    parser.add_argument("--target-username")
    parser.add_argument("--target-password")

    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def _default_host() -> str:
    return "127.0.0.1"


def _default_port(client_type: TorrentClientType) -> int:
    if client_type == TorrentClientType.TRANSMISSION:
        return 9091
    return 8080


def _list_source_items(
    source_type: TorrentClientType, source_adapter: TorrentClientAdapterBase
) -> list[TorrentMigrationItem]:
    if source_type == TorrentClientType.TRANSMISSION:
        if not isinstance(source_adapter, TransmissionAdapter):
            raise TypeError("Invalid source adapter for Transmission")
        torrents = source_adapter._client.get_torrents()
        items: list[TorrentMigrationItem] = []
        for torrent in torrents:
            if not isinstance(torrent, Torrent):
                continue
            items.append(
                TorrentMigrationItem(
                    source_id=int(torrent.id),
                    hash_value=_normalize_hash(torrent.hashString),
                    name=torrent.name,
                    download_dir=torrent.download_dir,
                    magnet_link=torrent.magnet_link,
                    payload_bytes=None,
                )
            )
        return items

    if not isinstance(source_adapter, QBitTorrentAdapter):
        raise TypeError("Invalid source adapter for qBittorrent")
    items = []
    for torrent in source_adapter._client.torrents_info():
        torrent_hash = _normalize_hash(torrent.hash)
        payload_bytes: Optional[bytes] = None
        try:
            payload_bytes = source_adapter._client.torrents_export(
                torrent_hash=torrent_hash
            )
        except Exception:
            payload_bytes = None
        magnet_link: Optional[str] = None
        if hasattr(torrent, "magnet_uri"):
            magnet_candidate = getattr(torrent, "magnet_uri")
            if isinstance(magnet_candidate, str) and magnet_candidate:
                magnet_link = magnet_candidate
        items.append(
            TorrentMigrationItem(
                source_id=_hash_to_id(torrent_hash),
                hash_value=torrent_hash,
                name=torrent.name,
                download_dir=torrent.save_path,
                magnet_link=magnet_link,
                payload_bytes=payload_bytes,
            )
        )
    return items


def _build_target_hash_index(
    target_type: TorrentClientType, target_adapter: TorrentClientAdapterBase
) -> dict[str, int]:
    hash_to_id: dict[str, int] = {}
    if target_type == TorrentClientType.TRANSMISSION:
        if not isinstance(target_adapter, TransmissionAdapter):
            raise TypeError("Invalid target adapter for Transmission")
        for torrent in target_adapter._client.get_torrents():
            if not isinstance(torrent, Torrent):
                continue
            hash_to_id[_normalize_hash(torrent.hashString)] = int(torrent.id)
        return hash_to_id

    if not isinstance(target_adapter, QBitTorrentAdapter):
        raise TypeError("Invalid target adapter for qBittorrent")
    for torrent in target_adapter._client.torrents_info():
        torrent_hash = _normalize_hash(torrent.hash)
        hash_to_id[torrent_hash] = _hash_to_id(torrent_hash)
    return hash_to_id


def _add_to_target(
    item: TorrentMigrationItem,
    target_type: TorrentClientType,
    target_adapter: TorrentClientAdapterBase,
) -> Optional[int]:
    if target_type == TorrentClientType.TRANSMISSION:
        if not isinstance(target_adapter, TransmissionAdapter):
            raise TypeError("Invalid target adapter for Transmission")
        if item.payload_bytes:
            created = target_adapter.add_torrent(item.payload_bytes, item.download_dir)
            if created is None:
                return None
            return int(created.id)
        if item.magnet_link:
            created = target_adapter._client.add_torrent(
                item.magnet_link, download_dir=item.download_dir
            )
            return int(created.id)
        return None

    if not isinstance(target_adapter, QBitTorrentAdapter):
        raise TypeError("Invalid target adapter for qBittorrent")
    if item.payload_bytes:
        added = target_adapter.add_torrent(item.payload_bytes, item.download_dir)
        if added is None:
            return None
    elif item.magnet_link:
        target_adapter._client.torrents_add(
            urls=item.magnet_link, save_path=item.download_dir
        )
    else:
        return None
    for torrent in target_adapter._client.torrents_info():
        if _normalize_hash(torrent.hash) == item.hash_value:
            return _hash_to_id(item.hash_value)
    return None


def _reconcile_mapping(source_id: int, target_id: int) -> bool:
    with DatabaseAdapter() as db_adapter:
        tracker_id = db_adapter.get_tracker_id_by_torrent_id(source_id)
        logging.debug(
            "source_id=%s, target_id=%s, tracker_id=%s",
            source_id,
            target_id,
            tracker_id,
        )
        if tracker_id is None:
            return True
        return db_adapter.update_torrent_id(tracker_id, target_id)


def _parse_types_or_exit(
    source_type_raw: str,
    target_type_raw: str,
) -> tuple[TorrentClientType, TorrentClientType]:
    try:
        source_type = TorrentClientType(source_type_raw)
        target_type = TorrentClientType(target_type_raw)
    except ValueError as exc:
        raise SystemExit(2) from exc
    return source_type, target_type


def _validate_args_or_exit(
    args: argparse.Namespace,
    source_type: TorrentClientType,
    target_type: TorrentClientType,
) -> None:
    source_host = args.source_host or _default_host()
    target_host = args.target_host or _default_host()
    source_port = args.source_port or _default_port(source_type)
    target_port = args.target_port or _default_port(target_type)

    if source_type == target_type:
        raise SystemExit("Source and target types are identical.")

    same_endpoint = (
        source_type == target_type
        and source_host == target_host
        and source_port == target_port
    )
    if same_endpoint:
        raise SystemExit("Source and target endpoint are identical.")


def _print_summary(stats: MigrationStats, failures: list[str], dry_run: bool) -> None:
    mode_prefix = "DRY-RUN " if dry_run else ""
    print(f"{mode_prefix}summary:")
    print(f"  migrated: {stats.migrated}")
    print(f"  skipped_duplicate: {stats.skipped_duplicate}")
    print(f"  failed_add: {stats.failed_add}")
    print(f"  failed_lookup: {stats.failed_lookup}")
    print(f"  failed_db_update: {stats.failed_db_update}")
    print(f"  source_removed: {stats.source_removed}")
    if failures:
        print("failed items:")
        for failure in failures:
            print(f"  - {failure}")


def run_migration(args: argparse.Namespace) -> int:
    source_type, target_type = _parse_types_or_exit(args.source_type, args.target_type)
    _validate_args_or_exit(args, source_type, target_type)

    source_host = args.source_host or _default_host()
    target_host = args.target_host or _default_host()
    source_port = args.source_port or _default_port(source_type)
    target_port = args.target_port or _default_port(target_type)

    source_adapter = create_torrent_client_adapter(
        client_type=source_type,
        host=source_host,
        port=source_port,
        username=args.source_username,
        password=args.source_password,
    )
    target_adapter = create_torrent_client_adapter(
        client_type=target_type,
        host=target_host,
        port=target_port,
        username=args.target_username,
        password=args.target_password,
    )

    source_items = _list_source_items(source_type, source_adapter)
    target_hash_to_id = _build_target_hash_index(target_type, target_adapter)

    stats = MigrationStats()
    failures: list[str] = []
    had_failure = False

    for item in source_items:
        if item.hash_value in target_hash_to_id:
            stats.skipped_duplicate += 1
            target_id = target_hash_to_id[item.hash_value]
            if not args.dry_run:
                mapping_updated = _reconcile_mapping(item.source_id, target_id)
                if not mapping_updated:
                    stats.failed_db_update += 1
                    had_failure = True
                    failures.append(
                        f"{item.name} ({item.hash_value}) duplicate mapping update failed"
                    )
            continue

        if item.payload_bytes is None and not item.magnet_link:
            stats.failed_add += 1
            had_failure = True
            failures.append(
                f"{item.name} ({item.hash_value}) no transferable payload or magnet"
            )
            continue

        if args.dry_run:
            print(
                "DRY-RUN migrate:",
                item.name,
                item.hash_value,
                "->",
                target_type.value,
                f"path={item.download_dir}",
            )
            continue

        try:
            new_target_id = _add_to_target(item, target_type, target_adapter)
        except Exception as exc:
            stats.failed_add += 1
            had_failure = True
            failures.append(f"{item.name} ({item.hash_value}) add failed: {exc}")
            continue

        if new_target_id is None:
            stats.failed_lookup += 1
            had_failure = True
            failures.append(
                f"{item.name} ({item.hash_value}) added but target id lookup failed"
            )
            continue

        target_hash_to_id[item.hash_value] = new_target_id
        stats.migrated += 1

        if not _reconcile_mapping(item.source_id, new_target_id):
            stats.failed_db_update += 1
            had_failure = True
            failures.append(
                f"{item.name} ({item.hash_value}) mapping update failed "
                f"{item.source_id}->{new_target_id}"
            )
    _print_summary(stats, failures, args.dry_run)
    return 1 if had_failure else 0


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    try:
        exit_code = run_migration(args)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            raise
        parser.error(str(exc))
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)
