#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Reproducible first-run smoke: copy golden fixture → extract → compose.
# No image-generation provider credentials required.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${1:-$ROOT/runs/first-run}"
VENV="$ROOT/.venv"

cd "$ROOT"

if [[ ! -d "$VENV" ]]; then
  echo "[first-run] creating virtualenv at $VENV"
  python3 -m venv "$VENV"
fi

echo "[first-run] pip install -e ."
"$VENV/bin/pip" install -e . -q

echo "[first-run] seeding run dir from tests/fixtures/run → $RUN_DIR"
rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"
cp -r tests/fixtures/run/* "$RUN_DIR/"

echo "[first-run] extract_sprite_row_frames.py"
"$VENV/bin/python" scripts/extract_sprite_row_frames.py --run-dir "$RUN_DIR"

echo "[first-run] compose_sprite_atlas.py"
"$VENV/bin/python" scripts/compose_sprite_atlas.py --run-dir "$RUN_DIR"

for required in sprite-sheet-alpha.png manifest.json frames/frames-manifest.json; do
  if [[ ! -e "$RUN_DIR/$required" ]]; then
    echo "[first-run] ERROR: missing $RUN_DIR/$required" >&2
    exit 1
  fi
done

"$VENV/bin/python" - <<PY
import json
from pathlib import Path
run = Path("$RUN_DIR")
m = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
rows = m["frame_layout"]["rows"]
assert set(rows) == {"idle", "walk"}, rows
assert len(rows["idle"]) == 4 and len(rows["walk"]) == 3
for state, rects in rows.items():
    for r in rects:
        assert {"x", "y", "w", "h"} <= r.keys(), (state, r)
print("[first-run] manifest ok:", {s: len(rows[s]) for s in sorted(rows)})
print("[first-run] atlas:", run / "sprite-sheet-alpha.png")
PY

echo "[first-run] done."
