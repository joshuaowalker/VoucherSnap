"""Terminal UI components for VoucherSnap using Rich."""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

from .models import ManifestItem, UploadRecord, ScanResult


console = Console()


def print_banner() -> None:
    """Print the VoucherSnap banner."""
    banner = Text("VoucherSnap", style="bold cyan")
    console.print(Panel(banner, subtitle="Herbarium Specimen Photo Manager"))


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]Error:[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]Warning:[/yellow] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]{message}[/green]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]{message}[/blue]")


def display_scan_results(results: list[ScanResult]) -> None:
    """
    Display results of scanning images for QR codes.

    Args:
        results: List of ScanResult objects
    """
    table = Table(title="Scan Results")
    table.add_column("Filename", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Observation ID", style="green")

    for result in results:
        if result.success:
            status = "[green]Found[/green]"
            obs_id = str(result.observation_id)
        else:
            status = f"[red]{result.error}[/red]"
            obs_id = "-"

        table.add_row(result.image_path.name, status, obs_id)

    console.print(table)


def display_manifest(items: list[ManifestItem]) -> None:
    """
    Display the upload manifest table.

    Args:
        items: List of ManifestItem objects
    """
    table = Table(title="Upload Manifest")
    table.add_column("#", style="dim")
    table.add_column("Filename", style="cyan")
    table.add_column("Obs ID", style="green")
    table.add_column("Taxon", style="yellow")
    table.add_column("Observer", style="blue")
    table.add_column("Status", style="white")

    for i, item in enumerate(items, 1):
        # Build taxon display
        taxon = item.observation.taxon_name or "Unknown"
        if item.observation.taxon_common_name:
            taxon = f"{taxon} ({item.observation.taxon_common_name})"

        # Status indicator
        if item.is_duplicate:
            status = "[yellow]Duplicate[/yellow]"
        else:
            status = "[green]New[/green]"

        table.add_row(
            str(i),
            item.filename,
            str(item.observation.id),
            taxon,
            item.observation.observer_login or "Unknown",
            status,
        )

    console.print(table)


def display_history(records: list[UploadRecord], limit: int = 20) -> None:
    """
    Display upload history.

    Args:
        records: List of UploadRecord objects
        limit: Maximum records to show
    """
    if not records:
        console.print("[dim]No upload history found.[/dim]")
        return

    table = Table(title=f"Upload History (showing {min(len(records), limit)} of {len(records)})")
    table.add_column("Date", style="dim")
    table.add_column("Filename", style="cyan")
    table.add_column("Obs ID", style="green")
    table.add_column("Caption", style="yellow")
    table.add_column("Photo ID", style="blue")

    for record in records[:limit]:
        table.add_row(
            record.timestamp.strftime("%Y-%m-%d %H:%M"),
            record.filename,
            str(record.observation_id),
            record.caption or "-",
            str(record.inat_photo_id) if record.inat_photo_id else "-",
        )

    console.print(table)


def prompt_caption() -> str | None:
    """
    Prompt user for optional caption text.

    Returns:
        Caption string, or None if user declines
    """
    if not Confirm.ask("Add a caption to the images?", default=False):
        return None

    caption = Prompt.ask("Enter caption text")
    return caption if caption.strip() else None


def prompt_confirm_upload(count: int, duplicate_count: int = 0) -> bool:
    """
    Confirm upload of images.

    Args:
        count: Total number of images
        duplicate_count: Number of duplicate images

    Returns:
        True if user confirms
    """
    message = f"Upload {count} image(s) to iNaturalist?"
    if duplicate_count > 0:
        message = f"Upload {count} image(s) ({duplicate_count} duplicate(s)) to iNaturalist?"

    return Confirm.ask(message, default=True)


def prompt_confirm_duplicates() -> bool:
    """
    Confirm re-uploading duplicate images.

    Returns:
        True if user wants to include duplicates
    """
    return Confirm.ask(
        "Include duplicate images in upload?",
        default=False
    )


def prompt_manual_observation_id(filename: str) -> int | None:
    """
    Prompt user to manually enter an observation ID for a failed scan.

    Args:
        filename: Name of the image file

    Returns:
        Observation ID if entered, None if skipped
    """
    console.print(f"\n[cyan]{filename}[/cyan]")
    response = Prompt.ask(
        "  Enter observation ID (or press Enter to skip)",
        default=""
    )

    if not response.strip():
        return None

    # Handle full URLs or just IDs
    response = response.strip()

    # Try to extract ID from URL
    if "inaturalist.org" in response:
        import re
        match = re.search(r"/observations/(\d+)", response)
        if match:
            return int(match.group(1))

    # Try to parse as integer
    try:
        return int(response)
    except ValueError:
        console.print("  [yellow]Invalid input, skipping[/yellow]")
        return None


def prompt_manual_entry_for_failures(failed_count: int) -> bool:
    """
    Ask if user wants to manually enter observation IDs for failed scans.

    Args:
        failed_count: Number of images that failed QR detection

    Returns:
        True if user wants to enter IDs manually
    """
    return Confirm.ask(
        f"Manually enter observation IDs for {failed_count} failed image(s)?",
        default=False
    )


def print_auth_browser_message() -> None:
    """Inform user that browser will open for authentication."""
    console.print("\n[bold]iNaturalist Authentication[/bold]")
    console.print("Opening browser for iNaturalist login...")
    console.print("[dim]Complete the login in your browser to continue.[/dim]")


def create_progress() -> Progress:
    """
    Create a progress bar for uploads.

    Returns:
        Rich Progress object
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    )


def display_summary(
    total: int,
    successful: int,
    failed: int,
    skipped: int = 0
) -> None:
    """
    Display upload summary.

    Args:
        total: Total images processed
        successful: Number of successful uploads
        failed: Number of failed uploads
        skipped: Number of skipped uploads
    """
    console.print()
    console.print("[bold]Upload Summary[/bold]")
    console.print(f"  Total:      {total}")
    console.print(f"  [green]Successful: {successful}[/green]")
    if failed > 0:
        console.print(f"  [red]Failed:     {failed}[/red]")
    if skipped > 0:
        console.print(f"  [yellow]Skipped:    {skipped}[/yellow]")


def display_observation_list(
    observations: list[tuple[int, int, str, str]],
    selected: set[int],
) -> None:
    """
    Display numbered list of observations for manifest selection.

    Args:
        observations: List of (index, obs_id, date_str, filename) tuples
        selected: Set of selected indices (1-based)
    """
    table = Table(show_header=True, header_style="bold")
    table.add_column("", width=3)  # Selection marker
    table.add_column("#", style="dim", width=3)
    table.add_column("Obs ID", style="green")
    table.add_column("First Upload", style="dim")
    table.add_column("Filename", style="cyan")

    for idx, obs_id, date_str, filename in observations:
        marker = "[bold green][*][/bold green]" if idx in selected else "[ ]"
        table.add_row(marker, str(idx), str(obs_id), date_str, filename)

    console.print(table)


def interactive_toggle_selection(
    observations: list[tuple[int, int, str, str]],
) -> set[int]:
    """
    Interactive toggle selection for observations.

    Args:
        observations: List of (index, obs_id, date_str, filename) tuples

    Returns:
        Set of selected observation IDs
    """
    selected_indices: set[int] = set()
    max_idx = len(observations)

    # Initial display
    display_observation_list(observations, selected_indices)

    while True:
        console.print()
        response = Prompt.ask(
            'Enter numbers to toggle (e.g., "1 3 5"), "all", "none", or "done"',
            default=""
        ).strip().lower()

        if response == "done":
            break
        elif response == "all":
            selected_indices = set(range(1, max_idx + 1))
        elif response == "none":
            selected_indices = set()
        elif response == "":
            continue
        else:
            # Parse space-separated numbers
            for part in response.split():
                try:
                    num = int(part)
                    if 1 <= num <= max_idx:
                        if num in selected_indices:
                            selected_indices.discard(num)
                        else:
                            selected_indices.add(num)
                    else:
                        console.print(f"[yellow]Invalid: {num} (enter 1-{max_idx})[/yellow]")
                except ValueError:
                    console.print(f"[yellow]Invalid input: {part}[/yellow]")

        # Redisplay with updated selection
        console.print()
        display_observation_list(observations, selected_indices)

    # Convert indices to observation IDs
    idx_to_obs = {idx: obs_id for idx, obs_id, _, _ in observations}
    return {idx_to_obs[idx] for idx in selected_indices}


def format_plain_manifest(
    items: list[tuple[int, str, str | None]],
) -> str:
    """
    Format observations as plain ASCII manifest with checkboxes.

    Args:
        items: List of (obs_id, taxon_name, common_name) tuples

    Returns:
        Plain text manifest string for printing
    """
    from datetime import datetime

    lines = []
    lines.append("=" * 50)
    lines.append("SHIPPING MANIFEST")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("=" * 50)
    lines.append("")

    for obs_id, taxon_name, common_name in items:
        taxon_display = taxon_name or "Unknown taxon"
        if common_name:
            taxon_display = f"{taxon_display} ({common_name})"
        lines.append(f"[ ] {obs_id}  {taxon_display}")

    lines.append("")
    lines.append("=" * 50)
    lines.append(f"Total: {len(items)} specimen(s)")
    lines.append("=" * 50)

    return "\n".join(lines)


def print_plain_manifest(manifest_text: str) -> None:
    """
    Print manifest as plain text without Rich formatting.

    Args:
        manifest_text: The formatted manifest string
    """
    # Use print() directly to avoid Rich markup interpretation
    print(manifest_text)
