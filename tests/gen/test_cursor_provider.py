# SPDX-License-Identifier: Apache-2.0
"""Offline tests for the cursor image provider."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from sprite_gen import gen
from sprite_gen.gen import base as gen_base
from sprite_gen.gen import cursor_bridge, cursor_openai, cursor_provider
from sprite_gen.gen.base import GenRequest


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), (10, 20, 30, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_list_models_prints_cursor_catalog() -> None:
    assert gen.run(list_models=True, out=None, prompt="ignored", report=None) == 0


def test_cursor_provider_declares_native_transparency() -> None:
    assert cursor_provider.CursorProvider.transparency == gen_base.TRANSPARENCY_NATIVE


def test_cursor_bridge_complete_copies_png(tmp_path: Path, monkeypatch) -> None:
    bridge_root = tmp_path / "bridge"
    monkeypatch.setenv(cursor_bridge.BRIDGE_DIR_ENV, str(bridge_root))
    raw = tmp_path / "raw.png"
    source = tmp_path / "generated.png"
    source.write_bytes(_png_bytes())
    job_id = cursor_bridge.submit_bridge_job({"raw": str(raw), "prompt": "knight"})
    assert cursor_bridge.complete_bridge_job(job_id, source) == 0
    assert raw.read_bytes() == source.read_bytes()
    assert not (bridge_root / "inbox" / f"{job_id}.json").exists()


def test_cursor_openai_generation_writes_png(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(cursor_openai.OPENAI_API_KEY_ENV, "test-key")
    payload = {"data": [{"b64_json": base64.b64encode(_png_bytes()).decode()}]}
    captured: dict[str, object] = {}

    class _Response:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(cursor_openai, "urlopen", fake_urlopen)
    destination = tmp_path / "out.png"
    meta = cursor_openai.generate_openai_image(
        prompt="a fox",
        destination=destination,
        refs=[],
        model="gpt-image-2",
        aspect_ratio="1:1",
        quality="medium",
        native_alpha=False,
    )
    assert destination.read_bytes()[:8] == gen_base.PNG_MAGIC
    assert meta["model"] == "gpt-image-2"
    assert captured["url"].endswith("/images/generations")


def test_cursor_provider_openai_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(cursor_bridge.TRANSPORT_ENV, cursor_bridge.TRANSPORT_OPENAI)

    def fake_generate(**kwargs):
        Path(kwargs["destination"]).write_bytes(_png_bytes())
        return {"transport": "openai", "model": "gpt-image-2"}

    monkeypatch.setattr(cursor_provider, "generate_openai_image", fake_generate)
    run = cursor_provider.CursorProvider().generate(
        GenRequest(prompt="knight", raw=tmp_path / "raw.png", model="gpt-image-2"),
        tmp_path,
    )
    assert run.provider == "cursor"
    assert run.model == "gpt-image-2"


def test_unknown_cursor_model_fails_loud() -> None:
    with pytest.raises(SystemExit, match="unknown model"):
        cursor_provider.CursorProvider().generate(
            GenRequest(prompt="x", raw=Path("raw.png"), model="not-a-model"),
            Path("."),
        )
