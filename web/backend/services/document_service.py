"""Pull readable text out of an uploaded Word or PDF document.

The prediction page takes pasted text and the link page takes a URL. This covers the
third way a Somali document actually reaches a reader: as a file. Only Word (.docx) and
PDF are accepted, because those are the two formats the classifier can be given a fair
chance on -- a spreadsheet or an image carries no continuous prose, and a plain rename
of one to `.docx` would otherwise reach the parser and fail there instead of here.

Two checks run before any parsing:

  * The extension must be `.docx` or `.pdf`.
  * The first bytes must match that format -- `PK\\x03\\x04` for the ZIP container Word
    uses, `%PDF-` for PDF. Extension alone is a claim the uploader makes; the signature
    is the file itself, and rejecting on it keeps a renamed `.exe` from being parsed.

`.doc` (the pre-2007 binary format) is refused with a message that says how to convert,
because reading it would need Word itself rather than a library.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

# The text a document holds is unlimited; the file that carries it is not. 100 MB is
# far beyond any prose document -- a 400-page thesis with figures runs to a few MB --
# and the bound exists only so a mis-aimed upload fails fast instead of being read into
# memory whole. It is a guard against accident, not a quota on the user.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

ACCEPTED_EXTENSIONS = {".docx", ".pdf"}
ACCEPTED_LABEL = "Word (.docx) or PDF (.pdf)"

_SIGNATURES = {
    ".docx": b"PK\x03\x04",
    ".pdf": b"%PDF-",
}

_WHITESPACE = re.compile(r"[ \t ]+")
_BLANK_RUNS = re.compile(r"\n{3,}")


class DocumentError(Exception):
    """The upload was rejected, or held no readable text."""


def _normalise(blocks: list[str]) -> str:
    """Join extracted blocks into prose with paragraph breaks preserved.

    Paragraph structure is kept because the caller may split on it -- collapsing the
    document to one line would cost the link-analysis path its per-paragraph view.
    """
    cleaned = []
    for block in blocks:
        block = _WHITESPACE.sub(" ", block).strip()
        if block:
            cleaned.append(block)
    return _BLANK_RUNS.sub("\n\n", "\n\n".join(cleaned)).strip()


def _extract_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise DocumentError("Word support is not installed on this server") from exc

    try:
        document = docx.Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise DocumentError(
            "That file could not be opened as a Word document. It may be corrupt, or "
            "saved in the older .doc format."
        ) from exc

    blocks = [p.text for p in document.paragraphs]
    # Tables hold real prose in many report templates, so their cells count too; a
    # document that puts its body in a single-cell table would otherwise read as empty.
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                blocks.extend(p.text for p in cell.paragraphs)
    return _normalise(blocks)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise DocumentError("PDF support is not installed on this server") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - pypdf raises a wide range on bad input
        raise DocumentError("That file could not be opened as a PDF. It may be corrupt.") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")  # many PDFs are "encrypted" with an empty owner password
        except Exception as exc:  # noqa: BLE001
            raise DocumentError(
                "That PDF is password-protected. Remove the password and try again."
            ) from exc

    blocks = []
    for page in reader.pages:
        try:
            blocks.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a single bad page must not lose the rest
            logger.warning("a PDF page could not be read; continuing with the others")
    text = _normalise(blocks)
    if not text:
        raise DocumentError(
            "No text could be read from that PDF. Scanned pages are images, so they "
            "hold no text to extract — a text-based PDF is needed."
        )
    return text


def extract(filename: str, data: bytes) -> tuple[str, str]:
    """Return (extension, text) for an accepted upload, or raise DocumentError.

    Rejection happens before parsing so an unsupported file never reaches a parser.
    """
    if not data:
        raise DocumentError("That file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError(
            f"That file is {len(data) / 1024 / 1024:.1f} MB. The limit is "
            f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB."
        )

    suffix = Path(filename or "").suffix.lower()
    if suffix == ".doc":
        raise DocumentError(
            "The old .doc format cannot be read. Open it in Word and use "
            "File → Save As → Word Document (.docx), then upload that."
        )
    if suffix not in ACCEPTED_EXTENSIONS:
        raise DocumentError(f"Only {ACCEPTED_LABEL} files are accepted.")

    # The signature is the file; the extension is only what the uploader called it.
    if not data.startswith(_SIGNATURES[suffix]):
        raise DocumentError(
            f"That file is named {suffix} but its contents are not a "
            f"{'Word document' if suffix == '.docx' else 'PDF'}. "
            f"Only genuine {ACCEPTED_LABEL} files are accepted."
        )

    text = _extract_docx(data) if suffix == ".docx" else _extract_pdf(data)
    if not text:
        raise DocumentError("No readable text was found in that document.")
    return suffix, text
