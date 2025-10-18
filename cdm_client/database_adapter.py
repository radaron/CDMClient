import os
from types import TracebackType
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class DownloadTorrentMapping(Base):  # type: ignore[valid-type,misc]
    __tablename__ = "download_torrent_mapping"

    tracker_id: int = Column(Integer, primary_key=True)  # type: ignore[assignment]
    torrent_id: int = Column(Integer, nullable=False)  # type: ignore[assignment]

    __table_args__ = (
        UniqueConstraint("tracker_id", "torrent_id", name="unique_download_torrent"),
    )


class DatabaseAdapter:
    DATABASE_PATH = os.path.join(
        os.path.expanduser("~"), ".local", "share", "cdm_client", "cdm_client.db"
    )

    def __init__(self) -> None:
        os.makedirs(os.path.dirname(self.DATABASE_PATH), exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.DATABASE_PATH}")
        Base.metadata.create_all(self.engine)

    def __enter__(self) -> "DatabaseAdapter":
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.session.close()

    def create_or_update_download_torrent_mapping(
        self, tracker_id: int, torrent_id: int
    ) -> bool:
        if self.get_torrent_id_by_tracker_id(tracker_id):
            return self.update_torrent_id(tracker_id, torrent_id)
        try:
            mapping = DownloadTorrentMapping(
                tracker_id=tracker_id, torrent_id=torrent_id
            )
            self.session.add(mapping)
            self.session.commit()
            return True
        except IntegrityError:
            self.session.rollback()
            return False
        except Exception:
            self.session.rollback()
            return False

    def get_torrent_id_by_tracker_id(self, tracker_id: int) -> Optional[int]:
        mapping = (
            self.session.query(DownloadTorrentMapping)
            .filter_by(tracker_id=tracker_id)
            .first()
        )
        return mapping.torrent_id if mapping else None

    def update_torrent_id(self, tracker_id: int, new_torrent_id: int) -> bool:
        mapping = (
            self.session.query(DownloadTorrentMapping)
            .filter_by(tracker_id=tracker_id)
            .first()
        )

        if mapping:
            mapping.torrent_id = new_torrent_id
            self.session.commit()
            return True
        return False

    def get_tracker_id_by_torrent_id(self, torrent_id: int) -> Optional[int]:
        mapping = (
            self.session.query(DownloadTorrentMapping)
            .filter_by(torrent_id=torrent_id)
            .first()
        )
        return mapping.tracker_id if mapping else None

    def delete_mapping(self, torrent_id: int) -> bool:
        mapping = (
            self.session.query(DownloadTorrentMapping)
            .filter_by(torrent_id=torrent_id)
            .first()
        )

        if mapping:
            self.session.delete(mapping)
            self.session.commit()
            return True
        return False
