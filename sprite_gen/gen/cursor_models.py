# SPDX-License-Identifier: Apache-2.0
"""Cursor-compatible image model registry for the `cursor` generation provider.

These are the GPT Image family models exposed by Cursor's GenerateImage tool and
the OpenAI Images API. The `cursor` provider uses the same model IDs for both
transport modes (OpenAI API and IDE bridge).
"""

from __future__ import annotations

import os

# Model IDs accepted by --model and recorded in generation reports.
CURSOR_IMAGE_MODELS: tuple[str, ...] = (
    "gpt-image-2",
    "gpt-image-1.5",
    "gpt-image-1",
    "gpt-image-1-mini",
)

DEFAULT_CURSOR_MODEL = os.environ.get("SPRITE_GEN_CURSOR_DEFAULT_MODEL", "gpt-image-2").strip() or "gpt-image-2"

CURSOR_QUALITIES: tuple[str, ...] = ("low", "medium", "high")
DEFAULT_CURSOR_QUALITY = os.environ.get("SPRITE_GEN_CURSOR_QUALITY", "medium").strip() or "medium"

# Aspect ratios supported by GenerateImage and mapped to OpenAI `size` values.
CURSOR_ASPECT_RATIOS: tuple[str, ...] = ("1:1", "4:3", "3:4", "16:9", "9:16")

# gpt-image-1.x fixed sizes (OpenAI Images API).
_ASPECT_TO_SIZE_LEGACY: dict[str, str] = {
    "1:1": "1024x1024",
    "4:3": "1536x1024",
    "3:4": "1024x1536",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
}

# gpt-image-2 accepts the same named sizes today; custom sizes are a follow-up.
_ASPECT_TO_SIZE_GPT_IMAGE_2: dict[str, str] = dict(_ASPECT_TO_SIZE_LEGACY)


def resolve_cursor_model(model: str | None) -> str:
    """Return a validated model id, or fail loud."""
    chosen = (model or DEFAULT_CURSOR_MODEL).strip()
    if chosen not in CURSOR_IMAGE_MODELS:
        raise SystemExit(
            f"cursor-gen: unknown model {chosen!r}; expected one of {', '.join(CURSOR_IMAGE_MODELS)}. "
            "Pass --list-models to print the catalog."
        )
    return chosen


def resolve_cursor_quality(quality: str | None) -> str:
    chosen = (quality or DEFAULT_CURSOR_QUALITY).strip()
    if chosen not in CURSOR_QUALITIES:
        raise SystemExit(
            f"cursor-gen: unknown quality {chosen!r}; expected one of {', '.join(CURSOR_QUALITIES)}"
        )
    return chosen


def resolve_cursor_size(model: str, aspect_ratio: str | None) -> str:
    ratio = (aspect_ratio or "1:1").strip()
    if ratio not in CURSOR_ASPECT_RATIOS:
        raise SystemExit(
            f"cursor-gen: unknown aspect ratio {ratio!r}; expected one of {', '.join(CURSOR_ASPECT_RATIOS)}"
        )
    table = _ASPECT_TO_SIZE_GPT_IMAGE_2 if model == "gpt-image-2" else _ASPECT_TO_SIZE_LEGACY
    return table[ratio]
