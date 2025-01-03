import logging
from logging.handlers import SysLogHandler
from time import sleep
import requests
from cdm_client.config import Config
from cdm_client.transmission_adapter import TransmissionAdapter


class CDMClient:
    def __init__(self) -> None:
        self._logger = self._init_logger()
        self._config = Config()
        self._transmission_adapter = TransmissionAdapter(
            self._config["rpc_user"] or None, self._config["rpc_password"] or None
        )

    def _init_logger(self) -> logging.Logger:
        syslog = SysLogHandler(address="/dev/log")
        syslog.setFormatter(logging.Formatter("cdm-client %(name)s: %(levelname)s %(message)s"))
        logger = logging.getLogger("cdm-client")
        logger.addHandler(syslog)
        logger.setLevel(logging.INFO)
        return logger

    def _update_status(self) -> None:
        data = {"data": self._transmission_adapter.get_status()}
        resp = requests.post(
            f"{self._config['server_host']}/api/client/status/",
            json=data,
            headers={"x-api-key": self._config["api_key"]},
            timeout=5,
        )
        resp.raise_for_status()

    def _download_files(self) -> None:
        resp = requests.get(
            f"{self._config['server_host']}/api/client/", headers={"x-api-key": self._config["api_key"]}, timeout=5
        )
        resp.raise_for_status()

        files = resp.json()["data"]["files"]
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

    def run(self) -> None:
        self._logger.info("Starting cdm-client...")
        while True:
            try:
                self._update_status()
                self._download_files()
            except Exception:  # pylint: disable=broad-except
                self._logger.exception("An error occurred.")
            sleep(30)


def main() -> None:
    cdm_client = CDMClient()
    cdm_client.run()
