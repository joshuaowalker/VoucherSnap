"""QR code detection for VoucherSnap."""

import re
from pathlib import Path

from PIL import Image, ImageOps
from pyzbar import pyzbar

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False

from .models import ScanResult


# Pattern to match iNaturalist observation URLs
INAT_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?inaturalist\.org/observations/(\d+)",
    re.IGNORECASE
)


def extract_observation_id(url: str) -> int | None:
    """
    Extract observation ID from an iNaturalist URL.

    Args:
        url: URL string to parse

    Returns:
        Observation ID as integer, or None if not a valid iNat URL
    """
    match = INAT_URL_PATTERN.search(url)
    if match:
        return int(match.group(1))
    return None


def scan_image(image_path: Path) -> ScanResult:
    """
    Scan an image for QR codes and extract iNaturalist observation ID.

    Args:
        image_path: Path to the image file

    Returns:
        ScanResult with observation_id if found, or error message
    """
    try:
        # Load the image
        with Image.open(image_path) as img:
            # Apply EXIF orientation
            img = ImageOps.exif_transpose(img)

            # Convert to RGB if necessary (pyzbar works better with RGB)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Decode QR codes
            decoded = pyzbar.decode(img)

            # Look for iNaturalist URLs in decoded data
            for obj in decoded:
                if obj.type == "QRCODE":
                    try:
                        data = obj.data.decode("utf-8")
                        obs_id = extract_observation_id(data)
                        if obs_id is not None:
                            return ScanResult(
                                image_path=image_path,
                                observation_id=obs_id
                            )
                    except UnicodeDecodeError:
                        continue

            # No valid iNat QR code found
            if decoded:
                return ScanResult(
                    image_path=image_path,
                    error="QR code found but not an iNaturalist observation URL"
                )
            else:
                return ScanResult(
                    image_path=image_path,
                    error="No QR code detected"
                )

    except FileNotFoundError:
        return ScanResult(
            image_path=image_path,
            error=f"File not found: {image_path}"
        )
    except Exception as e:
        return ScanResult(
            image_path=image_path,
            error=f"Error scanning image: {e}"
        )


def scan_batch(paths: list[Path]) -> list[ScanResult]:
    """
    Scan multiple images for QR codes.

    Args:
        paths: List of image paths to scan

    Returns:
        List of ScanResult objects
    """
    return [scan_image(path) for path in paths]


def get_supported_extensions() -> set[str]:
    """Get set of supported image file extensions."""
    extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    if HEIF_SUPPORTED:
        extensions.update({".heic", ".heif"})
    return extensions


def is_supported_image(path: Path) -> bool:
    """Check if a file is a supported image format."""
    return path.suffix.lower() in get_supported_extensions()
