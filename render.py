"""MADGIC vertical promo — full motion-graphics renderer (1080x1920, 30fps)."""
import math, subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import imageio_ffmpeg
from timeline import TIMELINE

W, H, FPS = 1080, 1920, 30
TOTAL = TIMELINE["total"]
SCENES = {s["key"]: s for s in TIMELINE["scenes"]}

# ---------- palette ----------
BG      = (7, 9, 18)
PANEL   = (17, 21, 38)
PANEL2  = (23, 28, 50)
TEXT    = (245, 247, 255)
MUTED   = (148, 156, 186)
GOLD    = (255, 209, 102)
GOLD_HI = (255, 243, 196)
GOLD_LO = (185, 122, 28)
CYAN    = (64, 224, 208)
CYAN_DK = (18, 60, 70)
RED     = (255, 82, 82)
GREEN   = (52, 211, 153)
WHITE   = (255, 255, 255)

F = lambda name, size: ImageFont.truetype(f"assets/fonts/{name}", size)
ANTON   = lambda s: F("Anton_400Regular.ttf", s)
MONT    = lambda s: F("Montserrat_400Regular.ttf", s)
MONTM   = lambda s: F("Montserrat_500Medium.ttf", s)
MONTB   = lambda s: F("Montserrat_700Bold.ttf", s)
MONTBB  = lambda s: F("Montserrat_800ExtraBold.ttf", s)

# ---------- math helpers ----------
def clamp(v, a=0.0, b=1.0): return max(a, min(b, v))
def lerp(a, b, t): return a + (b - a) * t
def eoc(t): t = clamp(t); return 1 - (1 - t) ** 3
def eio(t): t = clamp(t); return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
def eob(t):
    t = clamp(t); c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
def eex(t): t = clamp(t); return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)
def fade(t, t0, t1): return clamp((t - t0) / (t1 - t0))

