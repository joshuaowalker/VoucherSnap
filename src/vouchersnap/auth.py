"""PKCE OAuth authentication for iNaturalist."""

import base64
import hashlib
import http.server
import secrets
import socketserver
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

INAT_AUTH_URL = "https://www.inaturalist.org/oauth/authorize"
INAT_TOKEN_URL = "https://www.inaturalist.org/oauth/token"
REDIRECT_PORT = 8914
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"


class AuthError(Exception):
    """Exception for authentication errors."""
    pass


@dataclass
class TokenInfo:
    """OAuth token information."""
    access_token: str
    token_type: str
    created_at: datetime
    expires_in: int | None = None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 5 min buffer)."""
        if self.expires_in is None:
            # Assume 24 hour expiration if not specified
            expires_in = 86400
        else:
            expires_in = self.expires_in

        expiry = self.created_at + timedelta(seconds=expires_in - 300)
        return datetime.now() > expiry

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "created_at": self.created_at.isoformat(),
            "expires_in": self.expires_in,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenInfo":
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            token_type=data["token_type"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_in=data.get("expires_in"),
        )


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate PKCE code verifier and challenge.

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate a random code verifier (43-128 characters)
    code_verifier = secrets.token_urlsafe(64)

    # Create code challenge using S256 method
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")

    return code_verifier, code_challenge


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    auth_code: str | None = None
    error: str | None = None

    def do_GET(self):
        """Handle GET request from OAuth redirect."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self._send_success_response()
        elif "error" in params:
            _OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self._send_error_response()
        else:
            self._send_error_response("Unknown response")

    def _send_success_response(self):
        """Send success HTML page."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>VoucherSnap - Authenticated</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>Authentication Successful!</h1>
            <p>You can close this window and return to VoucherSnap.</p>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def _send_error_response(self, error: str = None):
        """Send error HTML page."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        error_msg = error or _OAuthCallbackHandler.error or "Unknown error"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>VoucherSnap - Error</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>Authentication Failed</h1>
            <p>{error_msg}</p>
            <p>Please close this window and try again.</p>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def authenticate_pkce(client_id: str, timeout: int = 120) -> TokenInfo:
    """
    Perform PKCE OAuth authentication flow.

    Opens browser for user to log in, catches the callback,
    and exchanges the auth code for an access token.

    Args:
        client_id: iNaturalist OAuth application ID
        timeout: Seconds to wait for user to complete login

    Returns:
        TokenInfo with access token

    Raises:
        AuthError: If authentication fails
    """
    # Reset handler state
    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.error = None

    # Generate PKCE pair
    code_verifier, code_challenge = generate_pkce_pair()

    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
    }
    auth_url = f"{INAT_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    # Start local server to catch callback
    server = socketserver.TCPServer(("127.0.0.1", REDIRECT_PORT), _OAuthCallbackHandler)
    server.timeout = timeout

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback (single request)
    try:
        server.handle_request()
    finally:
        server.server_close()

    # Check for errors
    if _OAuthCallbackHandler.error:
        raise AuthError(f"Authorization failed: {_OAuthCallbackHandler.error}")

    if not _OAuthCallbackHandler.auth_code:
        raise AuthError("No authorization code received (timeout or user cancelled)")

    # Exchange code for token
    token_data = {
        "client_id": client_id,
        "code": _OAuthCallbackHandler.auth_code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }

    try:
        response = requests.post(INAT_TOKEN_URL, data=token_data, timeout=30)
        response.raise_for_status()
        token_response = response.json()
    except requests.RequestException as e:
        raise AuthError(f"Token exchange failed: {e}") from e

    if "access_token" not in token_response:
        raise AuthError(f"Invalid token response: {token_response}")

    return TokenInfo(
        access_token=token_response["access_token"],
        token_type=token_response.get("token_type", "Bearer"),
        created_at=datetime.now(),
        expires_in=token_response.get("expires_in"),
    )
