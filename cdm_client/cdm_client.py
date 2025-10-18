import logging
from enum import Enum
from logging.handlers import SysLogHandler
from time import sleep

import requests

from cdm_client.config import Config
from cdm_client.transmission_adapter import TransmissionAdapter


class InstructionAction(Enum):
    STOP = "stop"
    START = "start"
    DELETE = "delete"


class CDMClient:
    def __init__(self) -> None:
        self._logger = self._init_logger()
        self._config = Config()
        self._transmission_adapter = TransmissionAdapter(
            self._config["rpc_user"] or None, self._config["rpc_password"] or None
        )

    def _init_logger(self) -> logging.Logger:
        syslog = SysLogHandler(address="/dev/log")
        syslog.setFormatter(
            logging.Formatter("cdm-client %(name)s: %(levelname)s %(message)s")
        )
        logger = logging.getLogger("cdm-client")
        logger.addHandler(syslog)
        logger.setLevel(logging.INFO)
        return logger

    def _get_status_for_deletion(self, torrent_id: int) -> list[dict]:
        status = self._transmission_adapter.get_status_by_id(torrent_id)
        status["is_deleted"] = True
        return [status]

    def _update_status(self, status_data: list[dict]) -> None:
        resp = requests.post(
            f"{self._config['server_host']}/api/client/status/",
            json={"data": status_data},
            headers={"x-api-key": self._config["api_key"]},
            timeout=5,
        )
        resp.raise_for_status()

    def _download_files(self, files: dict[int, str]) -> None:
        for torrent_id, path in files.items():
            resp = requests.get(
                f"{self._config['server_host']}/api/client/download/{torrent_id}/",
                headers={"x-api-key": self._config["api_key"]},
                stream=True,
                timeout=5,
            )
            resp.raise_for_status()
            self._transmission_adapter.add_torrent(resp.content, download_dir=path)
            self._logger.info("Downloading torrent: %s to %s", torrent_id, path)

    def _execute_instructions(self, instructions: list[dict]) -> None:
        for instruction in instructions:
            self._logger.info("Received instruction: %s", instruction)
            for action, params in instruction.items():
                if action == InstructionAction.STOP.value:
                    self._transmission_adapter.pause_torrent(params["torrent_id"])
                    self._logger.info("Stopped torrent: %s", params["torrent_id"])
                elif action == InstructionAction.START.value:
                    self._transmission_adapter.resume_torrent(params["torrent_id"])
                    self._logger.info("Started torrent: %s", params["torrent_id"])
                elif action == InstructionAction.DELETE.value:
                    status_data = self._get_status_for_deletion(params["torrent_id"])
                    self._transmission_adapter.remove_torrent(params["torrent_id"])
                    self._update_status(status_data)
                    self._logger.info(
                        "Removed torrent and data: %s", params["torrent_id"]
                    )
                else:
                    self._logger.warning("Unknown instruction action: %s", action)

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
            self._update_status(self._transmission_adapter.get_status())

    def run(self) -> None:
        self._logger.info("Starting cdm-client...")
        while True:
            try:
                self._update_status(self._transmission_adapter.get_status())
                self._get_order()
            except Exception:  # pylint: disable=broad-except
                self._logger.exception("An error occurred.")
            sleep(5)


def main() -> None:
    cdm_client = CDMClient()
    cdm_client.run()


if __name__ == "__main__":
    main()
