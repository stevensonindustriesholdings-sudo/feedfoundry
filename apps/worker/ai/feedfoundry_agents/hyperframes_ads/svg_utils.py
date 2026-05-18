"""Tiny SVG helpers for transparent in-video graphics layers."""

from __future__ import annotations

import re
from html import escape


SAFE_FONT = "Inter, Arial, Helvetica, sans-serif"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "trend"


def safe_words(value: str, blocked_terms: list[str] | None = None) -> str:
    text = " ".join(value.split())
    for term in blocked_terms or []:
        if not term:
            continue
        text = re.sub(re.escape(term), "", text, flags=re.IGNORECASE)
    return " ".join(text.split()) or "Trend Drop"


def trend_badge_svg(
    *,
    logo_text: str,
    badge_text: str,
    width: int = 1080,
    height: int = 1080,
    palette: list[str] | None = None,
) -> str:
    """Return a square transparent SVG badge usable as a Hyperframes overlay."""

    colors = palette or ["#101018", "#f7f0da", "#ff3d81", "#38f5d0"]
    title = escape(logo_text[:30].upper())
    badge = escape(badge_text[:34].upper())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="#000000" flood-opacity="0.32"/>
    </filter>
    <linearGradient id="pop" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{colors[2]}"/>
      <stop offset="1" stop-color="{colors[3]}"/>
    </linearGradient>
  </defs>
  <g filter="url(#softShadow)">
    <circle cx="540" cy="540" r="392" fill="{colors[0]}" fill-opacity="0.90"/>
    <circle cx="540" cy="540" r="352" fill="none" stroke="url(#pop)" stroke-width="28" stroke-dasharray="72 24"/>
    <path d="M230 592 C348 478, 458 710, 585 553 C688 426, 779 474, 850 395" fill="none" stroke="{colors[1]}" stroke-width="28" stroke-linecap="round" opacity="0.95"/>
    <text x="540" y="514" text-anchor="middle" font-family="{SAFE_FONT}" font-size="96" font-weight="900" fill="{colors[1]}" letter-spacing="-3">{title}</text>
    <rect x="248" y="618" width="584" height="118" rx="59" fill="url(#pop)"/>
    <text x="540" y="695" text-anchor="middle" font-family="{SAFE_FONT}" font-size="42" font-weight="900" fill="{colors[0]}" letter-spacing="3">{badge}</text>
  </g>
</svg>'''


def lower_third_svg(text: str, subtext: str, *, width: int = 1080, height: int = 260) -> str:
    headline = escape(text[:52])
    caption = escape(subtext[:82])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="54" y="34" width="972" height="192" rx="48" fill="#090912" fill-opacity="0.84"/>
  <rect x="78" y="58" width="12" height="144" rx="6" fill="#ff3d81"/>
  <text x="116" y="118" font-family="{SAFE_FONT}" font-size="44" font-weight="900" fill="#fff7df">{headline}</text>
  <text x="116" y="174" font-family="{SAFE_FONT}" font-size="30" font-weight="700" fill="#38f5d0">{caption}</text>
</svg>'''


def price_pill_svg(text: str = "POD HAUL", *, width: int = 420, height: int = 132) -> str:
    label = escape(text[:24].upper())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="12" y="12" width="396" height="108" rx="54" fill="#fff7df" fill-opacity="0.94"/>
  <rect x="28" y="28" width="364" height="76" rx="38" fill="#101018"/>
  <text x="210" y="80" text-anchor="middle" font-family="{SAFE_FONT}" font-size="34" font-weight="900" fill="#ff3d81" letter-spacing="2">{label}</text>
</svg>'''


def diagonal_wipe_alpha_svg(*, width: int = 1080, height: int = 1920) -> str:
    """Alpha mask with transparent canvas and white wipe geometry."""

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="black" fill-opacity="0"/>
  <path d="M-220 {height} L{width} -160 L{width + 220} 0 L0 {height + 160} Z" fill="white" fill-opacity="0.72"/>
</svg>'''
