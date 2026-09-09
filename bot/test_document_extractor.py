#!/usr/bin/env python3
"""Unit tests for document extractor fallback helpers."""

import binascii
import os
import sys

import pytest


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_extractor import _decode_base64, _fallback_text, _meaningful_len  # noqa: E402


@pytest.mark.scenario("document-extraction.fallback_text_format")
def test_fallback_text_format():
    assert _fallback_text("x") == "[document metadata: filename=x]"
    assert _fallback_text("x", path="/tmp/x.docx") == (
        "[document metadata: filename=x, path=/tmp/x.docx]"
    )
    assert _fallback_text("x", data_length=123) == (
        "[document metadata: filename=x, bytes=123]"
    )
    assert _fallback_text("") == "[document metadata: filename=document]"


@pytest.mark.scenario("document-extraction.meaningful_len_ignores_whitespace")
def test_meaningful_len_ignores_whitespace():
    assert _meaningful_len("a b  c") == 3
    assert _meaningful_len("  \n\t") == 0
    assert _meaningful_len("") == 0
    assert _meaningful_len("x" * 10) == 10


@pytest.mark.scenario("document-extraction.decode_base64_data_uri")
def test_decode_base64_data_uri():
    assert _decode_base64("data:image/png;base64,AAAA") == b"\x00\x00\x00"
    assert _decode_base64("AAAA") == b"\x00\x00\x00"
    assert _decode_base64("") == b""
    assert _decode_base64("data:mime;base64,") == b""
    with pytest.raises(binascii.Error, match="Incorrect padding"):
        _decode_base64("AA!A")
