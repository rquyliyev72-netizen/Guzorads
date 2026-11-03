"""G'uzor Ads — Instagram Reels video (1080x1920, 30fps, ~16s).

Colors and text come from the site's index.html:
  --bg #07111f, --card #0d1c30, --line #1c3048, --primary #008cff,
  --accent #00aaff, --accent-2 #6c5ce7, --muted #9eacbe.

Run: python3 video/make_reel.py   (needs Pillow, numpy, ffmpeg)
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
DUR = 16.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guzor_ads_reel.mp4")

BG = (7, 17, 31)
CARD = (13, 28, 48)
LINE = (28, 48, 72)
PRIMARY = (0, 140, 255)
ACCENT = (0, 170, 255)
ACCENT2 = (108, 92, 231)
MUTED = (158, 172, 190)
WHITE = (255, 255, 255)
GREEN = (126, 224, 168)

FD = "/usr/share/fonts/opentype/inter/"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"


def font(weight, size, display=True):
    return ImageFont.truetype(f"{FD}{'InterDisplay' if display else 'Inter'}-{weight}.otf", size)


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in(x):
    return x ** 3


def ease_back(x, s=1.6):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


# ---------- primitives ----------
def gradient(w, h, c1, c2, angle=135):
    """Linear gradient like CSS linear-gradient(angle, c1, c2)."""
    a = math.radians(angle - 90)
    xs, ys = np.meshgrid(np.linspace(-0.5, 0.5, w), np.linspace(-0.5, 0.5, h))
    d = xs * math.cos(a) + ys * math.sin(a)
    d = (d - d.min()) / (d.max() - d.min() + 1e-9)
    c1, c2 = np.array(c1, float), np.array(c2, float)
    arr = c1 + (c2 - c1) * d[..., None]
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def rounded_mask(w, h, r, ss=3):
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], r * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def rounded(w, h, r, fill, outline=None, width=2, ss=3):
    """Anti-aliased rounded rect; fill may be a color or an RGBA image."""
    img = fill.resize((w, h)) if isinstance(fill, Image.Image) else Image.new("RGBA", (w, h), fill)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, (0, 0), rounded_mask(w, h, r, ss))
    if outline:
        o = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(o).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], r * ss, outline=255, width=width * ss)
        o = o.resize((w, h), Image.LANCZOS)
        out.paste(Image.new("RGBA", (w, h), outline), (0, 0), o)
    return out


def glow(img, radius=40, color=ACCENT, strength=0.6):
    """Add a soft colored glow behind an RGBA image (returns larger image)."""
    pad = radius * 2
    W2, H2 = img.width + pad * 2, img.height + pad * 2
    a = Image.new("L", (W2, H2), 0)
    a.paste(img.getchannel("A"), (pad, pad))
    a = a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * strength))
    g = Image.new("RGBA", (W2, H2), color + (0,))
    g.putalpha(a)
    g.alpha_composite(img, (pad, pad))
    return g, pad


def text_img(s, fnt, fill=WHITE):
    l, t, r, b = fnt.getbbox(s)
    im = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 2 - t), s, font=fnt, fill=fill)
    return im


def gradient_text(s, fnt, c1=ACCENT, c2=ACCENT2):
    m = text_img(s, fnt, WHITE)
    g = gradient(m.width, m.height, c1, c2, 90)
    g.putalpha(m.getchannel("A"))
    return g


def emoji(ch, size):
    f = ImageFont.truetype(EMOJI, 109)
    im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)


def fade(img, a):
    if a >= 0.999:
        return img
    im = img.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def scaled(img, s):
    if abs(s - 1) < 1e-3:
        return img
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BICUBIC)


def put(frame, img, cx, cy, alpha=1.0, scale=1.0):
    """Composite img centered at (cx, cy)."""
    if alpha <= 0.003:
        return
    im = fade(scaled(img, scale), alpha)
    frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)), ) if (
        0 <= int(cx - im.width / 2) and 0 <= int(cy - im.height / 2)
        and int(cx - im.width / 2) + im.width <= W and int(cy - im.height / 2) + im.height <= H
    ) else _put_clip(frame, im, int(cx - im.width / 2), int(cy - im.height / 2))


def _put_clip(frame, im, x, y):
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    layer.paste(im, (x, y), im)
    frame.alpha_composite(layer)


# ---------- static assets ----------
print("Assets...")


def make_background():
    """Big background with the site's radial glows; we pan across it over time."""
    BW, BH = W + 400, H + 400
    ys, xs = np.mgrid[0:BH, 0:BW].astype(np.float32)
    arr = np.zeros((BH, BW, 3), np.float32) + np.array(BG, np.float32)

    def blob(cx, cy, r, color, a):
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / r
        k = np.clip(1 - d, 0, 1) ** 2 * a
        return k[..., None] * (np.array(color, np.float32) - arr)

    arr += blob(BW * 0.82, BH * 0.22, 900, (0, 92, 255), 0.45)
    arr += blob(BW * 0.15, BH * 0.70, 850, (0, 170, 255), 0.25)
    arr += blob(BW * 0.60, BH * 0.95, 700, ACCENT2, 0.22)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    # subtle grid, like a dashboard
    d = ImageDraw.Draw(img)
    for x in range(0, BW, 90):
        d.line([(x, 0), (x, BH)], fill=(255, 255, 255, 0), width=1)
    grid = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, BW, 90):
        gd.line([(x, 0), (x, BH)], fill=(28, 48, 72, 70), width=1)
    for y in range(0, BH, 90):
        gd.line([(0, y), (BW, y)], fill=(28, 48, 72, 70), width=1)
    img.alpha_composite(grid)
    return img


