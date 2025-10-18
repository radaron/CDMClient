import configparser
import os
from typing import Union

from cryptography.fernet import Fernet


class Config:
    CONFIG_FOLDER_PATH = os.path.join(os.path.expanduser("~"), ".config", "cdm_client")
    KEY_PATH = os.path.join(CONFIG_FOLDER_PATH, "key.key")
    CONFIG_PATH = os.path.join(CONFIG_FOLDER_PATH, "config.ini")
    DEFAULT_CONFIG = {
        "connection": {
            "server_host": "",
            "api_key": "",
            "rpc_user": "",
            "rpc_password": "",
        }
    }
    ENCRYPTED_CONFIG = ["rpc_password"]

    def __init__(self) -> None:
        self._key: Union[bytes, str] = ""
        self._config = self._load_config()
        self._check_key()

    def _check_key(self) -> None:
        if not self._key_exists:
            self._create_key()
        else:
            self._read_key()

    def _create_key(self) -> None:
        self._key = Fernet.generate_key()
        with open(self.KEY_PATH, "w", encoding="utf-8") as f:
            f.write(self._key.decode())

    def _read_key(self) -> None:
        with open(self.KEY_PATH, "r", encoding="utf-8") as f:
            self._key = f.read().encode()

    def _load_config(self) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        if config.read(self.CONFIG_PATH):
            return config
        return self._create_config()

    def _create_config(self) -> configparser.ConfigParser:
        if not os.path.exists(self.CONFIG_FOLDER_PATH):
            os.makedirs(self.CONFIG_FOLDER_PATH)
        config = configparser.ConfigParser()
        for section, configs in self.DEFAULT_CONFIG.items():
            config[section] = {}
            for config_key, config_value in configs.items():
                config[section][config_key] = config_value
        with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
            config.write(f)
        return config

    def _decrypt(self, value: str) -> str:
        f = Fernet(self._key)
        return f.decrypt(value.encode()).decode()

    def _encrypt(self, value: str) -> str:
        f = Fernet(self._key)
        return f.encrypt(value.encode()).decode()

    def _write_creds(self) -> None:
        with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
            self._config.write(f)

    @property
    def _key_exists(self) -> bool:
        return os.path.exists(self.KEY_PATH)

    def __getitem__(self, name: str) -> str:
        if name in self.ENCRYPTED_CONFIG:
            try:
                return self._decrypt(self._config["connection"][name])
            except Exception:  # pylint: disable=broad-except
                raw_value = self._config["connection"][name]
                self._config["connection"][name] = self._encrypt(
                    self._config["connection"][name]
                )
                self._write_creds()
                return raw_value
        return self._config["connection"][name]
