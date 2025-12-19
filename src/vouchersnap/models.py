"""Data models for VoucherSnap."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Observation:
    """iNaturalist observation metadata."""

    id: int
    taxon_name: str | None = None
    taxon_common_name: str | None = None
    observer_login: str | None = None
    observed_on: str | None = None
    place_guess: str | None = None
    url: str | None = None

    def __post_init__(self):
        if self.url is None:
            self.url = f"https://www.inaturalist.org/observations/{self.id}"


@dataclass
class ScanResult:
    """Result of scanning a single image for QR codes."""

    image_path: Path
    observation_id: int | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.observation_id is not None and self.error is None


@dataclass
class ManifestItem:
    """Item in the upload manifest, combining scan result with observation data."""

    image_path: Path
    image_hash: str
    observation: Observation
    is_duplicate: bool = False

    @property
    def filename(self) -> str:
        return self.image_path.name


@dataclass
class UploadRecord:
    """Record of a completed upload, stored in history."""

    image_hash: str
    observation_id: int
    filename: str
    timestamp: datetime
    caption: str | None = None
    inat_photo_id: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "image_hash": self.image_hash,
            "observation_id": self.observation_id,
            "filename": self.filename,
            "timestamp": self.timestamp.isoformat(),
            "caption": self.caption,
            "inat_photo_id": self.inat_photo_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UploadRecord":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            image_hash=data["image_hash"],
            observation_id=data["observation_id"],
            filename=data["filename"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            caption=data.get("caption"),
            inat_photo_id=data.get("inat_photo_id"),
        )


@dataclass
class UploadResult:
    """Result of uploading a single image."""

    manifest_item: ManifestItem
    success: bool
    inat_photo_id: int | None = None
    error: str | None = None


@dataclass
class ProcessingOptions:
    """Options for image processing."""

    max_dimension: int = 2048
    jpeg_quality: int = 85
    caption: str | None = None
    auto_rotate: bool = False
