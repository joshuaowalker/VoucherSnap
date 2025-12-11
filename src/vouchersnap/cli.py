"""Command-line interface for VoucherSnap."""

import glob
from datetime import datetime
from pathlib import Path

import click

from . import __version__
from .config import Config, load_config, save_config
from .history import HistoryManager
from .images import compute_hash, process_image
from .inat import INatClient, INatError
from .models import ManifestItem, ProcessingOptions, ScanResult
from .scanner import is_supported_image, scan_batch, get_supported_extensions
from . import ui


def resolve_paths(paths: tuple[str, ...]) -> list[Path]:
    """
    Resolve input paths to a list of image files.

    Handles:
    - Directories (all supported images within)
    - Glob patterns
    - Individual files

    Args:
        paths: Tuple of path strings from CLI

    Returns:
        List of resolved Path objects to image files
    """
    result = []
    extensions = get_supported_extensions()

    for path_str in paths:
        # Check if it's a glob pattern
        if "*" in path_str or "?" in path_str:
            for match in glob.glob(path_str, recursive=True):
                p = Path(match)
                if p.is_file() and is_supported_image(p):
                    result.append(p)
        else:
            p = Path(path_str)
            if p.is_dir():
                # Add all supported images in directory
                for ext in extensions:
                    result.extend(p.glob(f"*{ext}"))
                    result.extend(p.glob(f"*{ext.upper()}"))
            elif p.is_file() and is_supported_image(p):
                result.append(p)

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for p in result:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(p)

    return sorted(unique, key=lambda p: p.name)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    """VoucherSnap - Herbarium specimen photo manager.

    Scan images for QR codes linking to iNaturalist observations,
    optionally add captions, and upload to iNaturalist.
    """
    if ctx.invoked_subcommand is None:
        # Show help by default
        click.echo(ctx.get_help())