def tracked(draw, x, y, text, fnt, fill, tracking=0, anchor="mm"):
    widths = [draw.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    cx = x - total / 2 if anchor == "mm" else (x - total if anchor == "rm" else x)
    for ch, w in zip(text, widths):
        draw.text((cx, y), ch, font=fnt, fill=fill, anchor="lm")
        cx += w + tracking
    return total

def rrect(draw, box, r, fill=None, outline=None, width=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

def sparkle_poly(cx, cy, r, rot=0.0):
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2 + rot
        rad = r if i % 2 == 0 else r * 0.18
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    return pts

def draw_sparkle(draw, cx, cy, r, color, core=WHITE, rot=0.0, alpha=255):
    draw.polygon(sparkle_poly(cx, cy, r, rot), fill=color + (alpha,) if len(color) == 3 else color)
    draw.polygon(sparkle_poly(cx, cy, r * 0.42, rot), fill=core + (alpha,) if len(core) == 3 else core)

def dust(t, seed, n, area=(0, 0, W, H), rise=55.0):
    """Deterministic drifting gold-dust particles."""
    rnd = np.random.default_rng(seed)
    x0, y0, x1, y1 = area
    xs, ys, szs, phs = rnd.random(n), rnd.random(n), rnd.random(n), rnd.random(n)
    wdt, hgt = x1 - x0, y1 - y0
    for i in range(n):
        y = (y0 + (ys[i] * hgt - t * rise * (0.5 + szs[i])) % hgt)
        x = x0 + xs[i] * wdt + math.sin(t * 0.7 + phs[i] * 6.28) * 24
        r = 1.5 + szs[i] * 3.4
        a = int(70 + 120 * (0.5 + 0.5 * math.sin(t * 1.7 + phs[i] * 9.0)))
        yield x, y, r, a

def radial_glow(size, center, radius, color, peak=255):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    steps = 26
    for i in range(steps, 0, -1):
        rr = radius * i / steps
        a = int(peak * (1 - i / steps) ** 1.7)
        d.ellipse([center[0] - rr, center[1] - rr, center[0] + rr, center[1] + rr],
                  fill=color + (a,))
    return layer.filter(ImageFilter.GaussianBlur(2))

def vgrad_image(top, bottom):
    base = np.zeros((H, W, 3), dtype=np.float32)
    tt = np.linspace(0, 1, H)[:, None, None]
    for c in range(3):
        base[:, :, c] = top[c] + (bottom[c] - top[c]) * tt[:, :, 0]
    return Image.fromarray(base.astype(np.uint8), "RGB")

def cover_img(path, target_w, target_h):
    img = Image.open(path).convert("RGB")
    s = max(target_w / img.width, target_h / img.height)
    return img.resize((int(img.width * s) + 1, int(img.height * s) + 1), Image.LANCZOS)

KB = {}
def kb_frame(path, prog):
    """Ken Burns: slow zoom + drift on a pre-scaled image."""
    K = 1.18
    if path not in KB:
        KB[path] = cover_img(path, int(W * K), int(H * K))
    big = KB[path]
    max_dx, max_dy = big.width - W, big.height - H
    p = eio(prog)
    cw = int(W * (1.0 - 0.13 * p))
    ch = int(H * (1.0 - 0.13 * p))
    cx = (max_dx + (W - cw) / 2) * (0.25 + 0.5 * p)
    cy = (max_dy + (H - ch) / 2) * (0.7 - 0.45 * p)
    frame = big.crop((int(cx), int(cy), int(cx) + cw, int(cy) + ch)).resize((W, H), Image.BILINEAR)
    return frame

def dim(frame, factor):
    return ImageEnhance_brightness(frame, factor)

from PIL import ImageEnhance
def ImageEnhance_brightness(frame, factor):
    return ImageEnhance.Brightness(frame).enhance(factor)

def bottom_gradient(alpha=200, height=760):
    g = Image.new("L", (1, height))
    for y in range(height):
        g.putpixel((0, y), int(alpha * (y / height) ** 1.6))
    return g.resize((W, height))

_BOTTOM = bottom_gradient()
_VIG = None
def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dx, dy = (xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)
        r2 = dx * dx + dy * dy
        _VIG = (1 - 0.40 * np.clip(r2, 0, 1.6) ** 1.35).astype(np.float32)
    return _VIG

def apply_vignette_and_grain(img, seed=1234):
    arr = np.asarray(img, dtype=np.float32)
    arr *= vignette()[:, :, None]
    rng = np.random.default_rng(seed)
    arr += rng.normal(0, 3.2, (H, W, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")

def new_layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))

# progress bar precomputed
def progress_bar(t):
    layer = new_layer()
    d = ImageDraw.Draw(layer)
    wdt = int(W * clamp(t / TOTAL))
    if wdt > 2:
        grad = np.zeros((10, wdt, 3), dtype=np.float32)
        tt = np.linspace(0, 1, wdt)[None, :, None]
        grad[:, :, 0] = lerp(CYAN[0], GOLD[0], tt[:, :, 0])
        grad[:, :, 1] = lerp(CYAN[1], GOLD[1], tt[:, :, 0])
        grad[:, :, 2] = lerp(CYAN[2], GOLD[2], tt[:, :, 0])
        layer.paste(Image.fromarray(grad.astype(np.uint8), "RGB"), (0, 0))
        draw_sparkle(d, wdt - 1, 5, 16, GOLD, WHITE, rot=t * 1.5, alpha=240)
    return layer

def word_pop(t, t0, dur=0.55):
    """Scale + alpha for staggered pop-ins."""
    p = clamp((t - t0) / dur)
    return eob(p), int(255 * fade(t, t0, t0 + dur * 0.5))

# ================= SCENES =================

def s1_intro(t, dur):
    frame = kb_frame("assets/img/searching_night.jpg", t / dur).convert("RGBA")
    frame = ImageEnhance_brightness(frame.convert("RGB"), 0.82).convert("RGBA")
    layer = new_layer(); d = ImageDraw.Draw(layer)
    layer.paste(Image.new("RGBA", (W, 760), (5, 6, 14, 235)), (0, H - 760), _BOTTOM)
    d = ImageDraw.Draw(layer)
    kick_a = int(255 * fade(t, 0.5, 1.0))
    tracked(d, W / 2, 1150, "S O N   H I S T O I R E   C O M M E N C E   I C I", MONTB(24), CYAN + (kick_a,), tracking=1)
    s, a = word_pop(t, 0.95, 0.6)
    if a:
        f1 = ANTON(158)
        d.text((W / 2, 1300), "IL SE", font=f1, fill=(245, 247, 255, a), anchor="mm")
    s, a = word_pop(t, 1.35, 0.6)
    if a:
        f1 = ANTON(158)
        d.text((W / 2, 1462), "CHERCHAIT.", font=f1, fill=(245, 247, 255, a), anchor="mm")
    bar = clamp((t - 1.75) / 0.7)
    if bar > 0:
        d.rounded_rectangle([W / 2 - 260 * eoc(bar), 1532, W / 2 + 260 * eoc(bar), 1540], 4, fill=GOLD + (255,))
    sub_a = int(255 * fade(t, 2.1, 2.7))
    if sub_a:
        d.text((W / 2, 1612), "à travers l'internet et les IA", font=MONT(33), fill=MUTED + (sub_a,), anchor="mm")
    for x, y, r, a2 in dust(t, 11, 34, area=(60, 200, W - 60, 1120), rise=34):
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD + (a2,))
    return Image.alpha_composite(frame, layer)

def s2_search(t, dur):
    frame = vgrad_image((10, 13, 26), (16, 26, 44)).convert("RGBA")
    layer = new_layer(); d = ImageDraw.Draw(layer)
    # ambient glow
    glow = radial_glow((W, H), (W / 2, 620), 560, CYAN, 60)
    frame = Image.alpha_composite(frame, glow)
    layer = new_layer(); d = ImageDraw.Draw(layer)
    tracked(d, W / 2, 210, "C H A P I T R E   1", MONTB(26), CYAN + (255,), tracking=2)
    d.text((W / 2, 285), "La recherche sans fin", font=MONT(30), fill=MUTED + (255,), anchor="mm")

    # search bar
    bar_y, bar_h = 520, 175
    pulse = 1 + 0.012 * math.sin(t * 2.4)
    bw = int(920 * pulse)
    rrect(d, [W / 2 - bw / 2, bar_y, W / 2 + bw / 2, bar_y + bar_h], 46, fill=(17, 23, 42, 255), outline=CYAN + (150,), width=3)
    # magnifier
    mx, my = W / 2 - bw / 2 + 95, bar_y + bar_h / 2
    d.ellipse([mx - 32, my - 32, mx + 32, my + 32], outline=CYAN + (255,), width=9)
    d.line([mx + 24, my + 24, mx + 58, my + 58], fill=CYAN + (255,), width=11)

    queries = [("qui suis-je vraiment ?", 0.6, 2.3),
               ("trouver ma voie", 2.75, 4.15),
               ("quelle IA est faite pour moi ?", 4.55, 6.6)]
    # only the active (most recent) query is drawn — previous ones are cleared
    current = -1
    for i, (_, t0, _) in enumerate(queries):
        if t >= t0 - 0.35:
            current = i
    font_q = MONTM(37)
    if current < 0:
        d.text((mx + 78, my), "rechercher…", font=font_q, fill=(90, 99, 128, 255), anchor="lm")
    else:
        q, t0, t1 = queries[current]
        local = clamp((t - t0) / (t1 - t0))
        shown = q[:int(len(q) * local)]
        d.text((mx + 78, my), shown, font=font_q, fill=(240, 246, 255, 255), anchor="lm")
        if int(t * 1.7) % 2 == 0 and local < 1:
            caret_x = mx + 78 + d.textlength(shown, font=font_q) + 4
            d.rectangle([caret_x, my - 24, caret_x + 5, my + 24], fill=CYAN + (255,))
    # result rows appear for the active query after it completes
    results_windows = [(2.3, 2.75), (4.15, 4.55), (6.6, 8.75)]
    active = [i for i, (_, t0, t1) in enumerate(queries) if t > t1 - 0.1]
    if active:
        t_done = queries[active[-1]][2]
        widths = [620, 540, 700, 480, 650, 560]
        locks  = [1, 0, 1, 1, 0, 1]
        for i in range(6):
            rt = t_done + 0.06 + i * 0.17
            a = int(230 * fade(t, rt, rt + 0.3))
            if a <= 0: continue
            y = 815 + i * 150
            rrect(d, [130, y, 130 + widths[i], y + 96], 20, fill=(22, 28, 50, a // 2))
            d.ellipse([160, y + 30, 194, y + 64], fill=(40, 50, 82, a))
            d.rounded_rectangle([228, y + 26, 228 + 190 + (i * 37 % 130), y + 42], 8, fill=(64, 74, 110, a))
            d.rounded_rectangle([228, y + 56, 228 + 150 + (i * 53 % 110), y + 68], 6, fill=(44, 52, 82, a))
            lx, ly = 130 + widths[i] - 62, y + 48
            if locks[i]:
                d.rounded_rectangle([lx - 17, ly - 6, lx + 17, ly + 24], 6, fill=RED + (a,))
                d.arc([lx - 11, ly - 24, lx + 11, ly + 2], 180, 360, fill=RED + (a,), width=6)
            else:
                d.ellipse([lx - 13, ly - 13, lx + 13, ly + 13], outline=CYAN + (a,), width=4)
    d.text((W / 2, 1785), "à travers le web, les forums, les vidéos…", font=MONT(27), fill=(110, 118, 148, 255), anchor="mm")
    return Image.alpha_composite(frame, layer)

def s3_prices(t, dur):
    frame = vgrad_image((14, 10, 14), (26, 12, 16)).convert("RGBA")
    glow = radial_glow((W, H), (W / 2, H + 100), 900, RED, 55)
    frame = Image.alpha_composite(frame, glow)
    layer = new_layer(); d = ImageDraw.Draw(layer)
    tracked(d, W / 2, 195, "L E   P R O B L È M E", MONTB(26), RED + (255,), tracking=2)
    d.text((W / 2, 268), "Des IA… mais à quel prix ?", font=MONT(30), fill=(205, 190, 190, 255), anchor="mm")

    cards = [
        ("IA",  "Chat IA Pro",       "abonnement mensuel", "20 €", 0.35, -18),
        ("IMG", "Studio Images Pro", "abonnement mensuel", "30 €", 0.80, 14),
        ("AGT", "Agent Autonome Pro","abonnement mensuel", "99 €", 1.25, -10),
    ]
    shake = 0.0
    for _, _, _, _, lt, _ in cards:
        hit = t - (lt + 0.32)
        if 0 < hit < 0.5:
            shake = max(shake, (0.5 - hit) * 16)
    if shake > 0.4:
        layer = layer.transform((W, H), Image.AFFINE, (1, 0, math.sin(t * 55) * shake, 0, 1, 0), resample=Image.BILINEAR)
        d = ImageDraw.Draw(layer)
    for glyph, title, sub, price, lt, rot in cards:
        p = eob(clamp((t - lt) / 0.55))
        if p <= 0.01: continue
        y = int(lerp(H + 200, 430 + [0, 1, 2].index(cards.index((glyph, title, sub, price, lt, rot))) * 350, min(p, 1.06)))
        card = Image.new("RGBA", (880, 300), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        rrect(cd, [0, 0, 879, 299], 40, fill=(24, 27, 46, 235), outline=(90, 40, 46, 255), width=3)
        rrect(cd, [45, 70, 195, 230], 28, fill=(36, 40, 66, 255), outline=RED + (140,), width=3)
        cd.text((120, 152), glyph, font=ANTON(64), fill=(255, 120, 120, 255), anchor="mm")
        cd.text((222, 105), title, font=MONTBB(33), fill=TEXT + (255,), anchor="lm")
        cd.text((222, 168), sub, font=MONT(24), fill=MUTED + (255,), anchor="lm")
        cd.text((222, 228), "renouvelé automatiquement", font=MONT(19), fill=(110, 118, 148, 255), anchor="lm")
        # price block (right edge)
        cd.text((730, 105), price, font=ANTON(76), fill=(255, 235, 235, 255), anchor="mm")
        cd.text((730, 188), "/ mois", font=MONT(22), fill=MUTED + (255,), anchor="mm")
        # PAYANT stamp over the price
        stamp = Image.new("RGBA", (320, 116), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        rrect(sd, [6, 6, 314, 110], 16, outline=RED + (240,), width=6)
        tracked(sd, 160, 59, "PAYANT", ANTON(48), RED + (240,), tracking=3)
        stamp = stamp.rotate(-11, resample=Image.BICUBIC, expand=False)
        card.paste(stamp, (470, 118), stamp)
        card = card.rotate(rot, resample=Image.BICUBIC, expand=False)
        layer.paste(card, (int((W - 880) / 2 + rot), int(y - 150)), card)
    big = fade(t, 1.9, 2.3)
    if big > 0:
        a = int(255 * big)
        d = ImageDraw.Draw(layer)
        tracked(d, W / 2, 1560, "T O U T   E S T", ANTON(120), (255, 255, 255, a), tracking=1)
        tracked(d, W / 2, 1700, "PAYANT.", ANTON(120), RED + (a,), tracking=1)
    return Image.alpha_composite(frame, layer)

def s4_notif(t, dur):
    frame = kb_frame("assets/img/face_screen.jpg", t / dur).convert("RGBA")
    frame = ImageEnhance_brightness(frame.convert("RGB"), 0.72).convert("RGBA")
    red_v = radial_glow((W, H), (W / 2, H / 2), 1200, (120, 10, 10), 70)
    frame = Image.alpha_composite(frame, red_v)
    layer = new_layer(); d = ImageDraw.Draw(layer)
    tracked(d, W / 2, 200, "L A   P O R T E", ANTON(96), (245, 247, 255, int(255 * fade(t, 0.15, 0.65))))
    tracked(d, W / 2, 330, "SE REFERME.", ANTON(96), RED + (int(255 * fade(t, 0.4, 0.9)),))

    # phone mockup sliding up
    p = eoc(clamp((t - 0.45) / 0.8))
    px, py = W / 2 - 330, int(lerp(H + 240, 560, p))
    pw, ph = 660, 1150
    if p > 0:
        rrect(d, [px - 14, py - 14, px + pw + 14, py + ph + 14], 74, fill=(4, 6, 14, 255), outline=(58, 66, 100, 255), width=4)
        rrect(d, [px, py, px + pw, py + ph], 62, fill=(13, 19, 33, 255))
        # status bar
        d.text((px + 55, py + 52), "21:47", font=MONTB(34), fill=(200, 208, 230, 255), anchor="lm")
        d.text((px + pw - 55, py + 52), "5G", font=MONTB(30), fill=(200, 208, 230, 255), anchor="rm")
        d.text((px + pw / 2, py + 210), "21:47", font=MONT(150), fill=(232, 236, 250, 255), anchor="mm")
        d.text((px + pw / 2, py + 330), "mardi 15 octobre", font=MONT(28), fill=(150, 158, 186, 255), anchor="mm")
        # notification card
        np_ = eoc(clamp((t - 1.15) / 0.6))
        if np_ > 0:
            ny = int(lerp(py + 620, py + 470, np_))
            na = int(255 * fade(t, 1.15, 1.5))
            rrect(d, [px + 40, ny, px + pw - 40, ny + 210], 34, fill=(244, 246, 252, na))
            d.ellipse([px + 75, ny + 58, px + 155, ny + 138], fill=(30, 36, 60, na))
            draw_sparkle(d, px + 115, ny + 98, 20, GOLD, WHITE, alpha=na)
            d.text((px + 185, ny + 62), "CHAT IA PRO", font=MONTB(24), fill=(90, 96, 120, na), anchor="lm")
            d.text((px + 185, ny + 108), "Passez à la version Pro", font=MONTBB(28), fill=(24, 28, 44, na), anchor="lm")
            d.text((px + 185, ny + 152), "Essai gratuit terminé.", font=MONT(23), fill=(90, 96, 120, na), anchor="lm")
            d.ellipse([px + pw - 78, ny - 16, px + pw - 26, ny + 36], fill=RED + (na,))
            d.text((px + pw - 52, ny + 10), "1", font=MONTB(30), fill=(255, 255, 255, na), anchor="mm")
        # home indicator
        d.rounded_rectangle([px + pw / 2 - 110, py + ph - 44, px + pw / 2 + 110, py + ph - 36], 5, fill=(120, 128, 158, 255))
    return Image.alpha_composite(frame, layer)

def s5_discovery(t, dur):
    frame = kb_frame("assets/img/door_light.jpg", t / dur).convert("RGBA")
    frame = ImageEnhance_brightness(frame.convert("RGB"), 0.9).convert("RGBA")
    layer = new_layer(); d = ImageDraw.Draw(layer)
    plate = Image.new("RGBA", (W, 520), (5, 4, 2, 225))
    layer.paste(plate, (0, H - 520), bottom_gradient(225, 520))
    d = ImageDraw.Draw(layer)
    # expanding warm flash reveal
    flash = 1 - eex(t / 1.5)
    if flash > 0.01:
        fg = radial_glow((W, H), (W / 2, int(H * 0.42)), int(200 + 1600 * eex(t / 1.3)), GOLD_HI, int(255 * flash))
        frame = Image.alpha_composite(frame, fg)
    for x, y, r, a in dust(t, 31, 44, area=(W / 2 - 260, 350, W / 2 + 260, 1250), rise=12):
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD_HI + (a,))
    kick_a = int(255 * fade(t, 0.35, 0.95))
    tracked(d, W / 2, 1332, "L E   D É C L I C", MONTB(27), GOLD + (kick_a,), tracking=3)
    a = int(255 * fade(t, 0.7, 1.3))
    if a:
        d.text((W / 2, 1405), "jusqu'au jour où il découvre…", font=MONT(33), fill=(255, 244, 214, a), anchor="mm")
    # logo slam
    if t > 2.05:
        p = eex((t - 2.05) / 0.5)
        la = int(255 * fade(t, 2.05, 2.35))
        sc = lerp(1.9, 1.0, p)
        lf = ANTON(int(148 * sc))
        flash2 = 1 - clamp((t - 2.05) / 0.42)
        if flash2 > 0:
            frame = Image.alpha_composite(frame, radial_glow((W, H), (W / 2, H * 0.86), 420, GOLD, int(230 * flash2)))
        tracked(d, W / 2, 1690, "MADGIC", lf, GOLD + (la,), tracking=max(4, int(10 * sc)))
    return Image.alpha_composite(frame, layer)

def s6_product(t, dur):
    frame = vgrad_image((9, 11, 24), (14, 30, 38)).convert("RGBA")
    frame = Image.alpha_composite(frame, radial_glow((W, H), (W / 2, 330), 700, CYAN, 55))
    layer = new_layer(); d = ImageDraw.Draw(layer)
    tracked(d, W / 2, 165, "M A D G I C", MONTB(28), GOLD + (255,), tracking=6)
    d.text((W / 2, 225), "toutes les IA, enfin réunies", font=MONT(27), fill=MUTED + (255,), anchor="mm")

    # chat window
    p = eob(clamp((t - 0.1) / 0.6))
    if p > 0:
        wx, wy, ww, wh = 85, 290, 910, 780
        off = int((1 - min(p, 1)) * 120)
        rrect(d, [wx, wy + off, wx + ww, wy + wh + off], 42, fill=(14, 18, 36, 255), outline=(52, 62, 96, 255), width=3)
        rrect(d, [wx, wy + off, wx + ww, wy + off + 92], 42, fill=(22, 27, 50, 255))
        d.rectangle([wx, wy + off + 46, wx + ww, wy + off + 92], fill=(22, 27, 50, 255))
        for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            d.ellipse([wx + 34 + i * 46, wy + off + 34, wx + 66 + i * 46, wy + off + 66], fill=c + (255,))
        rrect(d, [wx + 260, wy + off + 24, wx + ww - 260, wy + off + 68], 22, fill=(13, 17, 32, 255))
        tracked(d, wx + ww / 2, wy + off + 47, "m a d g i c", MONTM(22), CYAN + (255,), tracking=2)
        # user bubble
        aq = fade(t, 0.45, 1.0)
        if aq > 0:
            uw = 470
            ux = wx + ww - 40 - uw
            uy = wy + off + 135
            rrect(d, [ux, uy, ux + uw, uy + 108], 26, fill=(23, 78, 92, int(255 * aq)), outline=CYAN + (int(150 * aq),), width=2)
            d.text((ux + uw / 2, uy + 36), "Rédige mon business plan.", font=MONTM(26), fill=(214, 255, 248, int(255 * aq)), anchor="mm")
            d.text((ux + uw / 2, uy + 76), "et rends-le irrésistible.", font=MONTM(26), fill=(214, 255, 248, int(255 * aq)), anchor="mm")
        # agent typing dots
        if 1.35 < t < 2.25:
            ay = wy + off + 330
            for i in range(3):
                a = int(255 * (0.5 + 0.5 * math.sin(t * 6 + i * 1.05)))
                d.ellipse([wx + 70 + i * 34, ay, wx + 92 + i * 34, ay + 22], fill=GOLD + (a,))
        # agent bubble
        if t >= 2.15:
            at = "Bien sûr. Voici ton plan complet :"
            at2 = "marché, stratégie, budget, pitch…"
            local = clamp((t - 2.15) / 1.9)
            shown = at[:int(len(at) * local)]
            done2 = local >= 1
            a = 255
            ay = wy + off + 300
            rrect(d, [wx + 40, ay, wx + 700, ay + 225], 26, fill=(30, 34, 58, a), outline=GOLD + (90,), width=2)
            draw_sparkle(d, wx + 78, ay + 42, 15, GOLD, WHITE, alpha=255)
            d.text((wx + 105, ay + 43), "AGENT MADGIC", font=MONTB(22), fill=GOLD + (255,), anchor="lm", tracking=1)
            d.text((wx + 70, ay + 105), shown, font=MONT(28), fill=(238, 240, 252, 255), anchor="lm")
            if done2:
                l2 = clamp((t - 4.05) / 0.9)
                d.text((wx + 70, ay + 158), at2[:int(len(at2) * l2)], font=MONT(28), fill=(238, 240, 252, 255), anchor="lm")

    # checklist card
    cy = 1150
    a = int(255 * fade(t, 1.0, 1.45))
    if a:
        d.text((90, cy, ), "CE QUE MADGIC DÉBLOQUE", font=MONTB(26), fill=MUTED + (a,), anchor="lm", tracking=3)
    rows = [("Toutes les IA réunies au même endroit", 2.6),
            ("Un agent très poussé, inclus", 3.7),
            ("0 € d'abonnement — jamais", 4.8)]
    y = cy + 55
    for text, rt in rows:
        p = clamp((t - rt) / 0.45)
        if p <= 0: continue
        s = eob(p); a = int(255 * fade(t, rt, rt + 0.3))
        rrect(d, [90, y, W - 90, y + 118], 30, fill=(18, 33, 33, int(220 * a / 255)), outline=GREEN + (int(110 * a / 255),), width=2)
        ccx, ccy = 160, y + 59
        d.ellipse([ccx - 30 * s, ccy - 30 * s, ccx + 30 * s, ccy + 30 * s], fill=GREEN + (a,))
        ch = 16 * s
        d.line([(ccx - ch * 0.55, ccy + 1), (ccx - ch * 0.12, ccy + ch * 0.5), (ccx + ch * 0.72, ccy - ch * 0.62)],
               fill=(8, 26, 20, a), width=max(4, int(7 * s)), joint="curve")
        d.text((225, ccy), text, font=MONTB(30), fill=(232, 252, 244, a), anchor="lm")
        y += 140
    return Image.alpha_composite(frame, layer)

def s7_benefits(t, dur):
    frame = vgrad_image((10, 14, 17), (12, 22, 20)).convert("RGBA")
    frame = Image.alpha_composite(frame, radial_glow((W, H), (W / 2, 320), 620, GREEN, 42))
    layer = new_layer(); d = ImageDraw.Draw(layer)
    tracked(d, W / 2, 190, "C E   Q U E   T U   G A G N E S", MONTB(25), GREEN + (255,), tracking=2)

    lines = [("Plus d'abonnement.", 0.3), ("Plus de limite.", 0.95), ("Toute la puissance de l'IA.", 1.6)]
    y = 330
    for text, lt in lines:
        p = eob(clamp((t - lt) / 0.5))
        if p <= 0.01: continue
        a = int(255 * fade(t, lt, lt + 0.3))
        d.ellipse([90, y, 172, y + 82], fill=GREEN + (a,))
        d.line([(112, y + 42), (128, y + 58), (156, y + 20)], fill=(8, 26, 20, a), width=8, joint="curve")
        d.text((205, y + 42), text, font=MONTBB(43), fill=(240, 252, 246, a), anchor="lm")
        y += 128

    # price transformation
    a = int(255 * fade(t, 0.8, 1.15))
    if a:
        d.text((W / 2, 800), "A V A N T", font=MONTB(24), fill=MUTED + (a,), anchor="mm", tracking=4)
        old = "99 € / mois"
        f_old = ANTON(120)
        tw = d.textlength(old, font=f_old)
        d.text((W / 2, 915), old, font=f_old, fill=(130, 136, 162, a), anchor="mm")
        sw = fade(t, 1.1, 1.75) * (tw + 80)
        d.line([(W / 2 - tw / 2 - 40, 915), (W / 2 - tw / 2 - 40 + sw, 915)], fill=RED + (a,), width=14)
    tracked(d, W / 2, 1095, "M A I N T E N A N T", MONTB(26), CYAN + (int(255 * fade(t, 1.7, 2.1)),), tracking=4)
    p = eob(clamp((t - 1.9) / 0.7))
    if p > 0:
        a = int(255 * fade(t, 1.9, 2.3))
        f_big = ANTON(290)
        # gold gradient text via mask
        mask = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(mask)
        md.text((W / 2, 1330), "0,00 €", font=f_big, fill=255, anchor="mm")
        grad = Image.new("RGB", (W, H))
        grad.paste(GOLD_HI, (0, 0, W, H // 2))
        grad.paste(GOLD, (0, H // 2, W, int(H * 0.72)))
        grad.paste(GOLD_LO, (0, int(H * 0.72), W, H))
        grad = grad.filter(ImageFilter.GaussianBlur(28))
        layer.paste(grad, (0, 0), mask)
        draw_sparkle(d, W / 2 + 385, 1185, int(34 * (0.7 + 0.5 * abs(math.sin(t * 2.1)))), GOLD_HI, WHITE, rot=t * 0.8, alpha=a)
    a = int(255 * fade(t, 2.5, 2.9))
    if a:
        d.text((W / 2, 1565), "par mois. pour toujours.", font=MONT(31), fill=(214, 220, 238, a), anchor="mm")
    return Image.alpha_composite(frame, layer)

def s8_cta(t, dur):
    frame = Image.new("RGBA", (W, H), (6, 6, 12, 255))
    glow = radial_glow((W, H), (W / 2, 640), 780, GOLD, 68)
    frame = Image.alpha_composite(frame, glow)
    layer = new_layer(); d = ImageDraw.Draw(layer)
    for x, y, r, a in dust(t, 47, 60, area=(0, 150, W, 1300), rise=42):
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD + (a,))

    # MADGIC wordmark with vertical gold gradient
    lf = ANTON(252)
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.text((W / 2, 770), "MADGIC", font=lf, fill=255, anchor="mm")
    grad = Image.new("RGB", (W, H))
    grad.paste((255, 252, 230), (0, 0, W, 480))
    grad.paste(GOLD, (0, 480, W, 830))
    grad.paste(GOLD_LO, (0, 830, W, H))
    grad = grad.filter(ImageFilter.GaussianBlur(20))
    layer.paste(grad, (0, 0), mask)
    # sparkle on the M
    pulse = 0.65 + 0.45 * abs(math.sin(t * 1.8))
    draw_sparkle(d, W / 2 + 330, 560, int(46 * pulse), GOLD_HI, WHITE, rot=t * 0.9, alpha=255)
    draw_sparkle(d, W / 2 - 395, 640, int(26 * pulse), GOLD, WHITE, rot=-t * 0.7, alpha=220)

    a = int(255 * fade(t, 0.9, 1.4))
    if a:
        d.text((W / 2, 1005), "Toutes les IA. Un agent surpuissant.", font=MONT(33), fill=(238, 240, 250, a), anchor="mm")
    a = int(255 * fade(t, 1.25, 1.7))
    if a:
        d.text((W / 2, 1075), "GRATUITEMENT.", font=MONTBB(36), fill=GOLD + (a,), anchor="mm")

    # CTA pill
    p = fade(t, 1.8, 2.25)
    if p > 0:
        sc = 1 + 0.035 * math.sin(t * 3.4) * p
        pw, ph = int(690 * sc), int(158 * sc)
        px, py = W / 2 - pw / 2, 1240
        glow2 = radial_glow((W, H), (W / 2, py + ph / 2), int(340 * sc), GOLD, int(110 * p))
        frame2 = Image.alpha_composite(frame, glow2)
        layer = Image.alpha_composite(frame2, layer)
        d = ImageDraw.Draw(layer)
        pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        pd_ = ImageDraw.Draw(pill)
        rrect(pd_, [0, 0, pw - 1, ph - 1], ph // 2, fill=GOLD + (int(255 * p),))
        tracked(pd_, pw / 2, ph / 2 + 2, "Cherche « madgic »", MONTBB(46), (26, 18, 6, int(255 * p)), anchor="mm")
        layer.paste(pill, (int(px), int(py)), pill)
    a = int(255 * fade(t, 2.3, 2.7))
    if a:
        d.text((W / 2, 1465), "partout sur internet", font=MONT(27), fill=MUTED + (a,), anchor="mm")
    tracked(d, W / 2, 1725, "M A D G I C   —   L ' I N F O   Q U I   A I D E", MONTB(22), (120, 128, 158, int(200 * fade(t, 0.6, 1.2))), tracking=1)

    # fade to black at the very end
    fo = fade(t, dur - 1.5, dur - 0.15)
    if fo > 0:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * fo)))
    return Image.alpha_composite(frame, layer)

SCENE_DRAW = {
    "s1_intro": s1_intro, "s2_search": s2_search, "s3_prices": s3_prices,
    "s4_notif": s4_notif, "s5_discovery": s5_discovery, "s6_product": s6_product,
    "s7_benefits": s7_benefits, "s8_cta": s8_cta,
}

def render_frame(gt):
    scene = next((s for s in TIMELINE["scenes"] if s["start"] <= gt < s["start"] + s["duration"]),
                 TIMELINE["scenes"][-1])
    t = gt - scene["start"]
    img = SCENE_DRAW[scene["key"]](t, scene["duration"]).convert("RGB")
    img = Image.alpha_composite(img.convert("RGBA"), progress_bar(gt)).convert("RGB")
    # fade from black at the very beginning
    fi = fade(gt, 0.0, 0.7)
    if fi < 1:
        img = ImageEnhance_brightness(img, fi * fi * 0.9 + 0.05)
    img = apply_vignette_and_grain(img, seed=int(gt * FPS) + 7)
    return img

def main():
    sample = os.environ.get("SAMPLE_TIMES")
    if sample:
        for ts in sample.split(","):
            gt = float(ts)
            out = f"assets/build/sample_{gt:.2f}.png"
            render_frame(gt).save(out)
            print("wrote", out)
        return
    n_frames = int(TOTAL * FPS)
    FF = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [FF, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "assets/audio/mix.wav",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "medium",
           "-profile:v", "high", "-tune", "film",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-shortest", "madgic_promo.mp4"]
    print(f"rendering {n_frames} frames…", flush=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(n_frames):
        gt = i / FPS
        frame = render_frame(gt)
        proc.stdin.write(frame.tobytes())
        if i % 150 == 0:
            print(f"  frame {i}/{n_frames} ({gt:.1f}s)", flush=True)
    proc.stdin.close()
    proc.wait()
    print("encoded madgic_promo.mp4")

if __name__ == "__main__":
    main()
