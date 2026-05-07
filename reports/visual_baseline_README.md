# Visual Regression Baseline — 吉寶軒 Publish/index.html

Captured: **2026-05-02**  
Source: `http://localhost:8000/index.html` (python3 -m http.server 8000 --directory Publish)  
Tool: Chrome headless CDP (`scripts/take_baseline.py`)

---

## Baseline screenshots

All screenshots are in `tests/visual/baseline/`.  
Each is a viewport-clipped PNG at device-scale-factor 1.

| File | Viewport | Device reference | State |
|---|---|---|---|
| `1920x1080.png` | 1920 × 1080 | Desktop wide (4K/ultrawide) | Normal |
| `1920x1080_modal.png` | 1920 × 1080 | Desktop wide | Modal open (LOT 001) |
| `1440x900.png` | 1440 × 900 | Desktop standard (MacBook 13") | Normal |
| `1440x900_modal.png` | 1440 × 900 | Desktop standard | Modal open (LOT 001) |
| `1024x768.png` | 1024 × 768 | Tablet landscape / small laptop | Normal |
| `1024x768_modal.png` | 1024 × 768 | Tablet landscape | Modal open (LOT 001) |
| `768x1024.png` | 768 × 1024 | iPad portrait | Normal |
| `768x1024_modal.png` | 768 × 1024 | iPad portrait | Modal open (LOT 001) |
| `390x844.png` | 390 × 844 | iPhone 13 / 14 | Normal |
| `390x844_modal.png` | 390 × 844 | iPhone 13 / 14 | Modal open (LOT 001) |

### How to trigger a modal in the page

```js
openModal(0);   // opens the first item (LOT 001)
closeModal();   // closes it
```

---

## Performance baseline (2026-05-02 @ 1440×900)

Collected via `reports/perf_baseline_2026-05-02.json`.

| Metric | Value | Notes |
|---|---|---|
| **FCP** (First Contentful Paint) | **312 ms** | Canvas bg paint; excellent for local |
| **LCP** (Largest Contentful Paint) | — | Canvas element excluded from LCP by spec |
| **DOMInteractive** | 79 ms | JS parsed & DOM ready |
| **domContentLoaded** | 139 ms | DOMContentLoaded fired |
| **loadEvent** | 141 ms | Full page load |
| **Images** | 86 total / 86 with `alt` | 100% alt coverage — accessibility pass |
| **Has Canvas** | true | WebGL/Canvas background active |
| **Total resources** | 89 | link + fetch + css + img |
| **Failed resources** | 5 | GAS fetch + 4 Google Drive thumbnails (require auth / CORS) |

### Thresholds for future CI comparison

| Metric | Warn threshold | Fail threshold |
|---|---|---|
| FCP | > 600 ms | > 1000 ms |
| loadEvent | > 500 ms | > 1500 ms |
| Images with alt | < 86 | — |
| Failed resources | > 5 | > 10 |

---

## Console baseline

Collected via `reports/console_baseline_2026-05-02.json`.

Known expected errors (not regressions):
- `GET .../seedream-*.webp` → 404 — background image not bundled in Publish/
- GAS fetch returns 0 bytes in local mode — expected (no network/auth)
- Google Drive thumbnails blocked — expected (require login)

---

## How to use these baselines for visual diff

### Manual diff (no tooling)

1. Take new screenshots with the same script:
   ```bash
   python3 scripts/take_baseline.py
   # screenshots land in tests/visual/baseline/ (overwrites)
   ```
2. Compare with stored baseline using any image diff tool:
   - Windows: `fc /b old.png new.png` (byte diff only)
   - Python: `from PIL import Image, ImageChops; diff = ImageChops.difference(img1, img2)`
   - CLI: `magick compare -metric PSNR baseline.png new.png diff.png`

### Automated diff (future — add to CI)

```python
# Example pixel-diff check (pytest)
from PIL import Image, ImageChops
import numpy as np

def test_no_visual_regression(viewport="1440x900"):
    baseline = Image.open(f"tests/visual/baseline/{viewport}.png")
    current  = Image.open(f"tests/visual/current/{viewport}.png")
    diff = ImageChops.difference(baseline, current)
    arr = np.array(diff)
    changed_pixels = (arr > 10).any(axis=2).sum()
    assert changed_pixels < 500, f"{changed_pixels} pixels changed (threshold 500)"
```

### When to update the baseline

Update baselines intentionally when:
- A **Tier 1 Council-approved** visual change lands on main
- The content dataset changes significantly (more/fewer LOT cards)
- The background image is finally bundled into Publish/

Run `python3 scripts/take_baseline.py` and commit with message:
```
test(visual): update baseline — <reason>
```

---

## Re-running the capture script

```bash
# Prerequisites: HTTP server running
python3 -m http.server 8000 --directory Publish &

# Run capture (Chrome headless + CDP)
python3 scripts/take_baseline.py

# Outputs:
#   tests/visual/baseline/<viewport>.png        (10 files)
#   reports/perf_baseline_<date>.json
#   reports/console_baseline_<date>.json
```

The script requires:
- `requests` and `websockets` Python packages (already in project env)
- Google Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`
- HTTP server serving Publish/ at port 8000
