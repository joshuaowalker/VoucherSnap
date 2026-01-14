"""Upload history management for VoucherSnap."""

import json
from datetime import datetime
from pathlib import Path

from .config import get_history_path
from .models import UploadRecord


class HistoryManager:
    """Manages upload history to track and detect duplicate uploads."""

    def __init__(self, history_path: Path | None = None):
        """
        Initialize the history manager.

        Args:
            history_path: Path to history file (uses default if None)
        """
        self.history_path = history_path or get_history_path()
        self._records: list[UploadRecord] = []
        self._load()

    def _load(self) -> None:
        """Load history from file."""
        if self.history_path.exists():
            try:
                with open(self.history_path) as f:
                    data = json.load(f)
                self._records = [
                    UploadRecord.from_dict(record)
                    for record in data.get("uploads", [])
                ]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._records = []
        else:
            self._records = []

    def _save(self) -> None:
        """Save history to file."""
        # Ensure parent directory exists
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "uploads": [record.to_dict() for record in self._records]
        }
        with open(self.history_path, "w") as f:
            json.dump(data, f, indent=2)

    def is_duplicate(self, image_hash: str, obs_id: int) -> bool:
        """
        Check if this exact image was already uploaded to this observation.

        Args:
            image_hash: SHA256 hash of the image
            obs_id: iNaturalist observation ID

        Returns:
            True if this image was previously uploaded to this observation
        """
        return any(
            record.image_hash == image_hash and record.observation_id == obs_id
            for record in self._records
        )

    def get_duplicate_record(self, image_hash: str, obs_id: int) -> UploadRecord | None:
        """
        Get the existing upload record if this is a duplicate.

        Args:
            image_hash: SHA256 hash of the image
            obs_id: iNaturalist observation ID

        Returns:
            UploadRecord if duplicate exists, None otherwise
        """
        for record in self._records:
            if record.image_hash == image_hash and record.observation_id == obs_id:
                return record
        return None

    def add_record(self, record: UploadRecord) -> None:
        """
        Add an upload record and save.

        Args:
            record: UploadRecord to add
        """
        self._records.append(record)
        self._save()

    def create_record(
        self,
        image_hash: str,
        observation_id: int,
        filename: str,
        caption: str | None = None,
        inat_photo_id: int | None = None,
    ) -> UploadRecord:
        """
        Create and add a new upload record.

        Args:
            image_hash: SHA256 hash of the image
            observation_id: iNaturalist observation ID
            filename: Original filename
            caption: Caption used (if any)
            inat_photo_id: iNaturalist photo ID returned from upload

        Returns:
            The created UploadRecord
        """
        record = UploadRecord(
            image_hash=image_hash,
            observation_id=observation_id,
            filename=filename,
            timestamp=datetime.now(),
            caption=caption,
            inat_photo_id=inat_photo_id,
        )
        self.add_record(record)
        return record

    def get_history(self) -> list[UploadRecord]:
        """
        Get all upload records, most recent first.

        Returns:
            List of UploadRecord objects sorted by timestamp descending
        """
        return sorted(self._records, key=lambda r: r.timestamp, reverse=True)

    def get_uploads_for_observation(self, obs_id: int) -> list[UploadRecord]:
        """
        Get all uploads for a specific observation.

        Args:
            obs_id: iNaturalist observation ID

        Returns:
            List of UploadRecord objects for this observation
        """
        return [r for r in self._records if r.observation_id == obs_id]

    @property
    def count(self) -> int:
        """Get total number of upload records."""
        return len(self._records)

    def get_unique_observations(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[int, list[UploadRecord]]:
        """
        Get unique observation IDs grouped with their upload records.

        Args:
            since: Only include records after this datetime
            until: Only include records before this datetime

        Returns:
            Dictionary mapping observation_id to list of UploadRecords,
            sorted by earliest upload timestamp
        """
        # Filter records by date range
        filtered = self._records
        if since:
            filtered = [r for r in filtered if r.timestamp >= since]
        if until:
            filtered = [r for r in filtered if r.timestamp <= until]

        # Group by observation ID
        groups: dict[int, list[UploadRecord]] = {}
        for record in filtered:
            if record.observation_id not in groups:
                groups[record.observation_id] = []
            groups[record.observation_id].append(record)

        # Sort each group by timestamp and sort groups by earliest timestamp
        for obs_id in groups:
            groups[obs_id].sort(key=lambda r: r.timestamp)

        # Return sorted by earliest upload
        return dict(
            sorted(groups.items(), key=lambda x: x[1][0].timestamp)
        )