BGIMG = make_background()


def logo_mark(size):
    m = rounded(size, size, int(size * 10 / 36), gradient(size, size, ACCENT, ACCENT2, 135))
    g = text_img("G", font("ExtraBold", int(size * 0.6)))
    m.alpha_composite(g, ((size - g.width) // 2, (size - g.height) // 2))
    return m


LOGO_BIG, LOGO_PAD = glow(logo_mark(260), 60, ACCENT, 0.7)
LOGO_SMALL = logo_mark(64)
BRAND = text_img("G‘UZOR ADS", font("ExtraBold", 110))
BRAND_SMALL = text_img("G‘UZOR ADS", font("ExtraBold", 38))
TAG = text_img("MARKETING  &  SMM  AGENCY", font("SemiBold", 34, False), MUTED)


def pill(label, fnt, fg=WHITE, fill=(0, 140, 255, 40), outline=(0, 170, 255, 140), padx=34, h=None):
    t = text_img(label, fnt, fg)
    h = h or t.height + 36
    p = rounded(t.width + padx * 2, h, h // 2, fill, outline, 2)
    p.alpha_composite(t, (padx, (h - t.height) // 2))
    return p


BADGE = pill("🚀  Marketing & SMM Agency".replace("🚀  ", ""), font("SemiBold", 34, False))
ROCKET = emoji("🚀", 44)
badge = Image.new("RGBA", (BADGE.width + 60, BADGE.height), (0, 0, 0, 0))
BADGE2 = pill("      Marketing & SMM Agency", font("SemiBold", 34, False))
BADGE2.alpha_composite(ROCKET, (30, (BADGE2.height - ROCKET.height) // 2))

# Hook lines
HOOK_F = font("ExtraBold", 118)
HOOK = [text_img("Biznesingizni", HOOK_F), gradient_text("raqamli dunyoda", HOOK_F), text_img("rivojlantiramiz.", HOOK_F)]
HOOK_SUB = [text_img(s, font("Medium", 40, False), MUTED) for s in
            ["SMM, Target, Kontent va Grafik dizayn —", "biznesingizni ko‘proq mijozlarga tanitamiz."]]

# Service cards
SERVICES = [
    ("📱", "SMM", "Instagram va Telegram sahifangizni\nprofessional yuritamiz"),
    ("🎯", "Target reklama", "Reklamangizni aynan kerakli\nauditoriyaga yetkazamiz"),
    ("🎬", "Kontent", "Reels, Stories va postlar uchun\nkreativ g‘oyalar"),
    ("🎨", "Grafik dizayn", "Zamonaviy banner, post va\nreklama dizaynlari"),
    ("✨", "Brending", "Logotip, rang palitrasi va\nyagona uslub"),
    ("💡", "Marketing maslahat", "Qaysi kanal va strategiya\nfoyda berishini aytamiz"),
]
CW, CH = 900, 180
card_bg = gradient(CW, CH, (16, 38, 65), (9, 24, 39), 145)


def service_card(icon, title, desc):
    c = rounded(CW, CH, 28, card_bg, LINE + (255,), 2)
    ib = rounded(120, 120, 28, gradient(120, 120, (0, 170, 255), (108, 92, 231), 135))
    e = emoji(icon, 64)
    ib.alpha_composite(e, ((120 - e.width) // 2, (120 - e.height) // 2))
    c.alpha_composite(ib, (36, (CH - 120) // 2))
    c.alpha_composite(text_img(title, font("Bold", 50)), (190, 28))
    y = 92
    for ln in desc.split("\n"):
        t = text_img(ln, font("Medium", 32, False), MUTED)
        c.alpha_composite(t, (205, y))
        y += 40
    return c


CARDS = [service_card(*s) for s in SERVICES]
SERV_TITLE = text_img("Bizning xizmatlar", font("ExtraBold", 92))
SERV_SUB = text_img("Barcha marketing xizmatlari — bir joyda", font("Medium", 38, False), MUTED)

# Results / stats scene
RES_TITLE = text_img("Reklama natijalari", font("ExtraBold", 92))
STAT_F = font("ExtraBold", 120)
STATS = [("6", "Xizmat yo‘nalishi"), ("24/7", "Aloqa"), ("100%", "Individual yondashuv")]
STAT_LAB = [text_img(l, font("SemiBold", 30, False), MUTED) for _, l in STATS]
PANEL_W, PANEL_H = 900, 640
PANEL = rounded(PANEL_W, PANEL_H, 36, gradient(PANEL_W, PANEL_H, (16, 38, 65), (9, 24, 39), 145), LINE + (255,), 2)
PANEL.alpha_composite(text_img("Qamrov", font("Bold", 44)), (50, 46))
LEAD = pill("📩 Yangi murojaat".replace("📩 ", "      "), font("Bold", 32, False), WHITE,
            (126, 224, 168, 40), (126, 224, 168, 170))
LEAD.alpha_composite(emoji("📩", 38), (30, (LEAD.height - 34) // 2 - 2))
CHECK_ITEMS = ["Individual strategiya", "Shaffof hisobot", "Mahalliy bozorni bilamiz", "Tezkor aloqa"]


def check_row(s):
    t = text_img(s, font("SemiBold", 42, False))
    b = rounded(58, 58, 16, gradient(58, 58, ACCENT, ACCENT2, 135))
    ImageDraw.Draw(b).line([(15, 30), (25, 40), (44, 19)], fill=WHITE, width=6, joint="curve")
    r = Image.new("RGBA", (t.width + 90, 64), (0, 0, 0, 0))
    r.alpha_composite(b, (0, 3))
    r.alpha_composite(t, (88, (64 - t.height) // 2))
    return r


CHECKS = [check_row(s) for s in CHECK_ITEMS]
WHY = text_img("Nega aynan G‘uzor Ads?", font("ExtraBold", 80))

# CTA
CTA_T1 = text_img("Biznesingizni", font("ExtraBold", 110))
CTA_T2 = gradient_text("o‘stirish vaqti keldi!", font("ExtraBold", 96))
BTN_W, BTN_H = 760, 150
BTN = rounded(BTN_W, BTN_H, 34, gradient(BTN_W, BTN_H, ACCENT, PRIMARY, 135))
bt = text_img("        Bepul maslahat", font("ExtraBold", 54))
BTN.alpha_composite(bt, ((BTN_W - bt.width) // 2, (BTN_H - bt.height) // 2))
be = emoji("💬", 56)
BTN.alpha_composite(be, ((BTN_W - bt.width) // 2 + 4, (BTN_H - be.height) // 2))
BTN_G, BTN_PAD = glow(BTN, 50, PRIMARY, 0.8)


def contact_row(icon_txt, label, color):
    ic = rounded(84, 84, 24, color + (255,))
    t = text_img(icon_txt, font("ExtraBold", 40))
    ic.alpha_composite(t, ((84 - t.width) // 2, (84 - t.height) // 2))
    lab = text_img(label, font("Bold", 50))
    r = rounded(800, 130, 30, CARD + (235,), LINE + (255,), 2)
    r.alpha_composite(ic, (30, 23))
    r.alpha_composite(lab, (140, (130 - lab.height) // 2))
    return r


TG = contact_row("✈", "t.me/GuzorAds", (34, 158, 217))
# The ✈ glyph may be missing in Inter; draw a paper plane instead
tgi = Image.new("RGBA", (84, 84), (0, 0, 0, 0))
d = ImageDraw.Draw(tgi)
d.rounded_rectangle([0, 0, 83, 83], 24, fill=(34, 158, 217))
d.polygon([(18, 42), (66, 22), (56, 64), (40, 52)], fill=WHITE)
d.polygon([(40, 52), (36, 66), (46, 56)], fill=(210, 230, 245))
TG = rounded(800, 130, 30, CARD + (235,), LINE + (255,), 2)
TG.alpha_composite(tgi, (30, 23))
tl = text_img("t.me/GuzorAds", font("Bold", 50))
TG.alpha_composite(tl, (140, (130 - tl.height) // 2))
PH = rounded(800, 130, 30, CARD + (235,), LINE + (255,), 2)
phi = rounded(84, 84, 24, gradient(84, 84, ACCENT, ACCENT2, 135))
pe = emoji("📞", 46)
phi.alpha_composite(pe, ((84 - pe.width) // 2, (84 - pe.height) // 2))
PH.alpha_composite(phi, (30, 23))
pl = text_img("+998 95 008 35 07", font("Bold", 50))
PH.alpha_composite(pl, (140, (130 - pl.height) // 2))


# ---------- scenes ----------
def scene_intro(f, t):
    # 0.0 - 3.0
    p = prog(t, 0.1, 0.8)
    s = 0.2 + 0.8 * ease_back(p) if p < 1 else 1.0
    rot_alpha = clamp(p * 2)
    out = prog(t, 2.6, 0.4)
    put(f, LOGO_BIG, W / 2, 760 - 120 * ease_in(out), rot_alpha * (1 - out), max(s, 0.01))
    pb = ease_out(prog(t, 0.8, 0.7))
    put(f, BRAND, W / 2, 1090 + 60 * (1 - pb) - 120 * ease_in(out), pb * (1 - out))
    pt = ease_out(prog(t, 1.2, 0.7))
    put(f, TAG, W / 2, 1200 + 40 * (1 - pt) - 120 * ease_in(out), pt * (1 - out))
    # underline sweep
    pl = ease_out(prog(t, 1.4, 0.8))
    if pl > 0:
        lw = int(520 * pl)
        line = gradient(max(lw, 2), 8, ACCENT, ACCENT2, 90)
        line = rounded(line.width, 8, 4, line)
        put(f, line, W / 2, 1270 - 120 * ease_in(out), 1 - out)


def scene_hook(f, t):
    # 3.0 - 6.4
    lt = t - 3.0
    out = ease_in(prog(t, 6.0, 0.4))
    put(f, BADGE2, W / 2, 620, ease_out(prog(lt, 0, 0.5)) * (1 - out))
    for i, im in enumerate(HOOK):
        p = ease_out(prog(lt, 0.2 + i * 0.25, 0.6))
        put(f, im, W / 2 - 160 * (1 - p) - 200 * out, 800 + i * 150, p * (1 - out))
    for i, im in enumerate(HOOK_SUB):
        p = ease_out(prog(lt, 1.2 + i * 0.15, 0.6))
        put(f, im, W / 2, 1300 + i * 58 + 30 * (1 - p), p * (1 - out))


def scene_services(f, t):
    # 6.4 - 10.4
    lt = t - 6.4
    out = ease_in(prog(t, 10.0, 0.4))
    pt = ease_out(prog(lt, 0, 0.5))
    put(f, SERV_TITLE, W / 2, 330 + 40 * (1 - pt), pt * (1 - out))
    put(f, SERV_SUB, W / 2, 430, ease_out(prog(lt, 0.2, 0.5)) * (1 - out))
    for i, c in enumerate(CARDS):
        p = ease_out(prog(lt, 0.4 + i * 0.22, 0.55))
        x = W / 2 + (1 if i % 2 else -1) * 700 * (1 - p)
        put(f, c, x, 580 + i * 196, p * (1 - out))


def draw_chart(f, t0, lt, alpha, ox, oy):
    """Animated growth chart inside the panel."""
    if alpha <= 0:
        return
    layer = Image.new("RGBA", (PANEL_W, PANEL_H), (0, 0, 0, 0))
    layer.alpha_composite(PANEL)
    d = ImageDraw.Draw(layer)
    # bars
    vals = [0.22, 0.30, 0.28, 0.42, 0.50, 0.63, 0.78, 0.95]
    bw, gap, base, top = 70, 32, 560, 170
    x0 = 60
    for i, v in enumerate(vals):
        p = ease_out(prog(lt, 0.3 + i * 0.09, 0.6))
        h = (base - top) * v * p
        if h < 2:
            continue
        bar = gradient(bw, int(h), ACCENT, ACCENT2, 180)
        bar = rounded(bw, int(h), 14, bar)
        layer.alpha_composite(bar, (x0 + i * (bw + gap), int(base - h)))
    # trend line
    pts = [(x0 + i * (bw + gap) + bw / 2, base - (base - top) * v - 30) for i, v in enumerate(vals)]
    pl = ease_out(prog(lt, 0.6, 1.2))
    n = pl * (len(pts) - 1)
    k = int(n)
    seg = pts[:k + 1]
    if k < len(pts) - 1:
        fr = n - k
        a, b = pts[k], pts[k + 1]
        seg = seg + [(a[0] + (b[0] - a[0]) * fr, a[1] + (b[1] - a[1]) * fr)]
    if len(seg) > 1:
        d.line(seg, fill=GREEN + (255,), width=7, joint="curve")
        ex, ey = seg[-1]
        d.ellipse([ex - 13, ey - 13, ex + 13, ey + 13], fill=GREEN + (255,))
    # percentage counter
    pct = int(248 * ease_out(prog(lt, 0.4, 1.6)))
    tx = text_img(f"+{pct}%", font("ExtraBold", 64), GREEN)
    layer.alpha_composite(tx, (PANEL_W - tx.width - 50, 36))
    put(f, layer, ox, oy, alpha)


def scene_results(f, t):
    # 10.4 - 13.0
    lt = t - 10.4
    out = ease_in(prog(t, 12.6, 0.4))
    pt = ease_out(prog(lt, 0, 0.5))
    put(f, RES_TITLE, W / 2, 330 + 40 * (1 - pt), pt * (1 - out))
    pp = ease_out(prog(lt, 0.1, 0.6))
    draw_chart(f, 10.4, lt, pp * (1 - out), W / 2, 720 + 80 * (1 - pp))
    # lead notification pops
    pn = prog(lt, 1.3, 0.5)
    if pn > 0:
        put(f, LEAD, W / 2 + 230, 1040, clamp(pn * 2) * (1 - out), max(0.01, ease_back(pn)))
    # stats row
    for i, (val, _) in enumerate(STATS):
        p = ease_out(prog(lt, 0.6 + i * 0.18, 0.6))
        if val == "6":
            v = str(int(round(6 * p)))
        elif val == "100%":
            v = f"{int(100 * p)}%"
        else:
            v = val
        im = gradient_text(v, STAT_F) if i == 1 else text_img(v, STAT_F)
        cx = 200 + i * 340
        put(f, im, cx, 1200 + 40 * (1 - p), p * (1 - out))
        put(f, STAT_LAB[i], cx, 1300 + 40 * (1 - p), p * (1 - out))
    # checklist
    for i, c in enumerate(CHECKS):
        p = ease_out(prog(lt, 1.0 + i * 0.15, 0.5))
        put(f, c, 140 + c.width / 2 + 60 * (1 - p), 1400 + i * 76, p * (1 - out))


def scene_cta(f, t):
    # 13.0 - 16.0
    lt = t - 13.0
    put(f, LOGO_SMALL, W / 2 - BRAND_SMALL.width / 2 - 20, 300, ease_out(prog(lt, 0, 0.5)))
    put(f, BRAND_SMALL, W / 2 + 44, 300, ease_out(prog(lt, 0, 0.5)))
    p1 = ease_out(prog(lt, 0.1, 0.6))
    put(f, CTA_T1, W / 2, 560 + 50 * (1 - p1), p1)
    p2 = ease_out(prog(lt, 0.3, 0.6))
    put(f, CTA_T2, W / 2, 700 + 50 * (1 - p2), p2)
    pb = prog(lt, 0.6, 0.6)
    pulse = 1 + 0.035 * math.sin(max(0, lt - 1.2) * 2 * math.pi * 1.1) if lt > 1.2 else 1
    if pb > 0:
        put(f, BTN_G, W / 2, 960, clamp(pb * 2), max(0.01, ease_back(pb) * pulse))
    for i, r in enumerate([TG, PH]):
        p = ease_out(prog(lt, 1.0 + i * 0.2, 0.6))
        put(f, r, W / 2, 1200 + i * 160 + 60 * (1 - p), p)
    pf = ease_out(prog(lt, 1.6, 0.6))
    put(f, FOOT, W / 2, 1560, pf)


FOOT = text_img("Narxlar biznesingizga qarab individual belgilanadi", font("Medium", 32, False), MUTED)

# persistent top/bottom chrome
PROG_Y = 70


def chrome(f, t):
    # progress bar in brand gradient (stories style)
    bar = Image.new("RGBA", (W - 120, 8), (255, 255, 255, 40))
    bar = rounded(W - 120, 8, 4, (255, 255, 255, 45))
    f.alpha_composite(bar, (60, PROG_Y))
    pw = max(8, int((W - 120) * t / DUR))
    f.alpha_composite(rounded(pw, 8, 4, gradient(pw, 8, ACCENT, ACCENT2, 90)), (60, PROG_Y))
    if 3.0 <= t < 13.0:
        a = clamp((t - 3.0) / 0.4) * clamp((13.0 - t) / 0.3)
        put(f, WATERMARK, W / 2, 150, a * 0.9)


WATERMARK = Image.new("RGBA", (LOGO_SMALL.width + 20 + BRAND_SMALL.width, 64), (0, 0, 0, 0))
_ls = scaled(LOGO_SMALL, 0.8)
WATERMARK.alpha_composite(_ls, (0, (64 - _ls.height) // 2))
WATERMARK.alpha_composite(BRAND_SMALL, (_ls.width + 16, (64 - BRAND_SMALL.height) // 2))

# floating particles
rng = np.random.default_rng(7)
PARTS = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(3, 8), rng.uniform(20, 60), rng.uniform(0, 6.28),
          ACCENT if rng.random() < 0.6 else ACCENT2) for _ in range(40)]


def background(t):
    ox = int(200 + 140 * math.sin(t * 0.35))
    oy = int(200 + 160 * math.cos(t * 0.28))
    f = BGIMG.crop((ox, oy, ox + W, oy + H)).copy()
    d = ImageDraw.Draw(f, "RGBA")
    for x, y, r, sp, ph, c in PARTS:
        yy = (y - sp * t) % H
        xx = x + 20 * math.sin(t + ph)
        a = int(90 + 70 * math.sin(t * 2 + ph))
        d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=c + (a,))
    return f


def render(t):
    f = background(t)
    if t < 3.0:
        scene_intro(f, t)
    elif t < 6.4:
        scene_hook(f, t)
    elif t < 10.4:
        scene_services(f, t)
    elif t < 13.0:
        scene_results(f, t)
    else:
        scene_cta(f, t)
    chrome(f, t)
    return f.convert("RGB")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--stills":
        os.makedirs(sys.argv[2], exist_ok=True)
        for t in [1.8, 5.2, 9.5, 12.2, 15.5]:
            render(t).save(os.path.join(sys.argv[2], f"t{t:04.1f}.png"))
        return
    n = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-shortest", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(render(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"frame {i}/{n}", flush=True)
    p.stdin.close()
    p.wait()
    print("Saved", OUT)


if __name__ == "__main__":
    main()
