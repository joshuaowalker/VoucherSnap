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


def prompt_credentials() -> tuple[str, str]:
    """
    Prompt for iNaturalist credentials.

    Returns:
        Tuple of (username, password)
    """
    console.print("\n[bold]iNaturalist Authentication[/bold]")
    username = Prompt.ask("Username")
    password = Prompt.ask("Password", password=True)
    return username, password


def prompt_oauth_config() -> tuple[str, str]:
    """
    Prompt for OAuth application credentials.

    Returns:
        Tuple of (client_id, client_secret)
    """
    console.print("\n[bold]OAuth Application Setup[/bold]")
    console.print(
        "Create an application at: "
        "[link=https://www.inaturalist.org/oauth/applications]"
        "inaturalist.org/oauth/applications[/link]"
    )
    console.print()
    client_id = Prompt.ask("Client ID (App ID)")
    client_secret = Prompt.ask("Client Secret")
    return client_id, client_secret


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
