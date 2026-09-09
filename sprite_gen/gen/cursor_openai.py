# SPDX-License-Identifier: Apache-2.0
"""OpenAI Images API transport for the `cursor` provider (stdlib only)."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .cursor_models import resolve_cursor_model, resolve_cursor_quality, resolve_cursor_size

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def _api_key() -> str:
    key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
    if not key:
        raise SystemExit(
            f"cursor-gen: {OPENAI_API_KEY_ENV} is not set. "
            f"Set it for OpenAI transport, or use {OPENAI_API_KEY_ENV}=... with "
            "SPRITE_GEN_CURSOR_TRANSPORT=bridge and complete jobs via "
            "`sprite-gen cursor-bridge complete`."
        )
    return key


def _base_url() -> str:
    return os.environ.get(OPENAI_BASE_URL_ENV, DEFAULT_OPENAI_BASE_URL).strip().rstrip("/")


def _decode_response_image(payload: dict[str, Any], destination: Path) -> None:
    data = payload.get("data") or []
    if not data:
        raise SystemExit(f"cursor-gen: OpenAI response carried no images: {payload}")
    item = data[0]
    if item.get("b64_json"):
        destination.write_bytes(base64.b64decode(item["b64_json"]))
        return
    url = item.get("url")
    if not url:
        raise SystemExit(f"cursor-gen: OpenAI image item has no b64_json or url: {item}")
    with urlopen(url, timeout=120) as response:
        destination.write_bytes(response.read())


def _post_json(path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        f"{_base_url()}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"cursor-gen: OpenAI HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"cursor-gen: OpenAI request failed: {exc}") from exc


def _multipart_body(fields: list[tuple[str, str]], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = f"----sprite-gen-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")
    for field_name, path in files:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'.encode()
        )
        chunks.append(f"Content-Type: {mime}\r\n\r\n".encode())
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def _post_multipart(path: str, fields: list[tuple[str, str]], files: list[tuple[str, Path]]) -> dict[str, Any]:
    body, boundary = _multipart_body(fields, files)
    request = Request(
        f"{_base_url()}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"cursor-gen: OpenAI HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"cursor-gen: OpenAI request failed: {exc}") from exc


def generate_openai_image(
    *,
    prompt: str,
    destination: Path,
    refs: list[Path],
    model: str | None,
    aspect_ratio: str | None,
    quality: str | None,
    native_alpha: bool,
) -> dict[str, Any]:
    """Call OpenAI Images API and write the PNG to destination."""
    resolved_model = resolve_cursor_model(model)
    resolved_quality = resolve_cursor_quality(quality)
    size = resolve_cursor_size(resolved_model, aspect_ratio)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if refs:
        fields = [
            ("model", resolved_model),
            ("prompt", prompt),
            ("size", size),
            ("quality", resolved_quality),
            ("n", "1"),
        ]
        if native_alpha:
            fields.append(("background", "transparent"))
        file_fields = [("image[]", path) for path in refs]
        payload = _post_multipart("/images/edits", fields, file_fields)
    else:
        body: dict[str, Any] = {
            "model": resolved_model,
            "prompt": prompt,
            "size": size,
            "quality": resolved_quality,
            "n": 1,
        }
        if native_alpha:
            body["background"] = "transparent"
        payload = _post_json("/images/generations", body)

    _decode_response_image(payload, destination)
    return {
        "transport": "openai",
        "model": resolved_model,
        "quality": resolved_quality,
        "size": size,
        "endpoint": "/images/edits" if refs else "/images/generations",
        "refs": [str(p) for p in refs],
    }
