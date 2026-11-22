"""Turn an uploaded file into clean notice text.

Only plain text is accepted (``.txt`` and ``.md``). Files are decoded as UTF-8
first, falling back to other common encodings when that fails, and line endings
are normalised so the rest of the tool sees tidy text.

PDF and Word support is a stretch goal. Testing the upload logic directly (see
``tests/test_ingest.py``) is deliberate, because Streamlit's ``AppTest`` covers
text inputs and buttons, not the file-upload widget.
"""

from __future__ import annotations

from pathlib import Path

from notice_tool.text import normalize

# Largest upload we will read (1 MB is far more than any real notice needs).
MAX_BYTES = 1_000_000

ALLOWED_SUFFIXES = {".txt", ".md"}

# Tried in order. ``utf-8-sig`` first so a byte-order mark is stripped;
# ``latin-1`` never fails, so it is the final safety net.
ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


class UploadError(ValueError):
    """Raised when an upload is the wrong type, too large, or unreadable."""


def _decode(data: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def ingest_bytes(filename: str, data: bytes) -> str:
    """Validate and clean uploaded bytes, returning normalised notice text."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        shown = suffix or filename or "(no name)"
        raise UploadError(f"Unsupported file type '{shown}'. Please upload a .txt or .md file.")
    if len(data) > MAX_BYTES:
        raise UploadError(
            f"File is too large ({len(data)} bytes). The limit is {MAX_BYTES} bytes."
        )
    return normalize(_decode(data))


def ingest_path(path: str | Path) -> str:
    """Read a file from disk and return normalised notice text."""
    path = Path(path)
    return ingest_bytes(path.name, path.read_bytes())
