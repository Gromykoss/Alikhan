#!/usr/bin/env python3
"""Local-only document text extractor for Alikhan.

The live WAHA bot currently posts base64/file_name. Other health and workflow
paths expect path/filename/chat_id/sender, so this service accepts both shapes.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = 8099
MAX_BODY_BYTES = 80 * 1024 * 1024
PREVIEW_CHARS = 500


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _clean_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r", "\n").splitlines()).strip()


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_xlsx(file_obj: io.BytesIO | str) -> str:
    try:
        import openpyxl
    except Exception as exc:
        return f"[extractor: openpyxl unavailable for spreadsheet extraction: {type(exc).__name__}]"

    workbook = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    parts: list[str] = []
    try:
        for sheet in workbook.worksheets:
            parts.append(f"### Sheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                cells = [_cell_text(value) for value in row]
                while cells and not cells[-1]:
                    cells.pop()
                if any(cells):
                    parts.append("\t".join(cells))
    finally:
        workbook.close()
    return _clean_text("\n".join(parts))


def _extract_pdf(file_obj: io.BytesIO | str) -> str:
    try:
        import pdfplumber
    except Exception:
        pdfplumber = None

    if pdfplumber is not None:
        try:
            with pdfplumber.open(file_obj) as pdf:
                return _clean_text("\n".join(page.extract_text() or "" for page in pdf.pages))
        except Exception as exc:
            return f"[extractor: pdfplumber failed: {type(exc).__name__}]"

    try:
        from pypdf import PdfReader
    except Exception as exc:
        return f"[extractor: PDF extraction unavailable: {type(exc).__name__}]"

    try:
        reader = PdfReader(file_obj)
        return _clean_text("\n".join(page.extract_text() or "" for page in reader.pages))
    except Exception as exc:
        return f"[extractor: pypdf failed: {type(exc).__name__}]"


def _fallback_text(filename: str, data_length: int | None = None, path: str | None = None) -> str:
    details = [f"filename={filename or 'document'}"]
    if path:
        details.append(f"path={path}")
    if data_length is not None:
        details.append(f"bytes={data_length}")
    return "[document metadata: " + ", ".join(details) + "]"


def _decode_base64(value: str) -> bytes:
    if "," in value and value.lstrip().startswith("data:"):
        value = value.split(",", 1)[1]
    return base64.b64decode(value, validate=False)


def extract_document(payload: dict[str, Any]) -> dict[str, Any]:
    filename = str(payload.get("filename") or payload.get("file_name") or "").strip()
    path = str(payload.get("path") or "").strip()
    b64 = payload.get("base64")

    raw_bytes: bytes | None = None
    source: io.BytesIO | str | None = None
    size: int | None = None

    if isinstance(b64, str) and b64.strip():
        try:
            raw_bytes = _decode_base64(b64.strip())
        except (binascii.Error, ValueError) as exc:
            text = f"[extractor: invalid base64: {type(exc).__name__}]"
            return _result(False, filename, text, "invalid_base64")
        source = io.BytesIO(raw_bytes)
        size = len(raw_bytes)
    elif path:
        file_path = Path(path).expanduser()
        if not file_path.exists() or not file_path.is_file():
            text = _fallback_text(filename or file_path.name, path=path)
            return _result(False, filename or file_path.name, text, "file_not_found")
        if not filename:
            filename = file_path.name
        source = str(file_path)
        try:
            size = file_path.stat().st_size
        except OSError:
            size = None
    else:
        text = _fallback_text(filename)
        return _result(False, filename, text, "missing_path_or_base64")

    ext = os.path.splitext(filename or path)[1].lower()
    try:
        if ext in {".xlsx", ".xlsm"}:
            text = _extract_xlsx(source)
        elif ext == ".pdf":
            text = _extract_pdf(source)
        else:
            text = _fallback_text(filename, size, path or None)
    except Exception as exc:
        text = f"[extractor: failed to read {filename or 'document'}: {type(exc).__name__}]"
        return _result(False, filename, text, "extract_failed")

    if not text:
        text = _fallback_text(filename, size, path or None)
    return _result(True, filename, text)


def _result(ok: bool, filename: str, text: str, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "filename": filename,
        "text": text,
        "content": text,
        "text_length": len(text),
        "text_preview": text[:PREVIEW_CHARS],
    }
    if error:
        payload["error"] = error
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "AlikhanDocumentExtractor/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[document-extractor] {self.address_string()} {fmt % args}", flush=True)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            _json_response(self, 200, {"ok": True})
            return
        _json_response(self, 404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/extract-document":
            _json_response(self, 404, {"ok": False, "error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            _json_response(self, 400, {"ok": False, "error": "invalid_content_length"})
            return

        if length <= 0 or length > MAX_BODY_BYTES:
            _json_response(self, 413, {"ok": False, "error": "invalid_body_size"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            _json_response(self, 400, {"ok": False, "error": "invalid_json"})
            return

        if not isinstance(payload, dict):
            _json_response(self, 400, {"ok": False, "error": "json_object_required"})
            return

        _json_response(self, 200, extract_document(payload))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[document-extractor] listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
