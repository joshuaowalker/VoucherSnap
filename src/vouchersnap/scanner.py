"""QR code detection for VoucherSnap."""

import re
from pathlib import Path

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
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


def _try_decode_qr(img: Image.Image) -> str | None:
    """Try to decode a QR code from an image and extract iNat observation ID."""
    decoded = pyzbar.decode(img)
    for obj in decoded:
        if obj.type == "QRCODE":
            try:
                data = obj.data.decode("utf-8")
                obs_id = extract_observation_id(data)
                if obs_id is not None:
                    return obs_id
            except UnicodeDecodeError:
                continue
    return None


def _generate_image_variants(img: Image.Image):
    """Generate image variants to try for QR detection."""
    w, h = img.size

    # Try multiple resize levels - pyzbar can struggle with very high-res images
    for max_dim in [2048, 1500, 1024, 800]:
        if max(w, h) <= max_dim:
            yield img, f"original_{max_dim}"
            continue

        ratio = max_dim / max(w, h)
        resized = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        yield resized, f"resize_{max_dim}"

        # Try with sharpening
        sharp = resized.filter(ImageFilter.SHARPEN)
        yield sharp, f"resize_{max_dim}_sharpen"

        # Try with contrast boost
        enhancer = ImageEnhance.Contrast(resized)
        contrast = enhancer.enhance(1.5)
        yield contrast, f"resize_{max_dim}_contrast"


def scan_image(image_path: Path) -> ScanResult:
    """
    Scan an image for QR codes and extract iNaturalist observation ID.

    Tries multiple image processing approaches to maximize detection rate:
    - Multiple resize levels (high-res images can cause issues)
    - Sharpening and contrast enhancement

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

            # Try original image first
            obs_id = _try_decode_qr(img)
            if obs_id is not None:
                return ScanResult(image_path=image_path, observation_id=obs_id)

            # Try various image processing approaches
            for variant, method in _generate_image_variants(img):
                obs_id = _try_decode_qr(variant)
                if obs_id is not None:
                    return ScanResult(image_path=image_path, observation_id=obs_id)

            # No valid iNat QR code found
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
