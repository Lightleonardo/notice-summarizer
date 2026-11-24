"""Tests for notice_tool.ingest - turning an upload into clean text."""

import pytest

from notice_tool.ingest import MAX_BYTES, UploadError, ingest_bytes, ingest_path


def test_reads_utf8_text():
    data = "Dear Parents, please come.".encode("utf-8")
    assert ingest_bytes("notice.txt", data) == "Dear Parents, please come."


def test_reads_markdown():
    assert ingest_bytes("notice.md", b"# Heading") == "# Heading"


def test_falls_back_to_another_encoding():
    text = "Café résumé"
    data = text.encode("cp1252")  # not valid UTF-8
    assert ingest_bytes("notice.txt", data) == text


def test_strips_a_utf8_byte_order_mark():
    data = "Hello".encode("utf-8-sig")
    assert ingest_bytes("notice.txt", data) == "Hello"


def test_normalises_line_endings():
    assert ingest_bytes("notice.txt", b"a\r\nb") == "a\nb"


def test_rejects_unsupported_file_type():
    with pytest.raises(UploadError):
        ingest_bytes("notice.pdf", b"%PDF-1.4")


def test_rejects_oversized_file():
    with pytest.raises(UploadError):
        ingest_bytes("big.txt", b"x" * (MAX_BYTES + 1))


def test_ingest_path(tmp_path):
    path = tmp_path / "notice.txt"
    path.write_bytes(b"Hello\r\nWorld")
    assert ingest_path(path) == "Hello\nWorld"
