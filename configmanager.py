import json
import logging
import os
from typing import Any, Dict, Optional
from server.settings import Settings

# from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configurations:
    - file-based config.json (persisted)
    - environment overrides (in-memory only)
    """

    def __init__(
        self,
        environment="development",
        config_file_path="server/config.json",
        aws_region="us-west-2",
    ):
        self.environment = environment
        self.config_file_path = config_file_path
        self.aws_region = aws_region
        self._file_config = {}
        self._env_config = {}
        self.raw_config = {}
        self.settings = Settings()

        self._load_json_config()
        # if environment == "development":
        self._load_env_vars()

        self._merge_file_and_env()
        self._validate_settings()

    def _load_json_config(self) -> None:
        """Load config.json into _file_config only."""
        try:
            with open(self.config_file_path, "r", encoding="utf-8") as f:
                self._file_config = json.load(f)
            logger.info("Local config.json loaded successfully.")
        except FileNotFoundError:
            logger.warning(
                f"Config file {self.config_file_path} not found. Using empty config."
            )
            self._file_config = {}
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            self._file_config = {}

    def _load_env_vars(self) -> None:
        """Loads environment variables into _env_config, never writing them to disk."""
        for key, val in os.environ.items():
            self._env_config[key] = val

    def _load_secrets_from_aws(self) -> None:
        logger.warning("AWS Secrets Manager not implemented yet.")

    def _merge_file_and_env(self) -> None:
        """
        Creates a final merged dictionary from _file_config and _env_config.
        Env vars take precedence (overwrite).
        """
        merged = dict(self._file_config)
        merged.update(self._env_config)
        self.raw_config = merged

    def _validate_settings(self) -> None:
        """
        Merge into Pydantic model to confirm correctness.
        If there's an error, log and fallback to defaults.
        """
        try:
            self.settings = Settings(**self.raw_config)
        except Exception as e:
            logger.error(f"Failed to validate Settings: {e}")
            self.settings = Settings()

    def get(self, key: str, default=None) -> Optional[Any]:
        """
        Get from final merged config (Pydantic).
        """
        return getattr(self.settings, key, default)

    def get_or_error(self, key: str) -> Any:
        data = self.get(key)
        if data is None:
            raise KeyError(f"Key '{key}' not found in settings.")
        return data

    def set(self, key: str, value: Any, persist: bool = False) -> None:
        """
        Update a single key in _file_config (and raw_config), optionally writing to disk.
        """

        try:
            with open(self.config_file_path, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
        except FileNotFoundError:
            disk_data = {}
        except Exception as e:
            logger.error(f"Error reading config file before set: {e}")
            disk_data = {}

        disk_data[key] = value
        self._file_config[key] = value

        if persist:
            try:
                with open(self.config_file_path, "w") as f:
                    json.dump(disk_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Key '{key}' updated in config.json.")
            except Exception as e:
                logger.error(f"Failed to save updated key '{key}' to config file: {e}")

        self._merge_file_and_env()
        self._validate_settings()

    def set_temp(self, key: str, value: Any) -> None:
        """
        Set a key-value pair in the in-memory-only config (_env_config).
        This change will not be written to disk.
        """
        self._env_config[key] = value
        self._merge_file_and_env()
        self._validate_settings()


config = ConfigManager()
