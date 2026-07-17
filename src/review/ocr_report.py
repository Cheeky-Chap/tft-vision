"""Dependency-free static report for manually checking HUD OCR evidence."""
from __future__ import annotations
import html
from pathlib import Path
from typing import Mapping
from src.state import Observation

def render_ocr_report(observations: Mapping[str, Observation], debug_dir: Path) -> str:
    cards = []
    for field in ("player_gold", "player_level"):
        item = observations[field]
        reason = item.error or ("value rejected or no unambiguous digits" if item.status.value == "unknown" else "")
        value = "null" if item.value is None else str(item.value)
        original = (debug_dir / f"{field}-original.png").as_posix()
        processed = (debug_dir / f"{field}-preprocessed.png").as_posix()
        cards.append(f'''<article><h2>{field}</h2><div class="images"><figure><img src="{original}" alt="{field} original"><figcaption>original crop</figcaption></figure><figure><img src="{processed}" alt="{field} preprocessed"><figcaption>preprocessed OCR input</figcaption></figure></div><dl><dt>raw text</dt><dd><pre>{html.escape(item.raw_text or "")}</pre></dd><dt>value</dt><dd>{value}</dd><dt>confidence</dt><dd>{item.confidence:.4f}</dd><dt>status</dt><dd>{item.status.value}</dd><dt>reason</dt><dd>{html.escape(reason)}</dd></dl></article>''')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TFT HUD OCR inspection</title><style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:auto;padding:1rem;background:#111827;color:#e5e7eb}article{background:#1f2937;padding:1rem;margin:1rem 0}.images{display:grid;grid-template-columns:1fr 1fr;gap:1rem}img{max-width:100%;image-rendering:pixelated;background:#000}dt{font-weight:bold;margin-top:.5rem}dd{margin-left:0}pre{white-space:pre-wrap}@media(max-width:600px){.images{grid-template-columns:1fr}}</style></head><body><h1>TFT HUD OCR inspection</h1>''' + "".join(cards) + "</body></html>"
