import streamlit as st
import anthropic
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import zipfile
import base64
import os
import json
import numpy as np
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="rMG Album Cover Generator",
    layout="centered",
)

# ── Paths ─────────────────────────────────────────────────────────────────────
ASSETS_DIR = Path(__file__).parent / "assets"
DATA_DIR   = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

EPP_LOGO   = ASSETS_DIR / "epp_logo.jpg"
RC_LOGO    = ASSETS_DIR / "rc_logo.jpg"
SSC_LOGO   = ASSETS_DIR / "ssc_logo.png"

TITLE_HISTORY_FILE = DATA_DIR / "album_title_history.json"
SERIES_NAMES_FILE  = DATA_DIR / "epp_series_names.json"

CATALOGS = {
    "EPP": {
        "label": "Ekonomic Propaganda", "code": "EPP", "logo_path": EPP_LOGO,
        "description": "Production music for advertising, TV, and corporate content. "
                       "Bright, bold, commercial aesthetic with clear white bottom band.",
        "layout": "epp",
    },
    "rC": {
        "label": "redCola", "code": "rC", "logo_path": RC_LOGO,
        "description": "Cinematic trailer music for thriller, suspense, horror, and sci-fi. "
                       "Dark, intense, highly variable creative layouts. No fixed band.",
        "layout": "rc",
    },
    "SSC": {
        "label": "Short Story Collective", "code": "SSC", "logo_path": SSC_LOGO,
        "description": "Traditional orchestral music for drama and thriller. "
                       "Elegant, cinematic. Catalog name at top, logo badge overlaid on image.",
        "layout": "ssc",
    },
}

OUTPUT_SIZES = [3000, 1500, 1000, 500]

