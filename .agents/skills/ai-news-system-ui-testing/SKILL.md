---
name: AI News System UI Testing
description: End-to-end testing of the generated ai-news-system HTML page in a sandboxed Linux environment.
---

# Testing the generated news page

- Generated HTML is written to `outputs/html/index.html` and copied to `docs/index.html` by `src/services/publisher.py`.
- Run unit tests with `python -m unittest discover tests -v` from the repo root.
- Run the full pipeline with `python src/main.py` from the repo root. It fetches live RSS and completes even when one source fails or is empty. No API keys are required unless `SEND_NEWSLETTER=true`.
- Open `file:///home/ubuntu/repos/ai-news-system/outputs/html/index.html` in Chrome for UI checks.
- In a sandboxed VM, Chrome may need `--no-sandbox --disable-gpu --disable-dev-shm-usage` flags, e.g.:
  `google-chrome --no-sandbox --disable-gpu --disable-dev-shm-usage "file:///.../outputs/html/index.html"`.
- Use `wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz` to maximize the browser window before recording.
- Filter UI elements:
  - Search: `#home-search-input` (fires `input` events).
  - Category buttons: `.category-filter-btn` with `data-category` values `all`, `ekonomi`, `teknoloji`, `dünya`, `gümrük`, `genel`.
  - Cards: `.news-card` with `data-search` and `data-category`.
- If native mouse coordinates are hard to estimate, use `document.querySelector(...).getBoundingClientRect()` and scale the coordinates to the `computer` tool's 1024x768 space, or call `.click()` directly in the browser console.

## Devin Secrets Needed
- None
