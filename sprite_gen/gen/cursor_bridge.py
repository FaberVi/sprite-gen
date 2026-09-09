# SPDX-License-Identifier: Apache-2.0
"""File-queue bridge between `sprite-gen gen --provider cursor` and Cursor IDE.

When `SPRITE_GEN_CURSOR_TRANSPORT=bridge`, the cursor provider writes a job JSON
into `inbox/` and waits for `outbox/<job-id>.json` to appear. A Cursor agent (or
a human) completes the job by calling GenerateImage, then:

    sprite-gen cursor-bridge complete --job-id <id> --from <generated.png>

This path exists for environments where OPENAI_API_KEY is unavailable but the
Cursor IDE GenerateImage tool is.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from sprite_gen.spec.runio import atomic_write_text

from .base import GEN_TIMEOUT_SECONDS, GenTimeoutError

BRIDGE_DIR_ENV = "SPRITE_GEN_CURSOR_BRIDGE_DIR"
TRANSPORT_ENV = "SPRITE_GEN_CURSOR_TRANSPORT"
TRANSPORT_OPENAI = "openai"
TRANSPORT_BRIDGE = "bridge"


def resolve_bridge_dir() -> Path:
    configured = os.environ.get(BRIDGE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".sprite-gen" / "cursor-bridge").resolve()


def resolve_cursor_transport() -> str:
    mode = os.environ.get(TRANSPORT_ENV, TRANSPORT_OPENAI).strip().lower()
    if mode not in (TRANSPORT_OPENAI, TRANSPORT_BRIDGE):
        raise SystemExit(
            f"cursor-gen: {TRANSPORT_ENV}={mode!r} is invalid; expected "
            f"'{TRANSPORT_OPENAI}' or '{TRANSPORT_BRIDGE}'"
        )
    return mode


def bridge_dirs(root: Path) -> tuple[Path, Path, Path]:
    inbox = root / "inbox"
    outbox = root / "outbox"
    for path in (inbox, outbox):
        path.mkdir(parents=True, exist_ok=True)
    return root, inbox, outbox


def submit_bridge_job(payload: dict[str, Any]) -> str:
    root, inbox, _outbox = bridge_dirs(resolve_bridge_dir())
    job_id = str(payload.get("id") or uuid.uuid4())
    payload = {**payload, "id": job_id}
    atomic_write_text(inbox / f"{job_id}.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return job_id


def wait_bridge_job(job_id: str, *, timeout_seconds: int = GEN_TIMEOUT_SECONDS) -> dict[str, Any]:
    root, _inbox, outbox = bridge_dirs(resolve_bridge_dir())
    inbox_file = root / "inbox" / f"{job_id}.json"
    outbox_file = outbox / f"{job_id}.json"
    started = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        if outbox_file.is_file():
            data = json.loads(outbox_file.read_text(encoding="utf-8"))
            if not data.get("ok"):
                raise SystemExit(f"cursor-gen bridge job {job_id} failed: {data.get('error', data)}")
            return data
        time.sleep(0.5)
    raise GenTimeoutError(
        f"cursor-gen: bridge job {job_id} did not complete within {timeout_seconds}s. "
        f"Job file: {inbox_file}. Complete it with:\n"
        f"  sprite-gen cursor-bridge complete --job-id {job_id} --from <path-to-png>"
    )


def complete_bridge_job(job_id: str, source: Path) -> int:
    root, inbox, outbox = bridge_dirs(resolve_bridge_dir())
    job_file = inbox / f"{job_id}.json"
    if not job_file.is_file():
        raise SystemExit(f"cursor-bridge: no pending job {job_id!r} in {inbox}")
    source = source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"cursor-bridge: source image not found: {source}")
    job = json.loads(job_file.read_text(encoding="utf-8"))
    destination = Path(str(job["raw"])).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    payload = {
        "ok": True,
        "job_id": job_id,
        "source": str(source),
        "raw": str(destination),
    }
    atomic_write_text(outbox / f"{job_id}.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    job_file.unlink(missing_ok=True)
    return 0


def list_bridge_jobs() -> int:
    root, inbox, outbox = bridge_dirs(resolve_bridge_dir())
    pending = sorted(inbox.glob("*.json"))
    done = sorted(outbox.glob("*.json"))
    print(json.dumps({
        "bridge_dir": str(root),
        "pending": [p.stem for p in pending],
        "completed": [p.stem for p in done],
    }, ensure_ascii=False, indent=2))
    return 0


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--list", action="store_true", help="list pending and completed bridge jobs")
    parser.add_argument("--job-id", help="bridge job id to complete")
    parser.add_argument("--from", dest="source", type=Path, help="generated PNG to copy into the job raw path")


def run(**kwargs: object) -> int:
    if kwargs.get("list"):
        return list_bridge_jobs()
    job_id = kwargs.get("job_id")
    source = kwargs.get("source")
    if job_id and source:
        return complete_bridge_job(str(job_id), Path(str(source)))
    raise SystemExit("cursor-bridge: pass --list or both --job-id and --from")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sprite-gen cursor-bridge")
    add_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return run(**vars(args))


if __name__ == "__main__":
    raise SystemExit(main())
