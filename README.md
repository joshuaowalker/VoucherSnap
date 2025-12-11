# VoucherSnap

A Python CLI tool for managing herbarium/fungarium specimen images. VoucherSnap scans images for QR codes linking to iNaturalist observations, optionally adds captions, and uploads images directly to iNaturalist.

Designed to work with [inat.label.py](https://github.com/AlanRockefeller/inat.label.py), which generates herbarium labels with QR codes linking to iNaturalist observations.

## Features

- Scan images for QR codes containing iNaturalist observation URLs
- Fetch observation metadata (taxon name, observer, date, location)
- Display manifest of images to be uploaded with observation details
- Burn captions onto images (e.g., "Packaged for DNA Sequencing 12/11/2025")
- Upload images to iNaturalist observations
- Track upload history to detect and warn about duplicates
- Support for JPEG and HEIC images (common iPhone formats)
- Configurable image resizing and JPEG quality

## Installation

### System Dependencies

VoucherSnap requires the `zbar` library for QR code detection.

**macOS (Homebrew):**
```bash
brew install zbar
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libzbar0
```

**Windows:**
Download and install from [ZBar Windows releases](http://zbar.sourceforge.net/download.html)

### Install VoucherSnap

```bash
pip install vouchersnap
```

Or install from source:
```bash
git clone https://github.com/joshuaowalker/VoucherSnap.git
cd vouchersnap
pip install -e .
```

### macOS Note

On macOS with Homebrew, you may need to set the library path:
```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
```

Add this to your `~/.zshrc` or `~/.bashrc` for persistence.

## Authentication

VoucherSnap uses OAuth 2.0 with PKCE (Proof Key for Code Exchange) to authenticate with iNaturalist. This is the recommended authentication flow for desktop/CLI applications as it doesn't require storing secrets.

### Login

```bash
vouchersnap login
```

This opens your browser to the iNaturalist login page. After you authorize VoucherSnap, your session is cached locally for future use.

### Logout

```bash
vouchersnap logout
```

Clears your cached session.

### How Authentication Works

1. When you run `login` (or `run` without an existing session), VoucherSnap starts a temporary local server on `http://127.0.0.1:8914`
2. Your browser opens to iNaturalist's authorization page
3. After you log in and authorize, iNaturalist redirects to the local server with an authorization code
4. VoucherSnap exchanges the code for an access token using PKCE verification
5. The token is cached in `~/.VoucherSnap/token.json`

This flow follows [RFC 7636](https://tools.ietf.org/html/rfc7636) and doesn't require a client secret, making it safe for open-source applications.

## Usage

### Interactive Workflow

The main workflow scans images, shows a manifest, and uploads to iNaturalist:

```bash
# Process all images in a directory
vouchersnap run ~/Photos/herbarium/

# Process specific files
vouchersnap run photo1.jpg photo2.heic

# Process with glob pattern
vouchersnap run "~/Photos/*.jpg"

# With caption
vouchersnap run ~/Photos/herbarium/ --caption "Packaged for DNA Sequencing 12/11/2025"

# With custom image settings
vouchersnap run ~/Photos/herbarium/ --max-size 1024 --quality 90
```

### Scan Only (No Upload)

To scan images for QR codes without uploading:

```bash
vouchersnap scan ~/Photos/herbarium/
```

### View Upload History

```bash
vouchersnap history
vouchersnap history --limit 50
```

## Workflow Example

1. Take photos of herbarium specimens with voucher slips (labels with QR codes)
2. Transfer photos from your phone to your computer
3. Run VoucherSnap:

```bash
$ vouchersnap run ~/Desktop/specimen_photos/

╭──────────────────────────────────────────────────────────────────────────────╮
│ VoucherSnap                                                                  │
╰────────────────────── Herbarium Specimen Photo Manager ──────────────────────╯
Found 5 image(s)

Scanning for QR codes...
Found QR codes in 5 image(s)

Fetching observation data...

                              Upload Manifest
┏━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┓
┃ # ┃ Filename           ┃ Obs ID   ┃ Taxon               ┃ Observer ┃ Status ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━┩
│ 1 │ IMG_0001.heic      │ 12345678 │ Amanita muscaria    │ mycouser │ New    │
│ 2 │ IMG_0002.heic      │ 12345679 │ Boletus edulis      │ mycouser │ New    │
│ 3 │ IMG_0003.heic      │ 12345680 │ Cantharellus        │ mycouser │ New    │
│ ...                                                                         │
└─────────────────────────────────────────────────────────────────────────────┘

Add a caption to the images? [y/N]: y
Enter caption text: Packaged for DNA Sequencing 12/11/2025
Caption: Packaged for DNA Sequencing 12/11/2025
Upload 5 image(s) to iNaturalist? [Y/n]: y

iNaturalist Authentication
Opening browser for iNaturalist login...
Complete the login in your browser to continue.
Authenticated successfully

Uploading images...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Upload Summary
  Total:      5
  Successful: 5
```

## Data Storage

VoucherSnap stores data in `~/.VoucherSnap/`:

- `token.json` - Cached OAuth access token
- `history.json` - Upload history for duplicate detection

## Options

### `run` command

| Option | Default | Description |
|--------|---------|-------------|
| `--caption`, `-c` | None | Caption to overlay on images |
| `--max-size` | 2048 | Max image dimension (pixels) |
| `--quality` | 85 | JPEG quality (1-100) |
| `--skip-duplicates` | False | Skip duplicates without prompting |

### `history` command

| Option | Default | Description |
|--------|---------|-------------|
| `--limit`, `-n` | 20 | Number of records to show |

## Requirements

- Python 3.10+
- zbar library (system dependency)

## License

BSD 2-Clause License
