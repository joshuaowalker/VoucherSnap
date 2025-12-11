"""Image processing for VoucherSnap."""

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

from .models import ProcessingOptions


def compute_hash(path: Path) -> str:
    """
    Compute SHA256 hash of an image file.

    Args:
        path: Path to the image file

    Returns:
        Hex-encoded SHA256 hash string
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_image(path: Path) -> Image.Image:
    """
    Load an image file, handling HEIC conversion if needed.

    Args:
        path: Path to the image file

    Returns:
        PIL Image object in RGB mode
    """
    img = Image.open(path)

    # Handle EXIF orientation
    try:
        exif = img._getexif()
        if exif:
            orientation = exif.get(274)  # 274 is the EXIF orientation tag
            if orientation:
                rotations = {
                    3: 180,
                    6: 270,
                    8: 90,
                }
                if orientation in rotations:
                    img = img.rotate(rotations[orientation], expand=True)
    except (AttributeError, KeyError, TypeError):
        pass

    # Convert to RGB if necessary
    if img.mode in ("RGBA", "P"):
        # Create white background for transparency
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    return img


def resize_image(img: Image.Image, max_dimension: int) -> Image.Image:
    """
    Resize image to fit within max_dimension while maintaining aspect ratio.

    Args:
        img: PIL Image object
        max_dimension: Maximum width or height

    Returns:
        Resized PIL Image (or original if already smaller)
    """
    width, height = img.size

    if width <= max_dimension and height <= max_dimension:
        return img

    if width > height:
        new_width = max_dimension
        new_height = int(height * (max_dimension / width))
    else:
        new_height = max_dimension
        new_width = int(width * (max_dimension / height))

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def add_caption(img: Image.Image, caption: str) -> Image.Image:
    """
    Add caption overlay at bottom center with semi-transparent background.

    Args:
        img: PIL Image object
        caption: Text to overlay

    Returns:
        PIL Image with caption overlay
    """
    img = img.copy()
    draw = ImageDraw.Draw(img, "RGBA")

    width, height = img.size

    # Calculate font size based on image dimensions (roughly 3% of height)
    target_font_size = max(20, int(height * 0.03))

    # Try to load a nice font, fall back to default
    font = None
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "/System/Library/Fonts/SFNSText.ttf",   # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch Linux
        "C:\\Windows\\Fonts\\arial.ttf",  # Windows
    ]

    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, target_font_size)
            break
        except (OSError, IOError):
            continue

    if font is None:
        # Fall back to default font
        font = ImageFont.load_default()

    # Get text bounding box
    bbox = draw.textbbox((0, 0), caption, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Calculate positions
    padding = int(height * 0.01)
    bar_height = text_height + padding * 2

    # Draw semi-transparent black bar at bottom
    bar_y = height - bar_height
    draw.rectangle(
        [(0, bar_y), (width, height)],
        fill=(0, 0, 0, 180)  # Semi-transparent black
    )

    # Draw text centered in bar
    text_x = (width - text_width) // 2
    text_y = bar_y + padding
    draw.text((text_x, text_y), caption, font=font, fill=(255, 255, 255, 255))

    # Convert back to RGB (removing alpha channel)
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background

    return img


def process_image(
    path: Path,
    options: ProcessingOptions | None = None
) -> bytes:
    """
    Full image processing pipeline.

    Args:
        path: Path to the source image
        options: Processing options (uses defaults if None)

    Returns:
        JPEG bytes of the processed image
    """
    if options is None:
        options = ProcessingOptions()

    # Load and convert
    img = load_image(path)

    # Resize if needed
    img = resize_image(img, options.max_dimension)

    # Add caption if provided
    if options.caption:
        img = add_caption(img, options.caption)

    # Encode to JPEG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=options.jpeg_quality, optimize=True)
    buffer.seek(0)

    return buffer.getvalue()
