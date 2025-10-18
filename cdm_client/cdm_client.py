import logging
import os
import shutil
from enum import Enum
from logging.handlers import SysLogHandler
from time import sleep
from typing import Optional

import requests

from cdm_client.config import Config
from cdm_client.database_adapter import DatabaseAdapter
from cdm_client.torent_client_factory import (
    TorrentClientType,
    create_torrent_client_adapter,
)


class InstructionAction(Enum):
    STOP = "stop"
    START = "start"
    DELETE = "delete"


class CDMClient:
    def __init__(self) -> None:
        self._logger = self._init_logger()
        self._config = Config()
        self._torrent_client_adapter = create_torrent_client_adapter(
            TorrentClientType.get_enum_from_value(self._config["client_type"]),
            username=self._config["client_username"] or None,
            password=self._config["client_password"] or None,
            host=self._config["client_host"] or None,
            port=int(self._config["client_port"])
            if self._config["client_port"]
            else None,
        )
        self._database_adapter = DatabaseAdapter()

    def _init_logger(self) -> logging.Logger:
        syslog = SysLogHandler(address="/dev/log")
        syslog.setFormatter(
            logging.Formatter("cdm-client %(name)s: %(levelname)s %(message)s")
        )
        logger = logging.getLogger("cdm-client")
        logger.addHandler(syslog)
        logger.setLevel(logging.INFO)
        return logger

    def _update_status(self, status_data: list[dict]) -> None:
        resp = requests.post(
            f"{self._config['server_host']}/api/client/status/",
            json={"data": status_data},
            headers={"x-api-key": self._config["api_key"]},
            timeout=5,
        )
        resp.raise_for_status()

    def _download_files(self, files: dict[int, str]) -> None:
        for tracker_id, path in files.items():
            resp = requests.get(
                f"{self._config['server_host']}/api/client/download/{tracker_id}/",
                headers={"x-api-key": self._config["api_key"]},
                stream=True,
                timeout=5,
            )
            resp.raise_for_status()
            new_torrent = self._torrent_client_adapter.add_torrent(
                resp.content, download_dir=path
            )
            with self._database_adapter as db_adapter:
                status = db_adapter.create_or_update_download_torrent_mapping(
                    tracker_id=tracker_id, torrent_id=new_torrent.id
                )
                if not status:
                    self._logger.error(
                        "Failed to save download-torrent mapping: %s", status
                    )
            self._logger.info("Downloading torrent: %s to %s", tracker_id, path)

    def _execute_instructions(self, instructions: list[dict]) -> None:
        for instruction in instructions:
            self._logger.info("Received instruction: %s", instruction)
            for action, params in instruction.items():
                if action == InstructionAction.STOP.value:
                    self._torrent_client_adapter.pause_torrent(params["torrent_id"])
                    self._logger.info("Stopped torrent: %s", params["torrent_id"])
                elif action == InstructionAction.START.value:
                    self._torrent_client_adapter.resume_torrent(params["torrent_id"])
                    self._logger.info("Started torrent: %s", params["torrent_id"])
                elif action == InstructionAction.DELETE.value:
                    self.delete_download(params["torrent_id"])
                else:
                    self._logger.warning("Unknown instruction action: %s", action)

    def delete_download(self, torrent_id: int) -> None:
        try:
            status_data = self._get_download_status(
                torrent_id=torrent_id, for_deletion=True
            )
            self._torrent_client_adapter.remove_torrent(torrent_id)
            self._update_status(status_data)
            self._force_delete_if_exists(
                os.path.join(status_data[0]["downloadDir"], status_data[0]["name"])
            )
        finally:
            with self._database_adapter as db_adapter:
                deleted_mapping = db_adapter.delete_mapping(torrent_id=torrent_id)
            self._update_status(status_data)

        self._logger.info(
            "Removed torrent and data: %s, deleted_mapping: %s",
            torrent_id,
            deleted_mapping,
        )

    def _force_delete_if_exists(self, file_path: str) -> None:
        sleep(1)
        if os.path.exists(file_path):
            self._logger.info("Force deleting file: %s", file_path)
            try:
                shutil.rmtree(file_path)
            except FileNotFoundError:
                self._logger.warning("File not found during deletion")

    def _get_order(self) -> None:
        resp = requests.get(
            f"{self._config['server_host']}/api/client/",
            headers={"x-api-key": self._config["api_key"]},
            timeout=5,
        )
        resp.raise_for_status()

        files = resp.json()["data"]["files"]
        if files:
            self._download_files(files)
        instructions = resp.json()["data"]["instructions"]
        if instructions:
            self._execute_instructions(instructions)
            self._update_status(self._get_download_status())

    def _get_download_status(
        self, torrent_id: Optional[int] = None, for_deletion: bool = False
    ) -> list[dict]:
        status = []
        if torrent_id:
            status.append(self._torrent_client_adapter.get_status_by_id(torrent_id))
        else:
            status = self._torrent_client_adapter.get_status()
        with self._database_adapter as db_adapter:
            for status_entry in status:
                tracker_id = db_adapter.get_tracker_id_by_torrent_id(status_entry["id"])
                if tracker_id:
                    status_entry["tracker_id"] = tracker_id
                if for_deletion:
                    status_entry["is_deleted"] = True
        return status

    def run(self) -> None:
        self._logger.info("Starting cdm-client...")
        while True:
            try:
                self._update_status(self._get_download_status())
                self._get_order()
            except Exception:  # pylint: disable=broad-except
                self._logger.exception("An error occurred.")
            sleep(5)


def main() -> None:
    cdm_client = CDMClient()
    cdm_client.run()


if __name__ == "__main__":
    main()
