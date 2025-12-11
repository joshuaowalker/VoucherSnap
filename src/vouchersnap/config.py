"""Configuration management for VoucherSnap."""

import json
from dataclasses import dataclass
from pathlib import Path

from .auth import TokenInfo


DEFAULT_MAX_DIMENSION = 2048
DEFAULT_JPEG_QUALITY = 85


def get_app_dir() -> Path:
    """Get the VoucherSnap application directory (~/.VoucherSnap)."""
    app_dir = Path.home() / ".VoucherSnap"
    app_dir.mkdir(exist_ok=True)
    return app_dir


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_app_dir() / "config.json"


def get_token_path() -> Path:
    """Get the path to the token file."""
    return get_app_dir() / "token.json"


def get_history_path() -> Path:
    """Get the path to the history file."""
    return get_app_dir() / "history.json"


@dataclass
class Config:
    """VoucherSnap configuration."""

    client_id: str = ""
    default_max_dimension: int = DEFAULT_MAX_DIMENSION
    default_jpeg_quality: int = DEFAULT_JPEG_QUALITY

    @property
    def is_configured(self) -> bool:
        """Check if OAuth client ID is configured."""
        return bool(self.client_id)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "client_id": self.client_id,
            "default_max_dimension": self.default_max_dimension,
            "default_jpeg_quality": self.default_jpeg_quality,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            client_id=data.get("client_id", ""),
            default_max_dimension=data.get("default_max_dimension", DEFAULT_MAX_DIMENSION),
            default_jpeg_quality=data.get("default_jpeg_quality", DEFAULT_JPEG_QUALITY),
        )


def load_config() -> Config:
    """Load configuration from file, or return default config if not found."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
            return Config.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return Config()
    return Config()


def save_config(config: Config) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2)


def load_token() -> TokenInfo | None:
    """Load saved token from file, or return None if not found or expired."""
    token_path = get_token_path()
    if token_path.exists():
        try:
            with open(token_path) as f:
                data = json.load(f)
            token = TokenInfo.from_dict(data)
            if not token.is_expired:
                return token
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return None


def save_token(token: TokenInfo) -> None:
    """Save token to file."""
    token_path = get_token_path()
    with open(token_path, "w") as f:
        json.dump(token.to_dict(), f, indent=2)


def clear_token() -> None:
    """Remove saved token."""
    token_path = get_token_path()
    if token_path.exists():
        token_path.unlink()
