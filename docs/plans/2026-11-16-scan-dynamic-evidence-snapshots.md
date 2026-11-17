# Implementation Plan — Dynamic Scroll & Focused Evidence Snapshots for `/scan`

> **Feature Area:** `server/api/main.py`, `server/aegis/schemas.py`, `web/app/(console)/scan/page.tsx`  
> **Scope:** `/scan` only (read-only URL scanner). Never touches the live agent loop or paired arena runs.  
> **Constraint:** Preserves `<details>` integrity (T04 signal) and maintains backward compatibility with `screenshot_b64`.

---

## 1. Goal & Architecture Overview

Currently, `/scan` loads a URL, waits 2.5 seconds at the top of the page, and captures a single viewport screenshot (`1280 × 720`). If an element is located below the fold (e.g. at `y = 1,800px`), it is detected by `snapshot.js` and listed in the text feed, but it cannot be highlighted with a red box because the camera never photographed that section.

### The Solution: Two-Part Targeted Upgrade
1. **Scroll-to-Bottom Flick:**
   Before snapshotting, the browser scrolls to the bottom (`document.body.scrollHeight`), waits 500 ms for scroll-activated scripts, lazy-loaded components, or scroll-triggered popups to fire, and scrolls back to `(0, 0)`.
   * *Safety rule:* Does **not** auto-expand `<details>` (preserving the collapsed-fee detection signal for T04).
2. **Focused Evidence Snapshots:**
   Instead of an unwieldy 20,000-pixel continuous image, the scanner identifies any flagged elements located outside the first screen (`y > 700px`). It groups them into at most **2 additional focused screens**, scrolls directly to their scroll offsets, and captures clean `1280 × 720` viewport screenshots with correctly aligned red bounding boxes.
3. **Evidence Switcher UI:**
   The scan result displays a clean tab bar (`Screen 1: Top (Overview)`, `Screen 2: Scrolled to Footer`). Clicking a screen or clicking a finding in the list immediately displays the corresponding screenshot with its red boxes.

---

## 2. Technical Architecture & Data Contract

### Schema Changes (`server/aegis/schemas.py`)
Add `ScanScreen` and attach `screens` to `ScanReport`:

```python
class ScanScreen(BaseModel):
    id: str  # e.g. "screen_0", "screen_1"
    title: str  # e.g. "Top of page" or "Scrolled to 1,450px"
    scroll_y: int
    screenshot_b64: str
    element_ids: list[str]  # IDs of flagged elements visible in this viewport

class ScanReport(BaseModel):
    # Existing fields remain identical for 100% backward compatibility:
    url: str
    final_url: str
    title: str
    findings: list[Finding]
    notes: list[Finding]
    flagged: list[Element]
    element_count: int
    screenshot_b64: str  # Always holds Screen 0 (legacy & fallback)
    detector_ms: int
    elapsed_ms: int
    blocked_requests: int
    # New additive field:
    screens: list[ScanScreen] = Field(default_factory=list)
```

---

## 3. Step-by-Step Implementation Tasks

### Task 1: Schema Updates
* **File:** `server/aegis/schemas.py`
* Add `ScanScreen` model.
* Add `screens: list[ScanScreen] = Field(default_factory=list)` to `ScanReport`.
* Regenerate OpenAPI contract:
  ```bash
  python -c "import json; from api.main import app; print(json.dumps(app.openapi()))" > openapi.json
  npx openapi-typescript openapi.json -o web/lib/api-types.ts
  ```

### Task 2: Backend Scroll Flick & Targeted Evidence Capture
* **File:** `server/api/main.py` (in `async def scan`)
* **Step 2.1 (Pre-scan scroll flick):**
  ```python
  # Trigger scroll-activated scripts, lazy-loaders, and scroll popups
  await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
  await page.wait_for_timeout(500)
  await page.evaluate("window.scrollTo(0, 0)")
  await page.wait_for_timeout(200)
  ```
* **Step 2.2 (Take primary snapshot and run detectors):**
  * `snap = await take_snapshot(page)`
  * `findings = run_fast(snap, None, None)`
  * `shot0 = await screenshot_b64(page)`
* **Step 2.3 (Identify off-screen flagged elements):**
  * Find elements associated with non-note findings where `bbox[1] > 700`.
  * Cluster `y` coordinates into at most 2 distinct target offsets (e.g. `scroll_y = int(e.bbox[1] - 80)`).
* **Step 2.4 (Capture focused evidence screens):**
  * For each target `scroll_y`:
    * `await page.evaluate(f"window.scrollTo(0, {scroll_y})")`
    * `await page.wait_for_timeout(150)`
    * `shot = await screenshot_b64(page)`
    * Record `ScanScreen` with visible element IDs.
  * Restore scroll to `(0, 0)`: `await page.evaluate("window.scrollTo(0, 0)")`.

### Task 3: Frontend Evidence Switcher in `/scan`
* **File:** `web/app/(console)/scan/page.tsx`
* **Step 3.1:** Add state `activeScreenIndex: number` (default 0).
* **Step 3.2:** If `report.screens.length > 1`, render a chip switcher bar above the browser frame:
  ```tsx
  <div className="chip-row screen-tabs">
    {report.screens.map((screen, idx) => (
      <button
        type="button"
        key={screen.id}
        className={idx === activeScreenIndex ? "primary-button" : "secondary-button"}
        onClick={() => setActiveScreenIndex(idx)}
      >
        {screen.title} ({screen.element_ids.length})
      </button>
    ))}
  </div>
  ```
* **Step 3.3 (Bounding box offset):**
  For the active screen, adjust the SVG highlight overlay so bounding boxes are offset by `scroll_y`:
  ```tsx
  const currentScreen = report.screens[activeScreenIndex] ?? null;
  const activeScrollY = currentScreen?.scroll_y ?? 0;
  // Boxes rendered with y: e.bbox[1] - activeScrollY
  ```
* **Step 3.4 (Interactive finding-to-screen link):**
  Clicking a finding in the right-hand panel automatically switches to the screen that contains that element.

### Task 4: Verification & Test Suite
* Update `server/tests/test_scan.py` to assert `screens` is populated and contains valid `scroll_y` and `screenshot_b64`.
* Run web verification: `cd web; npx next typegen; npx tsc --noEmit`.
* Run web tests: `node --test web/lib/*.test.mjs`.
* Run ESLint: `cd web; npx eslint .`.
* Run backend tests: `cd server; pytest tests/test_scan.py`.

---

## 4. Risk Mitigation & Guardrails

| Risk | Mitigation |
|---|---|
| **Scan Latency Increase** | Max 2 additional screens captured; short 150ms settle time; total scan overhead $\le 1.2$ s. |
| **Infinite Scroll Traps** | Scroll flick executes exactly once to `document.body.scrollHeight`; no infinite loop. |
| **Backward Compatibility** | `screenshot_b64` remains populated on `ScanReport` so existing clients and tests continue to work without modification. |
| **Agent Isolation** | All logic is strictly enclosed within `POST /scan`. The live agent loop in `loop.py` is completely untouched. |
