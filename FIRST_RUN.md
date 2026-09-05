# First run on this fork (idle + walk)

This document records a verified end-to-end pipeline run on **FaberVi/sprite-gen**
using the checked-in golden fixture (`tests/fixtures/run/`). The fixture path
produces `sprite-sheet-alpha.png` and `manifest.json` with **idle** (4 frames) and
**walk** (3 frames) without any image-generation provider credentials.

For the full contract (stage I/O, run-dir layout), see [`docs/run-contract.md`](docs/run-contract.md).

## Prerequisites

- CPython 3.10+ with `venv` support (`python3 -m venv` must work)
- On Debian/Ubuntu, if venv creation fails: `sudo apt install python3-venv`

## One-command fixture run (no provider auth)

From the repository root:

```bash
./scripts/first_run_fixture.sh
```

Or run the steps manually:

```bash
# 0. fresh virtualenv + install
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

# 1. seed a run dir from the golden fixture (idle + walk raw strips + request)
mkdir -p runs/first-run
cp -r tests/fixtures/run/* runs/first-run/

# 2. extract transparent frames from each raw row strip
python3 scripts/extract_sprite_row_frames.py --run-dir runs/first-run

# 3. bake the runtime atlas + manifest
python3 scripts/compose_sprite_atlas.py --run-dir runs/first-run
```

### Expected outputs

After a successful run, `runs/first-run/` contains at minimum:

| Path | Role |
|---|---|
| `raw/idle.png`, `raw/walk.png` | horizontal row strips (fixture inputs) |
| `frames/idle/frame-*.png` | 4 extracted transparent frames |
| `frames/walk/frame-*.png` | 3 extracted transparent frames |
| `frames/frames-manifest.json` | per-row extract report (`ok: true`) |
| `sprite-sheet-alpha.png` | transparent runtime atlas |
| `manifest.json` | runtime SSoT with `frame_layout` absolute rects |

Sanity-check the manifest:

```bash
python3 - <<'PY'
import json
from pathlib import Path
m = json.loads(Path("runs/first-run/manifest.json").read_text())
rows = m["frame_layout"]["rows"]
assert set(rows) == {"idle", "walk"}
assert len(rows["idle"]) == 4 and len(rows["walk"]) == 3
for state, rects in rows.items():
    for r in rects:
        assert {"x", "y", "w", "h"} <= r.keys()
print("manifest ok:", list(rows), "frame counts:", {s: len(rows[s]) for s in rows})
PY
```

## Full pipeline with a real character (providers required)

When Codex (`codex login`) or Grok (xAI OAuth via `grok`) is available, start from
your own `base.png` instead of the fixture:

```bash
source .venv/bin/activate
RUN=runs/my-character

# 1. prepare run dir (writes sprite-request.json, layout guides, prompts)
python3 scripts/prepare_sprite_run.py \
  --out-dir "$RUN" \
  --character-id my-character \
  --base-image path/to/base.png \
  --states idle walk

# 2. generate one row strip per state (repeat per state; refs lock identity)
python3 scripts/generate_sprite_image.py --provider codex \
  --prompt-file "$RUN/prompts/idle.txt" \
  --out "$RUN/raw/idle.png" \
  --ref "$RUN/base-source.png" \
  --ref "$RUN/references/layout-guides/idle.png"

python3 scripts/generate_sprite_image.py --provider codex \
  --prompt-file "$RUN/prompts/walk.txt" \
  --out "$RUN/raw/walk.png" \
  --ref "$RUN/base-source.png" \
  --ref "$RUN/references/layout-guides/walk.png"

# 3–4. same extract + compose as the fixture path
python3 scripts/extract_sprite_row_frames.py --run-dir "$RUN"
python3 scripts/compose_sprite_atlas.py --run-dir "$RUN"
```

Provider details and auth: [`docs/gen.md`](docs/gen.md).

**This environment:** `sprite-gen gen --provider codex` fails with
`Codex state root does not exist` (no `~/.codex` / ChatGPT OAuth). Use the fixture
path above for a credential-free first run; switch to the full path once providers
are configured locally.

## Optional next steps

```bash
# motion QA GIFs / contact sheets
python3 scripts/preview_animation.py --run-dir runs/first-run

# curation webview (frame picks, transforms — non-destructive sidecar)
python3 scripts/serve_curation.py --run-dir runs/first-run
```

## Verify tests still pass

```bash
pip install -e ".[dev]"
python -m pytest tests/packaging/test_pipeline_smoke.py -q
```
