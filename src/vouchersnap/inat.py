"""iNaturalist API wrapper for VoucherSnap."""

import io

from pyinaturalist import (
    ClientSession,
    get_observation,
    upload_photos,
)

from . import __version__
from .auth import TokenInfo
from .models import Observation


# Custom session with VoucherSnap user agent
# pyinaturalist handles rate limiting automatically (60 req/min default)
_session = ClientSession(user_agent=f"VoucherSnap/{__version__}")


class INatError(Exception):
    """Exception for iNaturalist API errors."""
    pass


class INatClient:
    """Client for interacting with the iNaturalist API."""

    def __init__(self, token: TokenInfo | None = None):
        """
        Initialize the client.

        Args:
            token: Optional TokenInfo for authenticated requests
        """
        self._token = token

    @property
    def access_token(self) -> str | None:
        """Get the access token string."""
        return self._token.access_token if self._token else None

    @property
    def is_authenticated(self) -> bool:
        """Check if client has a valid access token."""
        return self._token is not None and not self._token.is_expired

    def set_token(self, token: TokenInfo) -> None:
        """Set the access token."""
        self._token = token

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
            response = get_observation(obs_id, session=_session)

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
            raise INatError("Not authenticated. Please log in first.")

        try:
            # Convert bytes to file-like object
            photo_file = io.BytesIO(image_data)
            photo_file.name = filename

            response = upload_photos(
                observation_id=obs_id,
                photos=photo_file,
                access_token=self.access_token,
                session=_session,
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