FONT_OPTIONS = [
    "Helvetica", "Arial", "Avenir", "Futura", "Gill Sans", "Optima",
    "Bodoni 72", "Didot", "Baskerville", "Georgia", "Palatino", "Times New Roman",
    "Impact", "Copperplate", "Rockwell", "American Typewriter",
    "Phosphate", "Gurmukhi MN", "Trattatello", "Papyrus",
]


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #ffffff !important; }
    h1, h2, h3, h4, p, label { color: #222 !important; }
    .section-label {
        font-size: 0.72rem; letter-spacing: 2px; color: #888;
        text-transform: uppercase; margin-bottom: 8px; margin-top: 4px;
    }
    .logo-confirm-box {
        background: #ffffff; border: 1px solid #ddd; border-radius: 10px;
        padding: 14px; margin: 10px 0; text-align: center;
    }
    .confirm-label {
        font-size: 0.85rem; color: #888; margin-bottom: 6px;
        letter-spacing: 1px; text-transform: uppercase;
    }
    .ai-suggestion-box {
        background: #f9f9f9; border: 1px solid #ddd; border-radius: 8px;
        padding: 12px 16px; margin: 8px 0; color: #333; font-size: 0.9rem;
    }
    .stButton>button {
        background-color: #CC2200 !important; color: #ffffff !important;
        border: none !important; border-radius: 6px !important;
        font-weight: bold !important; letter-spacing: 0.5px !important;
    }
    .stButton>button:hover {
        background-color: #aa1a00 !important; color: #ffffff !important;
    }
    .stButton>button p, .stButton>button span { color: #ffffff !important; }
    div[data-testid="stSelectbox"] { background: #fff; border-radius: 8px; }
    .big-download .stDownloadButton>button {
        font-size: 1.3rem !important; padding: 18px 24px !important;
        background-color: #CC2200 !important; color: #ffffff !important;
        border: none !important; border-radius: 8px !important;
        font-weight: bold !important; letter-spacing: 1px !important;
    }
    .big-download .stDownloadButton>button:hover { background-color: #aa1a00 !important; }
    .big-download .stDownloadButton>button p,
    .big-download .stDownloadButton>button span { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)


# ── Data persistence ──────────────────────────────────────────────────────────

def load_title_history():
    if TITLE_HISTORY_FILE.exists():
        try: return json.loads(TITLE_HISTORY_FILE.read_text())
        except Exception: pass
    return []

def save_title_history(history):
    TITLE_HISTORY_FILE.write_text(json.dumps(history))

def add_to_title_history(title):
    if not title or not title.strip(): return
    history = load_title_history()
    title = title.strip()
    history = [t for t in history if t != title]
    history.insert(0, title)
    save_title_history(history[:20])

def load_series_names():
    if SERIES_NAMES_FILE.exists():
        try: return json.loads(SERIES_NAMES_FILE.read_text())
        except Exception: pass
    defaults = [
        "Sounds Like Trouble", "Orchestral Adventure", "Orchestral Drama",
        "Orchestral Romance", "Sounds Carefree", "Sounds Heartfelt",
        "Sounds Intimate", "Sounds Like Indie Rock", "Sounds Like Mischief",
        "Sounds Like Mystery", "Sounds Like Spies", "Sounds Like Sunshine",
        "Sounds Like The Holidays", "Sounds Like Travel", "Sounds Tropical",
        "Sounds Retro Cool", "Sounds Sexy", "Sounds Tender", "Sounds Electric",
    ]
    save_series_names(defaults)
    return defaults

def save_series_names(names):
    SERIES_NAMES_FILE.write_text(json.dumps(names))

def add_series_name(name):
    if not name or not name.strip(): return
    names = load_series_names()
    name = name.strip()
    if name not in names:
        names.append(name)
        names.sort()
        save_series_names(names)

def delete_series_name(name):
    names = load_series_names()
    save_series_names([n for n in names if n != name])

def rename_series_name(old_name, new_name):
    if not new_name or not new_name.strip(): return
    names = load_series_names()
    save_series_names([new_name.strip() if n == old_name else n for n in names])


# ── Image / font helpers ──────────────────────────────────────────────────────

def load_logo(path: Path):
    if not path.exists(): return None
    img = Image.open(path).convert("RGBA")
    data = np.array(img)
    r, g, b = data[:,:,0], data[:,:,1], data[:,:,2]
    is_dark  = (r < 40)  & (g < 40)  & (b < 40)
    is_light = (r > 215) & (g > 215) & (b > 215)
    data[is_dark | is_light, 3] = 0
    return Image.fromarray(data)

def hex_to_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def resize_cover(img, size):
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    ratio  = max(size / img.width, size / img.height)
    new_w, new_h = int(img.width * ratio), int(img.height * ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    x, y = (new_w - size) // 2, (new_h - size) // 2
    canvas.paste(resized.crop((x, y, x + size, y + size)), (0, 0))
    return canvas

def get_font(name, size):
    # Map Mac font names to Linux equivalents (for Streamlit Cloud / Linux deployment)
    LINUX_FONT_MAP = {
        "Helvetica":          ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        "Arial":              ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        "Avenir":             ["/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        "Futura":             ["/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        "Gill Sans":          ["/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
        "Optima":             ["/usr/share/fonts/truetype/google-fonts/Poppins-Light.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
        "Bodoni 72":          ["/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"],
        "Didot":              ["/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"],
        "Baskerville":        ["/usr/share/fonts/truetype/baskerville/GFSBaskerville.otf",
                               "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"],
        "Georgia":            ["/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"],
        "Palatino":           ["/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"],
        "Times New Roman":    ["/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"],
        "Impact":             ["/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
        "Copperplate":        ["/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        "Rockwell":           ["/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"],
        "American Typewriter": ["/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf"],
        "Phosphate":          ["/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        "Gurmukhi MN":        ["/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        "Trattatello":        ["/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf"],
        "Papyrus":            ["/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
    }

    # Also check for bundled fonts in assets/fonts/ (for custom fonts in the repo)
    assets_fonts = Path(__file__).parent / "assets" / "fonts"

    candidates = [
        # Mac system fonts
        f"/System/Library/Fonts/{name}.ttc",
        f"/System/Library/Fonts/{name}.ttf",
        f"/Library/Fonts/{name}.ttf",
        f"/Library/Fonts/{name} Regular.ttf",
        f"/System/Library/Fonts/Supplemental/{name}.ttf",
        f"/System/Library/Fonts/Supplemental/{name}.ttc",
        # Bundled fonts in repo
        str(assets_fonts / f"{name}.ttf"),
        str(assets_fonts / f"{name}.otf"),
    ]
    # Add Linux mapped fonts
    candidates.extend(LINUX_FONT_MAP.get(name, []))
    # Final fallbacks
    candidates.extend([
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ])

    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_text_spaced(draw, pos, text, font, fill, spacing=0, anchor="mm"):
    """Draw text with extra letter spacing. Uses 'ls' baseline anchoring to prevent wobble."""
    if not text: return
    if spacing == 0:
        draw.text(pos, text, font=font, fill=fill, anchor=anchor)
        return

    # Get font metrics for consistent baseline
    try:
        ascent, descent = font.getmetrics()
    except Exception:
        ascent = int(getattr(font, 'size', 12))
        descent = int(ascent * 0.25)

    # Calculate per-character advances and total width
    advances = []
    total_w = 0
    for i, ch in enumerate(text):
        try:
            adv = font.getlength(ch)
        except Exception:
            try:
                bb = font.getbbox(ch)
                adv = bb[2] - bb[0]
            except Exception:
                adv = ascent * 0.6
        advances.append(adv)
        total_w += adv
        if i < len(text) - 1:
            total_w += spacing

    cx, cy = pos
    h_anchor = anchor[0] if len(anchor) == 2 else "m"
    v_anchor = anchor[1] if len(anchor) == 2 else "m"

    # Horizontal start position
    if h_anchor == "m":
        start_x = cx - total_w / 2
    elif h_anchor == "r":
        start_x = cx - total_w
    else:
        start_x = cx

    # Convert vertical anchor to baseline y-coordinate
    if v_anchor == "t":
        baseline_y = cy + ascent
    elif v_anchor == "b":
        baseline_y = cy - descent
    elif v_anchor == "m":
        baseline_y = cy + (ascent - descent) / 2
    else:
        baseline_y = cy + (ascent - descent) / 2

    # Draw each character at shared baseline using 'ls' anchor — eliminates wobble
    x = start_x
    for i, (ch, adv) in enumerate(zip(text, advances)):
        draw.text((x, baseline_y), ch, font=font, fill=fill, anchor="ls")
        x += adv + spacing


# ── AI suggestions ────────────────────────────────────────────────────────────

def get_ai_suggestions(catalog, album_title, series_name, description, hero_b64):
    # Use Streamlit secrets (deployed) or environment variable (local)
    api_key = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY"))
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are an expert music album cover art director for production music catalogs.

CATALOG: {catalog['label']} ({catalog['code']})
CATALOG STYLE: {catalog['description']}
ALBUM TITLE: {album_title}
SERIES NAME: {series_name}
MOOD/DESCRIPTION: {description}

Study the hero image carefully. Then study the MOOD/DESCRIPTION carefully.
Your font and sizing choices MUST reflect the mood described:
- Playful/light moods → rounder, lighter fonts (Gill Sans, Avenir, Optima)
- Dark/intense moods → heavy, bold fonts (Impact, Bodoni 72, Copperplate)
- Elegant/sophisticated → serif fonts (Didot, Baskerville, Palatino)
- Retro/vintage → character fonts (American Typewriter, Rockwell)
- Experimental/edgy → distinctive fonts (Phosphate, Gurmukhi MN, Futura)

Respond ONLY with valid JSON (no markdown, no backticks):
{{
  "title_font": "one of: {', '.join(FONT_OPTIONS)}",
  "title_size_pct": 0.08,
  "title_color": "#111111",
  "title_position": "bottom",
  "series_font": "one of the fonts above",
  "series_size_pct": 0.025,
  "series_color": "#333333",
  "text_shadow": false,
  "reasoning": "2-3 sentences explaining how the mood and image influenced your font/layout choices"
}}

Layout rules:
- EPP: title_position = "bottom", dark text colors
- SSC: title_position = "top", light text colors
- rC: any position, often dramatic
- title_size_pct: 0.05=small, 0.08=medium, 0.11=large
- Choose fonts that genuinely match the mood. Do NOT default to Helvetica unless the mood is neutral/corporate.
"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": hero_b64}},
                    {"type": "text",  "text": prompt}
                ]
            }]
        )
        raw = response.content[0].text.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        fallbacks = {
            "EPP": {"title_font":"Bodoni 72","title_size_pct":0.07,"title_color":"#111111",
                    "title_position":"bottom","series_font":"Helvetica","series_size_pct":0.022,
                    "series_color":"#444444","text_shadow":False,
                    "reasoning":f"Default EPP layout (API unavailable: {e})"},
            "rC":  {"title_font":"Impact","title_size_pct":0.09,"title_color":"#FFFFFF",
                    "title_position":"bottom","series_font":"Helvetica","series_size_pct":0.025,
                    "series_color":"#FFFFFF","text_shadow":True,
                    "reasoning":f"Default rC layout (API unavailable: {e})"},
            "SSC": {"title_font":"Palatino","title_size_pct":0.09,"title_color":"#FFFFFF",
                    "title_position":"top","series_font":"Gill Sans","series_size_pct":0.022,
                    "series_color":"#DDDDDD","text_shadow":True,
                    "reasoning":f"Default SSC layout (API unavailable: {e})"},
        }
        return fallbacks.get(catalog["code"], fallbacks["rC"])


# ── EPP Compositing ───────────────────────────────────────────────────────────

def _draw_epp_badge(canvas, size, scale, logo, band_edge_y, position):
    max_badge_w, max_badge_h, pad = int(1100*scale), int(190*scale), int(24*scale)
    if logo:
        logo_ratio = logo.width / logo.height
        fit_w = min(max_badge_w, int(max_badge_h * logo_ratio))
        fit_h = int(fit_w / logo_ratio)
        box_w, box_h = fit_w + pad*2, fit_h + pad*2
        box_x = (size - box_w) // 2
        box_y = band_edge_y - pad if position == "top" else band_edge_y - fit_h - pad
        badge_bg = Image.new("RGBA", (box_w, box_h), (255, 255, 255, 255))
        bd = ImageDraw.Draw(badge_bg)
        bd.rectangle([0, 0, box_w-1, box_h-1], outline=(180,0,0), width=max(3, int(4*scale)))
        canvas.paste(badge_bg, (box_x, box_y))
        logo_r = logo.resize((fit_w, fit_h), Image.LANCZOS)
        canvas.paste(logo_r, (box_x+pad, box_y+pad), logo_r)
        return box_y, box_y + box_h
    else:
        box_w, box_h = max_badge_w, max_badge_h
        box_x = (size - box_w) // 2
        box_y = band_edge_y - pad if position == "top" else band_edge_y - box_h
        d = ImageDraw.Draw(canvas)
        d.rectangle([box_x, box_y, box_x+box_w, box_y+box_h],
                    fill=(255,255,255), outline=(180,0,0), width=max(3,int(4*scale)))
        f = get_font("Helvetica", int(box_h * 0.5))
        d.text((box_x+box_w//2, box_y+box_h//2), "EKONOMIC PROPAGANDA",
               fill=(180,0,0), font=f, anchor="mm")
        return box_y, box_y + box_h


def composite_epp(hero, size, logo, album_title, series_name, s, adj):
    canvas = resize_cover(hero, size)
    scale  = size / 3000
    position = adj.get("position", s.get("title_position", "bottom"))
    style = adj.get("style", "white_band")  # white_band, dark_overlay, light_overlay

    # Shared text setup
    base_title_sz  = adj.get("title_size",  0) or int(s.get("title_size_pct",  0.08)  * 3000)
    base_series_sz = adj.get("series_size", 0) or int(s.get("series_size_pct", 0.025) * 3000)
    title_sz  = max(8, int(base_title_sz  * scale))
    series_sz = max(8, int(base_series_sz * scale))
    letter_spacing = int(adj.get("letter_spacing", 0) * scale)
    title_font  = get_font(adj.get("title_font",  s.get("title_font",  "Helvetica")), title_sz)
    series_font = get_font(adj.get("series_font", s.get("series_font", "Helvetica")), series_sz)
    cx = size // 2
    title_str  = album_title.upper()  if adj.get("title_caps",  False) else album_title
    series_str = series_name.upper()  if adj.get("series_caps", False) else series_name

    # Measure actual text heights
    try:
        title_h = title_font.getbbox(title_str or "A")[3] - title_font.getbbox(title_str or "A")[1]
    except Exception:
        title_h = title_sz
    try:
        series_h = series_font.getbbox(series_str or "A")[3] - series_font.getbbox(series_str or "A")[1]
    except Exception:
        series_h = series_sz

    gap = int(14 * scale)
    padding = int(30 * scale)

    # EPP label for overlay modes (integrated into strip, no badge box)
    epp_label_sz = max(12, int(42 * scale))
    try:
        epp_label_font = get_font("Helvetica", epp_label_sz)
        epp_label_h = epp_label_font.getbbox("EKONOMIC PROPAGANDA")[3] - epp_label_font.getbbox("EKONOMIC PROPAGANDA")[1]
    except Exception:
        epp_label_font = get_font("Helvetica", 14)
        epp_label_h = 14
    epp_gap = int(18 * scale)

    text_block_h = title_h + (series_h + gap if series_name else 0)

    # ── Style-dependent colors ──
    if style == "dark_overlay":
        text_fill_title  = (255, 255, 255)
        text_fill_series = (210, 210, 210)
        epp_label_fill   = (180, 0, 0)
        overlay_fill     = (0, 0, 0, 155)
        use_overlay = True
        use_text_shadow = True
    elif style == "light_overlay":
        text_fill_title  = (17, 17, 17)
        text_fill_series = (68, 68, 68)
        epp_label_fill   = (180, 0, 0)
        overlay_fill     = (255, 255, 255, 150)
        use_overlay = True
        use_text_shadow = False
    else:
        title_col  = adj.get("title_color",  s.get("title_color",  "#111111"))
        series_col = adj.get("series_color", s.get("series_color", "#555555"))
        text_fill_title  = hex_to_rgb(title_col)
        text_fill_series = hex_to_rgb(series_col)
        use_overlay = False
        use_text_shadow = False

    # ── Helper: overlay text block (EPP label + series + title) ──
    def _draw_overlay_block(draw_ctx, y):
        try:
            draw_ctx.text((cx, y), "EKONOMIC PROPAGANDA", font=epp_label_font,
                          fill=epp_label_fill, anchor="mt")
        except Exception:
            pass  # skip label if font too small
        y += epp_label_h + epp_gap
        if series_name:
            draw_ctx.text((cx, y), series_str, font=series_font,
                          fill=text_fill_series, anchor="mt")
            y += series_h + gap
        draw_text_spaced(draw_ctx, (cx, y), title_str, title_font,
                         text_fill_title, letter_spacing, anchor="mt")

    # ── Helper: white band text block (series + title, badge separate) ──
    def _draw_band_block(draw_ctx, y):
        if series_name:
            draw_ctx.text((cx, y), series_str, font=series_font,
                          fill=text_fill_series, anchor="mt")
            y += series_h + gap
        draw_text_spaced(draw_ctx, (cx, y), title_str, title_font,
                         text_fill_title, letter_spacing, anchor="mt")

    # ══ OVERLAY STYLES ══
    if use_overlay:
        overlay_content_h = epp_label_h + epp_gap + text_block_h
        strip_pad = int(55 * scale)
        strip_h = overlay_content_h + strip_pad * 2
        margin = int(20 * scale)

        if position == "top":
            strip_y = margin
        elif position == "center":
            strip_y = (size - strip_h) // 2
        else:
            strip_y = size - strip_h - margin

        canvas = canvas.convert("RGBA")
        overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([0, strip_y, size, strip_y + strip_h], fill=overlay_fill)
        canvas = Image.alpha_composite(canvas, overlay)

        # Text shadow for dark overlay
        if use_text_shadow:
            try:
                shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                sd = ImageDraw.Draw(shadow)
                off = max(1, int(3 * scale))
                sy = strip_y + (strip_h - overlay_content_h) // 2
                sd.text((cx + off, sy + off), "EKONOMIC PROPAGANDA",
                        font=epp_label_font, fill=(0,0,0,60), anchor="mt")
                if series_name:
                    sd.text((cx + off, sy + epp_label_h + epp_gap + off),
                            series_str, font=series_font, fill=(0,0,0,80), anchor="mt")
                canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(off * 2)))
            except Exception:
                pass  # skip shadow if font rendering fails

        draw = ImageDraw.Draw(canvas)
        content_start = strip_y + (strip_h - overlay_content_h) // 2
        _draw_overlay_block(draw, content_start)
        canvas = canvas.convert("RGB")

    # ══ WHITE BAND STYLE ══
    else:
        band_h = max(int(365 * scale), text_block_h + padding * 2 + int(20 * scale))

        if position == "top":
            white_band = Image.new("RGB", (size, band_h), (255, 255, 255))
            canvas.paste(white_band, (0, 0))
            draw = ImageDraw.Draw(canvas)
            _draw_band_block(draw, (band_h - text_block_h) // 2)
            _draw_epp_badge(canvas, size, scale, logo, band_h, "top")

        elif position == "center":
            band_y = (size - band_h) // 2
            white_band = Image.new("RGB", (size, band_h), (255, 255, 255))
            canvas.paste(white_band, (0, band_y))
            draw = ImageDraw.Draw(canvas)
            _draw_band_block(draw, band_y + (band_h - text_block_h) // 2)
            _draw_epp_badge(canvas, size, scale, logo, band_y, "bottom")

        else:
            band_y = size - band_h
            white_band = Image.new("RGB", (size, band_h), (255, 255, 255))
            canvas.paste(white_band, (0, band_y))
            _draw_epp_badge(canvas, size, scale, logo, band_y, "bottom")
            draw = ImageDraw.Draw(canvas)
            _draw_band_block(draw, band_y + (band_h - text_block_h) // 2)

    return canvas if isinstance(canvas, Image.Image) and canvas.mode == "RGB" else canvas.convert("RGB")


def composite_rc(hero, size, logo, album_title, series_name, s, adj):
    canvas = resize_cover(hero, size).convert("RGBA")
    draw   = ImageDraw.Draw(canvas)
    scale  = size / 3000
    base_title_sz  = adj.get("title_size",  0) or int(s.get("title_size_pct",  0.08) * 3000)
    base_series_sz = adj.get("series_size", 0) or int(s.get("series_size_pct", 0.025) * 3000)
    title_sz  = max(8, int(base_title_sz  * scale))
    series_sz = max(8, int(base_series_sz * scale))
    title_col  = adj.get("title_color",  s["title_color"])
    series_col = adj.get("series_color", s["series_color"])
    title_font  = get_font(adj.get("title_font",  s["title_font"]),  title_sz)
    series_font = get_font(adj.get("series_font", s["series_font"]), series_sz)
    margin   = int(80 * scale)
    position = adj.get("position", s.get("title_position", "bottom-left"))

    if position == "top":       tx, ty, anchor = size//2, margin+title_sz,      "mt"
    elif position == "bottom":  tx, ty, anchor = size//2, size-margin-title_sz, "mb"
    elif position == "center":  tx, ty, anchor = size//2, size//2,              "mm"
    else:                       tx, ty, anchor = margin,  size-margin-title_sz*2, "la"

    if s.get("text_shadow", True):
        sh = Image.new("RGBA", canvas.size, (0,0,0,0))
        sd = ImageDraw.Draw(sh)
        off = max(2, int(4*scale))
        if series_name:
            sd.text((tx+off, ty-series_sz-4+off), series_name.upper(),
                    fill=(0,0,0,160), font=series_font, anchor=anchor)
        sd.text((tx+off, ty+off), album_title, fill=(0,0,0,160), font=title_font, anchor=anchor)
        canvas = Image.alpha_composite(canvas, sh.filter(ImageFilter.GaussianBlur(off*2)))
        draw = ImageDraw.Draw(canvas)

    letter_spacing = int(adj.get("letter_spacing", 0) * scale)
    title_str_rc  = album_title.upper() if adj.get("title_caps", False) else album_title
    series_str_rc = series_name.upper() if adj.get("series_caps", True)  else series_name
    if series_name:
        draw_text_spaced(draw, (tx, ty-series_sz-4), series_str_rc,
                         series_font, hex_to_rgb(series_col), letter_spacing, anchor=anchor)
    draw_text_spaced(draw, (tx, ty), title_str_rc,
                     title_font, hex_to_rgb(title_col), letter_spacing, anchor=anchor)
    if logo:
        lh = int(120*scale); lw = int(logo.width*(lh/logo.height))
        lr = logo.resize((lw, lh), Image.LANCZOS)
        canvas.paste(lr, (margin, size-margin-lh), lr)
    return canvas.convert("RGB")


# ── SSC Compositing ───────────────────────────────────────────────────────────

def composite_ssc(hero, size, logo, album_title, series_name, s, adj):
    canvas = resize_cover(hero, size).convert("RGBA")
    draw   = ImageDraw.Draw(canvas)
    scale  = size / 3000
    base_title_sz  = adj.get("title_size",  0) or int(s.get("title_size_pct",  0.08) * 3000)
    base_series_sz = adj.get("series_size", 0) or int(s.get("series_size_pct", 0.025) * 3000)
    title_sz  = max(8, int(base_title_sz  * scale))
    series_sz = max(8, int(base_series_sz * scale))
    title_col  = adj.get("title_color",  s["title_color"])
    series_col = adj.get("series_color", s["series_color"])
    title_font  = get_font(adj.get("title_font",  s["title_font"]),  title_sz)
    series_font = get_font(adj.get("series_font", s["series_font"]), series_sz)
    margin = int(80*scale)
    label_font = get_font("Gill Sans", int(32*scale))
    letter_spacing = int(adj.get("letter_spacing", 0) * scale)
    title_str_ssc  = album_title.upper() if adj.get("title_caps", False) else album_title
    series_str_ssc = series_name.upper() if adj.get("series_caps", False) else series_name

    draw_text_spaced(draw, (size//2, margin), "S H O R T   S T O R Y   C O L L E C T I V E",
                     label_font, hex_to_rgb(series_col), letter_spacing, anchor="mt")
    if series_name:
        draw_text_spaced(draw, (size//2, margin+int(50*scale)), series_str_ssc,
                         series_font, hex_to_rgb(series_col), letter_spacing, anchor="mt")
    title_y = int(size * 0.22)
    words = title_str_ssc.split()
    if len(words) > 3:
        mid = len(words) // 2
        draw_text_spaced(draw, (size//2, title_y), " ".join(words[:mid]),
                         title_font, hex_to_rgb(title_col), letter_spacing, anchor="mt")
        draw_text_spaced(draw, (size//2, title_y+int(title_sz*1.2)), " ".join(words[mid:]),
                         title_font, hex_to_rgb(title_col), letter_spacing, anchor="mt")
    else:
        draw_text_spaced(draw, (size//2, title_y), title_str_ssc,
                         title_font, hex_to_rgb(title_col), letter_spacing, anchor="mt")
    if logo:
        bw, bh = int(400*scale), int(220*scale)
        bx, by = (size-bw)//2, int(size*0.68)
        ov = Image.new("RGBA", canvas.size, (0,0,0,0))
        od = ImageDraw.Draw(ov)
        od.rectangle([bx,by,bx+bw,by+bh], fill=(200,200,200,180),
                     outline=(160,160,160,220), width=max(2,int(3*scale)))
        canvas = Image.alpha_composite(canvas, ov)
        lh = int(bh*0.75); lw = int(logo.width*(lh/logo.height))
        lr = logo.resize((lw, lh), Image.LANCZOS)
        canvas.paste(lr, (bx+(bw-lw)//2, by+(bh-lh)//2), lr)
    return canvas.convert("RGB")


# ── Build & export ────────────────────────────────────────────────────────────

def build_cover(catalog_key, hero_img, logo, album_title, series_name, s, adj):
    results = {}
    for sz in OUTPUT_SIZES:
        if catalog_key == "EPP":
            results[sz] = composite_epp(hero_img, sz, logo, album_title, series_name, s, adj)
        elif catalog_key == "rC":
            results[sz] = composite_rc(hero_img, sz, logo, album_title, series_name, s, adj)
        elif catalog_key == "SSC":
            results[sz] = composite_ssc(hero_img, sz, logo, album_title, series_name, s, adj)
    return results

def make_zip(covers, album_title, catalog_code):
    buf = io.BytesIO()
    safe_title = album_title.replace(" ","_").replace("/","-")[:40]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sz, img in covers.items():
            img_buf = io.BytesIO()
            img.convert("RGB").save(img_buf, format="JPEG", quality=95)
            zf.writestr(f"{catalog_code}_{safe_title}_{sz}x{sz}.jpg", img_buf.getvalue())
    return buf.getvalue()


# ── Session state ──────────────────────────────────────────────────────────────
for key, default in [("selected_catalog", None), ("suggestions", None),
                     ("covers", None), ("hero_img", None)]:
    if key not in st.session_state:
        st.session_state[key] = default


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("## rMG Album Cover Generator")
st.markdown("---")

# ── Step 1 — Catalog ──────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Step 1 — Select Catalog</div>', unsafe_allow_html=True)

catalog_options = ["— select —"] + [cat["label"] for cat in CATALOGS.values()]
chosen_label = st.selectbox("", catalog_options, label_visibility="collapsed")

selected_key = None
for k, v in CATALOGS.items():
    if v["label"] == chosen_label:
        selected_key = k
        break

if selected_key != st.session_state.selected_catalog:
    st.session_state.selected_catalog = selected_key
    st.session_state.suggestions = None
    st.session_state.covers = None

# Logo confirmation — RESTORED with actual logo image
if st.session_state.selected_catalog:
    cat = CATALOGS[st.session_state.selected_catalog]
    st.markdown('<div class="logo-confirm-box">', unsafe_allow_html=True)
    st.markdown(f'<div class="confirm-label">✓ Working on: {cat["label"]}</div>',
                unsafe_allow_html=True)
    if cat["logo_path"].exists():
        cl, cc, cr = st.columns([1, 2, 1])
        with cc:
            st.image(str(cat["logo_path"]), use_container_width=True)
    else:
        st.warning(f"Logo not found — place at: assets/{cat['logo_path'].name}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# ── Step 2 — Album details ────────────────────────────────────────────────────
if st.session_state.selected_catalog:
    st.markdown('<div class="section-label">Step 2 — Album Details</div>', unsafe_allow_html=True)

    # ── Album Title — single dropdown + conditional text input below ──
    title_history = load_title_history()
    title_options = ["— type new title —"] + title_history
    title_choice = st.selectbox("Album Title", title_options, key="title_sel")

    if title_choice == "— type new title —":
        album_title = st.text_input("Enter Album Title", placeholder="e.g. Wink Factor",
                                    key="new_title_input")
    else:
        album_title = title_choice

    # ── Series Name ──
    series_names = load_series_names()
    series_options = ["— select —", "➕ Add new…"] + sorted(series_names)
    series_choice = st.selectbox("Series Name", series_options, key="series_sel")

    if series_choice == "➕ Add new…":
        new_series = st.text_input("New Series Name", placeholder="e.g. Sounds Like Adventure",
                                   key="new_series_input")
        if new_series and st.button("Save Series Name", key="save_series"):
            add_series_name(new_series)
            st.rerun()
        series_name = new_series if new_series else ""
    elif series_choice == "— select —":
        series_name = ""
    else:
        series_name = series_choice

    with st.expander("📝 Manage Series Names", expanded=False):
        current_names = load_series_names()
        for i, sn in enumerate(sorted(current_names)):
            mc1, mc2, mc3 = st.columns([5, 1, 1])
            with mc1:
                edited = st.text_input(f"sn_{i}", value=sn, key=f"edit_sn_{i}",
                                       label_visibility="collapsed")
            with mc2:
                if edited != sn and st.button("✓", key=f"rename_sn_{i}"):
                    rename_series_name(sn, edited)
                    st.rerun()
            with mc3:
                if st.button("✕", key=f"del_sn_{i}"):
                    delete_series_name(sn)
                    st.rerun()

    # ── Mood ──
    mood_desc = st.text_area("Mood / Description (strongly influences AI font choices)",
                             placeholder="e.g. Dark, brooding synth-wave with pulsing bass…",
                             height=60)

    # ── Hero image — compact ──
    hero_file = st.file_uploader("Upload Hero Image", type=["jpg","jpeg","png"], key="hero_upload")
    if hero_file:
        st.session_state.hero_img = Image.open(hero_file).convert("RGB")
        thumb = st.session_state.hero_img.copy()
        thumb.thumbnail((250, 250))
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.image(thumb, caption="✓ Loaded", use_container_width=False)

    st.markdown("---")

    # ── Step 3 — Design ───────────────────────────────────────────────────────
    if st.session_state.hero_img and album_title:
        st.markdown('<div class="section-label">Step 3 — Design</div>', unsafe_allow_html=True)

        if st.button("✨ Generate Design Suggestions", use_container_width=True):
            add_to_title_history(album_title)
            with st.spinner("Claude is analysing…"):
                thumb = st.session_state.hero_img.copy()
                thumb.thumbnail((800, 800))
                buf = io.BytesIO()
                thumb.save(buf, format="JPEG", quality=85)
                hero_b64 = base64.b64encode(buf.getvalue()).decode()
                st.session_state.suggestions = get_ai_suggestions(
                    CATALOGS[st.session_state.selected_catalog],
                    album_title, series_name, mood_desc, hero_b64
                )

        if st.session_state.suggestions:
            s = st.session_state.suggestions
            st.markdown(f'<div class="ai-suggestion-box"><em>{s.get("reasoning","")}</em></div>',
                        unsafe_allow_html=True)

            # ── Seed defaults from AI ──
            if "adj_seeded" not in st.session_state or st.session_state.get("adj_seeded_for") != id(s):
                ai_tf = s.get("title_font", "Helvetica")
                ai_sf = s.get("series_font", "Helvetica")
                st.session_state["adj_title_font_v"]  = ai_tf if ai_tf in FONT_OPTIONS else "Helvetica"
                st.session_state["adj_title_size_v"]  = int(s.get("title_size_pct", 0.08) * 3000)
                st.session_state["adj_title_caps_v"]  = False
                st.session_state["adj_series_font_v"] = ai_sf if ai_sf in FONT_OPTIONS else "Helvetica"
                st.session_state["adj_series_caps_v"] = False  # OFF by default
                st.session_state["adj_position_v"]    = s.get("title_position", "bottom")
                st.session_state["adj_style_v"]       = "white_band"
                st.session_state["adj_spacing_v"]     = 0
                st.session_state["adj_seeded"]        = True
                st.session_state["adj_seeded_for"]    = id(s)

            # ── Fine-tune controls FIRST (above preview) ──
            with st.expander("⚙️ Fine-tune", expanded=True):
                r1a, r1b, r1c = st.columns([3, 1, 1])
                with r1a:
                    tf_idx = FONT_OPTIONS.index(st.session_state["adj_title_font_v"]) if st.session_state["adj_title_font_v"] in FONT_OPTIONS else 0
                    st.session_state["adj_title_font_v"] = st.selectbox(
                        "Title Font", FONT_OPTIONS, index=tf_idx, key="w_tf")
                with r1b:
                    st.session_state["adj_title_size_v"] = st.number_input(
                        "Size", min_value=10, max_value=400,
                        value=st.session_state["adj_title_size_v"], step=5, key="w_ts")
                with r1c:
                    st.session_state["adj_title_caps_v"] = st.checkbox(
                        "CAPS", value=st.session_state["adj_title_caps_v"], key="w_tcaps")

                r2a, r2b = st.columns([3, 1])
                with r2a:
                    sf_idx = FONT_OPTIONS.index(st.session_state["adj_series_font_v"]) if st.session_state["adj_series_font_v"] in FONT_OPTIONS else 0
                    st.session_state["adj_series_font_v"] = st.selectbox(
                        "Series Font", FONT_OPTIONS, index=sf_idx, key="w_sf")
                with r2b:
                    st.session_state["adj_series_caps_v"] = st.checkbox(
                        "Series CAPS", value=st.session_state["adj_series_caps_v"], key="w_scaps")

                r3a, r3b, r3c = st.columns([1, 1, 1])
                with r3a:
                    position_options = ["bottom", "top", "center"]
                    cur_pos = st.session_state["adj_position_v"]
                    pos_index = position_options.index(cur_pos) if cur_pos in position_options else 0
                    st.session_state["adj_position_v"] = st.selectbox(
                        "Position", position_options, index=pos_index, key="w_pos")
                with r3b:
                    style_options = ["white_band", "dark_overlay", "light_overlay"]
                    style_labels = {"white_band": "White Band", "dark_overlay": "Dark Overlay", "light_overlay": "Light Overlay"}
                    cur_style = st.session_state.get("adj_style_v", "white_band")
                    style_index = style_options.index(cur_style) if cur_style in style_options else 0
                    st.session_state["adj_style_v"] = st.selectbox(
                        "Style", style_options, index=style_index,
                        format_func=lambda x: style_labels.get(x, x), key="w_style")
                with r3c:
                    st.session_state["adj_spacing_v"] = st.slider(
                        "Spacing", -20, 60,
                        value=st.session_state["adj_spacing_v"], step=5, key="w_sp")

            adjustments = {
                "title_font":     st.session_state["adj_title_font_v"],
                "title_color":    "#111111",
                "title_size":     st.session_state["adj_title_size_v"],
                "title_caps":     st.session_state["adj_title_caps_v"],
                "series_font":    st.session_state["adj_series_font_v"],
                "series_color":   "#444444",
                "series_size":    st.session_state.get("adj_series_size_v",
                                    int(s.get("series_size_pct", 0.025) * 3000)),
                "series_caps":    st.session_state["adj_series_caps_v"],
                "position":       st.session_state["adj_position_v"],
                "style":          st.session_state.get("adj_style_v", "white_band"),
                "letter_spacing": st.session_state["adj_spacing_v"],
            }

            # ── Render button ──
            if st.button("🖼️ Render Preview", use_container_width=True):
                with st.spinner("Compositing…"):
                    cat  = CATALOGS[st.session_state.selected_catalog]
                    logo = load_logo(cat["logo_path"])
                    st.session_state.covers = build_cover(
                        st.session_state.selected_catalog,
                        st.session_state.hero_img,
                        logo, album_title, series_name,
                        st.session_state.suggestions, adjustments
                    )

            # ── Preview + Download BELOW controls ──
            if st.session_state.covers:
                preview = st.session_state.covers.get(1000)
                if preview:
                    st.image(preview, caption="Preview — 1000×1000", use_container_width=True)

                zip_bytes = make_zip(
                    st.session_state.covers, album_title,
                    CATALOGS[st.session_state.selected_catalog]["code"]
                )
                st.markdown('<div class="big-download">', unsafe_allow_html=True)
                st.download_button(
                    label="⬇️  DOWNLOAD ALL SIZES",
                    data=zip_bytes,
                    file_name=(f"{CATALOGS[st.session_state.selected_catalog]['code']}_"
                               f"{album_title.replace(' ','_')}_covers.zip"),
                    mime="application/zip",
                    use_container_width=True,
                )
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        if not st.session_state.hero_img:
            st.info("Upload a hero image to continue.")
        if not album_title:
            st.info("Enter an album title to continue.")
else:
    st.info("Select a catalog above to begin.")
