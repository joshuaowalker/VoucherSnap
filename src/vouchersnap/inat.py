"""iNaturalist API wrapper for VoucherSnap."""

import io

from pyinaturalist import (
    get_access_token,
    get_observation,
    upload_photos,
)

from .config import Config
from .models import Observation


class INatError(Exception):
    """Exception for iNaturalist API errors."""
    pass


class INatClient:
    """Client for interacting with the iNaturalist API."""

    def __init__(self, config: Config):
        """
        Initialize the client with OAuth credentials.

        Args:
            config: Configuration containing client_id and client_secret
        """
        self.config = config
        self._access_token: str | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if client has a valid access token."""
        return self._access_token is not None

    def authenticate(self, username: str, password: str) -> None:
        """
        Authenticate with iNaturalist and obtain access token.

        Args:
            username: iNaturalist username
            password: iNaturalist password

        Raises:
            INatError: If authentication fails
        """
        if not self.config.is_configured:
            raise INatError(
                "OAuth credentials not configured. Run 'vouchersnap config' first."
            )

        try:
            self._access_token = get_access_token(
                username=username,
                password=password,
                app_id=self.config.client_id,
                app_secret=self.config.client_secret,
            )
        except Exception as e:
            raise INatError(f"Authentication failed: {e}") from e

    def fetch_observation(self, obs_id: int) -> Observation:
        """
        Fetch observation details from iNaturalist.

        Args:
            obs_id: iNaturalist observation ID

        Returns:
            Observation object with metadata

        Raises:
            INatError: If observation not found or API error
        """
        try:
            response = get_observation(obs_id)

            # Extract taxon information
            taxon = response.get("taxon", {})
            taxon_name = taxon.get("name")
            taxon_common_name = taxon.get("preferred_common_name")

            # Extract observer information
            user = response.get("user", {})
            observer_login = user.get("login")

            return Observation(
                id=obs_id,
                taxon_name=taxon_name,
                taxon_common_name=taxon_common_name,
                observer_login=observer_login,
                observed_on=response.get("observed_on_string"),
                place_guess=response.get("place_guess"),
            )

        except Exception as e:
            raise INatError(f"Failed to fetch observation {obs_id}: {e}") from e

    def upload_photo(
        self,
        obs_id: int,
        image_data: bytes,
        filename: str = "photo.jpg"
    ) -> int:
        """
        Upload a photo to an observation.

        Args:
            obs_id: iNaturalist observation ID
            image_data: JPEG image bytes
            filename: Filename for the upload

        Returns:
            iNaturalist photo ID

        Raises:
            INatError: If not authenticated or upload fails
        """
        if not self.is_authenticated:
            raise INatError("Not authenticated. Call authenticate() first.")

        try:
            # Convert bytes to file-like object
            photo_file = io.BytesIO(image_data)
            photo_file.name = filename

            response = upload_photos(
                observation_id=obs_id,
                photos=photo_file,
                access_token=self._access_token,
            )

            # Response is a list of photo dicts
            if response and len(response) > 0:
                photo_id = response[0].get("id")
                if photo_id is not None:
                    return photo_id

            raise INatError("Upload succeeded but no photo ID returned")

        except INatError:
            raise
        except Exception as e:
            raise INatError(f"Failed to upload photo to observation {obs_id}: {e}") from e

    def fetch_observations_batch(self, obs_ids: list[int]) -> dict[int, Observation]:
        """
        Fetch multiple observations.

        Args:
            obs_ids: List of observation IDs to fetch

        Returns:
            Dictionary mapping observation ID to Observation object
        """
        results = {}
        for obs_id in obs_ids:
            try:
                results[obs_id] = self.fetch_observation(obs_id)
            except INatError:
                # Skip observations that fail to fetch
                pass
        return results
