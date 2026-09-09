# SPDX-License-Identifier: Apache-2.0
"""Cursor-compatible image generation provider.

Two transports, selected by `SPRITE_GEN_CURSOR_TRANSPORT`:

- `openai` (default): OpenAI Images API with the GPT Image model family that
  powers Cursor's GenerateImage tool (`gpt-image-2`, `gpt-image-1.5`, …).
  Requires `OPENAI_API_KEY`.

- `bridge`: write a job file and wait for a Cursor agent (or human) to run
  GenerateImage and complete it with `sprite-gen cursor-bridge complete`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .base import TRANSPARENCY_NATIVE, GenRequest, ProviderRun, verify_png
from .cursor_bridge import (
    TRANSPORT_BRIDGE,
    TRANSPORT_OPENAI,
    resolve_cursor_transport,
    submit_bridge_job,
    wait_bridge_job,
)
from .cursor_models import resolve_cursor_model
from .cursor_openai import generate_openai_image


class CursorProvider:
    """Generate one image through Cursor-compatible GPT Image backends."""

    name = "cursor"
    # gpt-image models can return real alpha when `background=transparent` is set.
    transparency = TRANSPARENCY_NATIVE

    def __init__(self, *, quality: str | None = None) -> None:
        self._quality = quality

    def generate(self, request: GenRequest, workdir: Path) -> ProviderRun:
        started = time.monotonic()
        transport = resolve_cursor_transport()
        model = resolve_cursor_model(request.model)

        if transport == TRANSPORT_OPENAI:
            extra = generate_openai_image(
                prompt=request.prompt,
                destination=request.raw,
                refs=list(request.refs),
                model=model,
                aspect_ratio=request.aspect_ratio,
                quality=self._quality,
                native_alpha=request.native_alpha,
            )
        else:
            job_id = submit_bridge_job({
                "prompt": request.prompt,
                "raw": str(request.raw),
                "refs": [str(p) for p in request.refs],
                "model": model,
                "aspect_ratio": request.aspect_ratio,
                "quality": self._quality,
                "native_alpha": request.native_alpha,
            })
            print(
                f"[cursor] bridge job {job_id} queued — run GenerateImage in Cursor, then:\n"
                f"  sprite-gen cursor-bridge complete --job-id {job_id} --from <generated.png>",
                file=sys.stderr,
            )
            result = wait_bridge_job(job_id)
            extra = {
                "transport": TRANSPORT_BRIDGE,
                "job_id": job_id,
                "bridge_source": result.get("source"),
            }

        verify_png(request.raw)
        elapsed = time.monotonic() - started
        return ProviderRun(
            provider=self.name,
            elapsed_seconds=elapsed,
            model=model,
            session_id=extra.get("job_id"),
            extra=extra,
        )