@cli.command()
@click.argument("paths", nargs=-1, required=True)
@click.option("--caption", "-c", help="Caption to overlay on images")
@click.option("--max-size", default=2048, help="Max image dimension (default: 2048)")
@click.option("--quality", default=85, help="JPEG quality 1-100 (default: 85)")
@click.option("--skip-duplicates", is_flag=True, help="Skip duplicate images without prompting")
def run(paths: tuple[str, ...], caption: str | None, max_size: int, quality: int, skip_duplicates: bool):
    """Interactive workflow for scanning and uploading images.

    PATHS can be directories, files, or glob patterns (e.g., *.jpg)
    """
    ui.print_banner()

    # Load configuration
    config = load_config()
    if not config.is_configured:
        ui.print_error("OAuth credentials not configured.")
        ui.print_info("Run 'vouchersnap config' to set up your iNaturalist application.")
        raise SystemExit(1)

    # Resolve paths
    image_paths = resolve_paths(paths)
    if not image_paths:
        ui.print_error("No supported image files found.")
        ui.print_info(f"Supported formats: {', '.join(sorted(get_supported_extensions()))}")
        raise SystemExit(1)

    ui.print_info(f"Found {len(image_paths)} image(s)")

    # Scan for QR codes
    ui.console.print("\n[bold]Scanning for QR codes...[/bold]")
    scan_results = scan_batch(image_paths)

    # Filter successful scans
    successful_scans = [r for r in scan_results if r.success]
    failed_scans = [r for r in scan_results if not r.success]

    if failed_scans:
        ui.display_scan_results(failed_scans)

    if not successful_scans:
        ui.print_error("No valid iNaturalist QR codes found in any images.")
        raise SystemExit(1)

    ui.print_success(f"Found QR codes in {len(successful_scans)} image(s)")

    # Fetch observation metadata
    ui.console.print("\n[bold]Fetching observation data...[/bold]")
    client = INatClient(config)
    obs_ids = list(set(r.observation_id for r in successful_scans if r.observation_id))

    observations = {}
    with ui.create_progress() as progress:
        task = progress.add_task("Fetching...", total=len(obs_ids))
        for obs_id in obs_ids:
            try:
                observations[obs_id] = client.fetch_observation(obs_id)
            except INatError as e:
                ui.print_warning(f"Could not fetch observation {obs_id}: {e}")
            progress.advance(task)

    # Build manifest
    history = HistoryManager()
    manifest: list[ManifestItem] = []

    for scan_result in successful_scans:
        obs_id = scan_result.observation_id
        if obs_id not in observations:
            continue

        image_hash = compute_hash(scan_result.image_path)
        is_duplicate = history.is_duplicate(image_hash, obs_id)

        manifest.append(ManifestItem(
            image_path=scan_result.image_path,
            image_hash=image_hash,
            observation=observations[obs_id],
            is_duplicate=is_duplicate,
        ))

    if not manifest:
        ui.print_error("No valid observations found for the scanned images.")
        raise SystemExit(1)

    # Display manifest
    ui.console.print()
    ui.display_manifest(manifest)

    # Handle duplicates
    duplicates = [m for m in manifest if m.is_duplicate]
    if duplicates and not skip_duplicates:
        ui.print_warning(f"{len(duplicates)} image(s) have been uploaded before.")
        if not ui.prompt_confirm_duplicates():
            manifest = [m for m in manifest if not m.is_duplicate]
            if not manifest:
                ui.print_info("No new images to upload.")
                raise SystemExit(0)
    elif skip_duplicates and duplicates:
        manifest = [m for m in manifest if not m.is_duplicate]
        if not manifest:
            ui.print_info("All images are duplicates. Nothing to upload.")
            raise SystemExit(0)

    # Prompt for caption if not provided
    if caption is None:
        caption = ui.prompt_caption()

    if caption:
        ui.print_info(f"Caption: {caption}")

    # Confirm upload
    if not ui.prompt_confirm_upload(len(manifest), len(duplicates)):
        ui.print_info("Upload cancelled.")
        raise SystemExit(0)

    # Authenticate
    username, password = ui.prompt_credentials()
    try:
        client.authenticate(username, password)
    except INatError as e:
        ui.print_error(f"Authentication failed: {e}")
        raise SystemExit(1)

    ui.print_success("Authenticated successfully")

    # Process and upload
    options = ProcessingOptions(
        max_dimension=max_size,
        jpeg_quality=quality,
        caption=caption,
    )

    successful = 0
    failed = 0

    ui.console.print("\n[bold]Uploading images...[/bold]")
    with ui.create_progress() as progress:
        task = progress.add_task("Uploading...", total=len(manifest))

        for item in manifest:
            try:
                # Process image
                image_data = process_image(item.image_path, options)

                # Upload
                photo_id = client.upload_photo(
                    item.observation.id,
                    image_data,
                    item.filename,
                )

                # Record in history
                history.create_record(
                    image_hash=item.image_hash,
                    observation_id=item.observation.id,
                    filename=item.filename,
                    caption=caption,
                    inat_photo_id=photo_id,
                )

                successful += 1

            except Exception as e:
                ui.print_error(f"Failed to upload {item.filename}: {e}")
                failed += 1

            progress.advance(task)

    # Display summary
    ui.display_summary(
        total=len(manifest),
        successful=successful,
        failed=failed,
    )


@cli.command()
@click.argument("paths", nargs=-1, required=True)
def scan(paths: tuple[str, ...]):
    """Scan images for QR codes without uploading.

    PATHS can be directories, files, or glob patterns.
    """
    ui.print_banner()

    image_paths = resolve_paths(paths)
    if not image_paths:
        ui.print_error("No supported image files found.")
        raise SystemExit(1)

    ui.print_info(f"Scanning {len(image_paths)} image(s)...")

    results = scan_batch(image_paths)
    ui.display_scan_results(results)

    successful = sum(1 for r in results if r.success)
    ui.console.print()
    ui.print_info(f"Found QR codes in {successful}/{len(results)} image(s)")


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of records to show")
def history(limit: int):
    """View upload history."""
    ui.print_banner()

    history_mgr = HistoryManager()
    records = history_mgr.get_history()

    ui.display_history(records, limit=limit)


@cli.command("config")
def configure():
    """Configure iNaturalist OAuth credentials."""
    ui.print_banner()

    config = load_config()

    if config.is_configured:
        ui.print_info("Existing configuration found.")
        if not ui.console.input("Overwrite? [y/N]: ").lower().startswith("y"):
            raise SystemExit(0)

    client_id, client_secret = ui.prompt_oauth_config()

    config = Config(
        client_id=client_id,
        client_secret=client_secret,
    )
    save_config(config)

    ui.print_success("Configuration saved!")
    ui.print_info(f"Config file: {config}")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
