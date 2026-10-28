"""Telegram Ads haqida vertikal (1080x1920) promo video yaratadi.

Ishga tushirish:  python3 make_video.py
Natija:          telegram-ads.mp4 (shu papkada)
Talab:           Pillow, numpy, ffmpeg
"""
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "telegram-ads.mp4")
AUDIO = os.path.join(HERE, "_music.wav")

FONT_DIR = "/usr/share/fonts/opentype/inter/"
BG = (7, 17, 31)
BLUE = (0, 170, 255)
TG = (42, 171, 238)
PURPLE = (108, 92, 231)
WHITE = (255, 255, 255)
MUTED = (184, 197, 214)
CARD = (13, 28, 48)
BORDER = (28, 48, 72)


def font(weight, size):
    name = {"xb": "Inter-ExtraBold.otf", "b": "Inter-Bold.otf",
            "sb": "Inter-SemiBold.otf", "m": "Inter-Medium.otf",
            "r": "Inter-Regular.otf"}[weight]
    return ImageFont.truetype(FONT_DIR + name, size)


# ---------------------------------------------------------------- helpers

def ease_out(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_back(p):
    p = max(0.0, min(1.0, p))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def wrap(text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            test = (cur + " " + word).strip()
            if fnt.getlength(test) <= max_w:
                cur = test
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def text_img(text, fnt, color=WHITE, max_w=W - 160, align="center", spacing=1.25):
    lines = wrap(text, fnt, max_w)
    asc, desc = fnt.getmetrics()
    lh = int((asc + desc) * spacing)
    w = int(max(fnt.getlength(l) for l in lines)) + 8
    h = lh * len(lines) + 8
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        lw = fnt.getlength(l)
        x = {"center": (w - lw) / 2, "left": 0}[align]
        d.text((x, i * lh), l, font=fnt, fill=color)
    return im


def gradient_text(text, fnt, c1=BLUE, c2=PURPLE, max_w=W - 160):
    mask = text_img(text, fnt, WHITE, max_w)
    w, h = mask.size
    grad = np.zeros((h, w, 4), dtype=np.uint8)
    t = np.linspace(0, 1, w)[None, :, None]
    grad[..., :3] = (np.array(c1) * (1 - t) + np.array(c2) * t).astype(np.uint8)
    grad[..., 3] = np.array(mask)[..., 3]
    return Image.fromarray(grad, "RGBA")


def rounded(w, h, r, fill, outline=None, width=2):
    s = 2
    im = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), r * s, fill=fill,
                        outline=outline, width=width * s)
    return im.resize((w, h), Image.LANCZOS)


def tg_logo(size):
    """Telegram uslubidagi doira + qog'oz samolyot."""
    s = 4
    S = size * s
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / S
        c = tuple(int(a * (1 - t) + b * t) for a, b in zip((55, 187, 254), (34, 158, 217)))
        gd.line((0, y, S, y), fill=c + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, S - 1, S - 1), fill=255)
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    k = S / 240
    plane = [(54, 118), (176, 70), (158, 170), (122, 146), (104, 162), (102, 136), (150, 94), (92, 130)]
    d.polygon([(x * k, y * k) for x, y in plane], fill=WHITE)
    d.polygon([(x * k, y * k) for x, y in [(92, 130), (102, 136), (104, 162), (96, 134)]], fill=(200, 218, 234))
    return im.resize((size, size), Image.LANCZOS)


def glow(size, color, alpha=110):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((size * .2, size * .2, size * .8, size * .8), fill=color + (alpha,))
    return im.filter(ImageFilter.GaussianBlur(size * .12))


def number_badge(n, size=84):
    im = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size * 2 - 1, size * 2 - 1), fill=BLUE)
    f = font("xb", int(size * 1.0))
    t = str(n)
    d.text((size - f.getlength(t) / 2, size * 0.42), t, font=f, fill=WHITE)
    return im.resize((size, size), Image.LANCZOS)


def check_icon(size=64, color=BLUE):
    s = 4
    im = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size * s - 1, size * s - 1), fill=color + (45,), outline=color, width=3 * s)
    k = size * s
    d.line([(k * .28, k * .52), (k * .44, k * .68), (k * .72, k * .36)], fill=color, width=int(k * .09), joint="curve")
    return im.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------- elements

class El:
    def __init__(self, img, x, y, start=0.0, anim="up", dur=0.6):
        self.img, self.x, self.y = img, x, y
        self.start, self.anim, self.dur = start, anim, dur
        self._cache = {}

    def faded(self, a):
        key = int(a * 20)
        if key not in self._cache:
            im = self.img.copy()
            al = np.array(im.getchannel("A"), dtype=np.float32) * (key / 20)
            im.putalpha(Image.fromarray(al.astype(np.uint8)))
            self._cache[key] = im
        return self._cache[key]

    def draw(self, frame, t, scene_alpha):
        p = (t - self.start) / self.dur
        if p <= 0:
            return
        e = ease_out(p)
        x, y = self.x, self.y
        img = self.img
        if self.anim == "up":
            y += int((1 - e) * 70)
        elif self.anim == "left":
            x -= int((1 - e) * 120)
        elif self.anim == "right":
            x += int((1 - e) * 120)
        elif self.anim == "pop":
            sc = max(0.05, ease_back(p))
            nw, nh = max(1, int(img.width * sc)), max(1, int(img.height * sc))
            img = img.resize((nw, nh), Image.BILINEAR)
            x += (self.img.width - nw) // 2
            y += (self.img.height - nh) // 2
        a = min(1.0, e) * scene_alpha
        if a <= 0.02:
            return
        im = img if self.anim == "pop" else self.faded(a)
        if self.anim == "pop" and a < 0.99:
            al = np.array(im.getchannel("A"), dtype=np.float32) * a
            im = im.copy()
            im.putalpha(Image.fromarray(al.astype(np.uint8)))
        frame.alpha_composite(im, (int(x), int(y)))


def cx(img):
    return (W - img.width) // 2


class Scene:
    def __init__(self, dur):
        self.dur = dur
        self.els = []
        self.dynamic = []  # funksiyalar: f(frame, t, alpha)

    def add(self, img, x=None, y=0, start=0.0, anim="up", dur=0.6):
        if x is None:
            x = cx(img)
        self.els.append(El(img, x, y, start, anim, dur))
        return img

    def render(self, frame, t):
        fade = 0.35
        a = 1.0
        if t > self.dur - fade:
            a = max(0.0, (self.dur - t) / fade)
        for el in self.els:
            el.draw(frame, t, a)
        for f in self.dynamic:
            f(frame, t, a)


def header(sc, kicker, title, y=250):
    k = text_img(kicker.upper(), font("b", 34), BLUE)
    sc.add(k, y=y, start=0.0)
    t = text_img(title, font("xb", 84), WHITE, max_w=W - 140, spacing=1.12)
    sc.add(t, y=y + 70, start=0.12)
    return y + 70 + t.height


# ----------------------------------------------------------------- scenes

def build_scenes():
    scenes = []

    # 1. Intro
    s = Scene(5.5)
    logo = tg_logo(340)
    s.add(glow(900, TG, 120), y=380, anim="fade", dur=1.2)
    s.add(logo, y=660, start=0.1, anim="pop", dur=0.8)
    s.add(text_img("TELEGRAM", font("xb", 130)), y=1080, start=0.6)
    s.add(gradient_text("ADS", font("xb", 200), TG, PURPLE), y=1220, start=0.8)
    s.add(text_img("Biznesingiz uchun yangi reklama imkoniyati", font("m", 46), MUTED, max_w=860), y=1500, start=1.2)
    s.add(text_img("G‘UZOR ADS", font("xb", 40), BLUE), y=1760, start=1.6, anim="fade")
    scenes.append(s)

    # 2. Nima?
    s = Scene(7.5)
    y = header(s, "1-qism", "Telegram Ads nima?")
    box = rounded(920, 520, 40, CARD + (255,), BORDER + (255,), 3)
    bd = ImageDraw.Draw(box)
    txt = text_img("Telegram’ning rasmiy reklama platformasi. Reklamangiz minglab obunachili ochiq kanallarda, "
                   "botlarda va qidiruvda ko‘rsatiladi.", font("m", 50), WHITE, max_w=820, align="left", spacing=1.35)
    box.alpha_composite(txt, (50, (520 - txt.height) // 2))
    s.add(box, y=y + 120, start=0.5)
    s.add(text_img("ads.telegram.org", font("b", 56), TG), y=y + 740, start=1.2)
    s.add(text_img("Rasmiy • Xavfsiz • Spam emas", font("m", 42), MUTED), y=y + 840, start=1.5)
    scenes.append(s)

    # 3. Raqamlar
    s = Scene(7.0)
    y = header(s, "2-qism", "Nega aynan Telegram?")
    stats = [(1, " mlrd+", "oylik faol foydalanuvchi"),
             (1, "-o‘rin", "O‘zbekistondagi eng mashhur messenjer"),
             (1000, "+", "obunachili kanallarda reklama")]
    for i, (num, suf, label) in enumerate(stats):
        top = y + 110 + i * 330
        card = rounded(920, 290, 36, CARD + (255,), BORDER + (255,), 3)
        card.alpha_composite(text_img(label, font("m", 42), MUTED, max_w=840, align="left"), (50, 175))
        st = 0.4 + i * 0.35
        s.add(card, y=top, start=st)

        def counter(frame, t, a, num=num, suf=suf, top=top, st=st):
            p = ease_out((t - st - 0.2) / 1.2)
            if t < st or a <= 0:
                return
            val = int(round(num * p)) if num > 1 else 1
            sval = f"{val:,}".replace(",", " ")
            im = gradient_text(sval + suf, font("xb", 112), BLUE, PURPLE, max_w=900)
            al = np.array(im.getchannel("A"), dtype=np.float32) * a * ease_out((t - st) / 0.6)
            im.putalpha(Image.fromarray(al.astype(np.uint8)))
            frame.alpha_composite(im, (130, top + 30))
        s.dynamic.append(counter)
    scenes.append(s)

    # 4. Afzalliklar
    s = Scene(8.0)
    y = header(s, "3-qism", "Afzalliklari")
    items = [("Aniq targeting", "Kanal, mavzu, til va hudud bo‘yicha"),
             ("Kam raqobat", "Raqobat hali past — reklama arzonroq"),
             ("Sifatli auditoriya", "Faol, o‘qiydigan va qiziqqan odamlar"),
             ("To‘liq nazorat", "Byudjet, CPM va statistika qo‘lingizda")]
    for i, (a, b) in enumerate(items):
        top = y + 110 + i * 255
        card = rounded(920, 220, 32, CARD + (255,), BORDER + (255,), 3)
        card.alpha_composite(check_icon(84), (40, 68))
        card.alpha_composite(text_img(a, font("b", 52), WHITE, align="left", max_w=740), (150, 42))
        card.alpha_composite(text_img(b, font("r", 36), MUTED, align="left", max_w=740), (150, 120))
        s.add(card, y=top, start=0.4 + i * 0.4, anim="left")
    scenes.append(s)

    # 5. Format (mock post)
    s = Scene(8.0)
    y = header(s, "4-qism", "Reklama qanday ko‘rinadi?")
    phone = rounded(860, 1120, 60, (17, 33, 52, 255), (40, 64, 92, 255), 4)
    pd = ImageDraw.Draw(phone)
    pd.rectangle((4, 70, 856, 170), fill=(22, 42, 64))
    phone.alpha_composite(tg_logo(76), (40, 82))
    phone.alpha_composite(text_img("Yangiliklar kanali", font("b", 40), WHITE, align="left"), (136, 84))
    phone.alpha_composite(text_img("152 400 obunachi", font("r", 28), MUTED, align="left"), (136, 132))
    post = rounded(700, 150, 26, (30, 52, 78, 255))
    phone.alpha_composite(post, (40, 220))
    s.add(phone, y=y + 90, start=0.3)
    # Reklama pufakchasi
    ad = rounded(780, 600, 30, (36, 62, 94, 255), BLUE + (255,), 3)
    ad.alpha_composite(text_img("Homiylik (reklama)", font("sb", 32), BLUE, align="left"), (36, 30))
    ad.alpha_composite(rounded(708, 210, 20, (52, 88, 130, 255)), (36, 84))
    ad.alpha_composite(text_img("RASM / VIDEO", font("b", 40), (150, 190, 230), align="left"), (240, 165))
    ad.alpha_composite(text_img("Matn 160 belgigacha — qisqa, aniq va qiziqarli taklif.",
                                font("m", 36), WHITE, max_w=700, align="left"), (36, 320))
    btn = rounded(708, 96, 22, BLUE + (255,))
    btn.alpha_composite(text_img("BATAFSIL", font("b", 38)), ((708 - 180) // 2, 26))
    ad.alpha_composite(btn, (36, 470))
    s.add(ad, y=y + 520, start=1.1, anim="pop", dur=0.8)
    scenes.append(s)

    # 6. Targeting
    s = Scene(7.5)
    y = header(s, "5-qism", "Targeting turlari")
    tg_items = [("Kanallar", "Aniq kanallarni tanlash"), ("Mavzular", "Biznes, ta’lim, sport..."),
                ("Til va hudud", "O‘zbek tili, O‘zbekiston"), ("Bot va qidiruv", "Yangi joylashuvlar")]
    for i, (a, b) in enumerate(tg_items):
        col, row = i % 2, i // 2
        card = rounded(445, 420, 34, CARD + (255,), BORDER + (255,), 3)
        cd = ImageDraw.Draw(card)
        cd.ellipse((40, 44, 140, 144), fill=PURPLE if i % 3 else BLUE)
        cd.text((90 - font("xb", 54).getlength(str(i + 1)) / 2, 58), str(i + 1), font=font("xb", 54), fill=WHITE)
        card.alpha_composite(text_img(a, font("b", 46), WHITE, align="left", max_w=380), (40, 190))
        card.alpha_composite(text_img(b, font("r", 34), MUTED, align="left", max_w=370), (40, 270))
        s.add(card, x=85 + col * 465, y=y + 110 + row * 450, start=0.4 + i * 0.3, anim="pop", dur=0.7)
    scenes.append(s)

    # 7. Qadamlar
    s = Scene(9.0)
    y = header(s, "6-qism", "Qanday boshlash kerak?")
    steps = ["ads.telegram.org’da akkaunt oching", "Balansni TON orqali to‘ldiring",
             "Reklama matni va mediani tayyorlang", "Auditoriya va CPM’ni belgilang",
             "Moderatsiyadan o‘tib, natijani kuzating"]
    for i, st in enumerate(steps):
        top = y + 100 + i * 200
        row = Image.new("RGBA", (920, 170), (0, 0, 0, 0))
        row.alpha_composite(rounded(920, 170, 30, CARD + (255,), BORDER + (255,), 3))
        row.alpha_composite(number_badge(i + 1, 96), (36, 37))
        label = text_img(st, font("sb", 42), WHITE, align="left", max_w=740)
        row.alpha_composite(label, (160, (170 - label.height) // 2))
        s.add(row, y=top, start=0.4 + i * 0.45, anim="right")
    scenes.append(s)

    # 8. Narx
    s = Scene(7.0)
    y = header(s, "7-qism", "Narx qanday hisoblanadi?")
    s.add(gradient_text("CPM", font("xb", 220), TG, PURPLE), y=y + 90, start=0.4, anim="pop", dur=0.8)
    s.add(text_img("1 000 ta ko‘rish uchun to‘lov", font("b", 54), WHITE), y=y + 380, start=0.9)
    lines = ["To‘lov TON (Toncoin) orqali", "Kunlik va umumiy byudjet limiti", "Yuqori CPM — ko‘proq ko‘rish"]
    for i, l in enumerate(lines):
        row = Image.new("RGBA", (900, 90), (0, 0, 0, 0))
        row.alpha_composite(check_icon(64), (0, 13))
        row.alpha_composite(text_img(l, font("m", 42), MUTED, align="left", max_w=800), (90, 18))
        s.add(row, y=y + 540 + i * 120, start=1.4 + i * 0.35, anim="left")
    scenes.append(s)

    # 9. Maslahatlar
    s = Scene(8.0)
    y = header(s, "8-qism", "Samarali reklama sirlari")
    tips = [("Qisqa yozing", "Birinchi so‘zlar diqqatni tortsin"),
            ("Aniq taklif bering", "Chegirma, bonus yoki bepul maslahat"),
            ("A/B test qiling", "Bir nechta matnni sinab ko‘ring"),
            ("Tahlil qiling", "CTR va konversiyani kuzating")]
    for i, (a, b) in enumerate(tips):
        top = y + 110 + i * 255
        card = rounded(920, 220, 32, CARD + (255,), BORDER + (255,), 3)
        card.alpha_composite(number_badge(i + 1, 84), (40, 68))
        card.alpha_composite(text_img(a, font("b", 52), WHITE, align="left", max_w=740), (150, 42))
        card.alpha_composite(text_img(b, font("r", 36), MUTED, align="left", max_w=740), (150, 120))
        s.add(card, y=top, start=0.4 + i * 0.4, anim="right")
    scenes.append(s)

    # 10. CTA
    s = Scene(8.0)
    s.add(glow(1000, BLUE, 110), y=200, anim="fade", dur=1.0)
    s.add(text_img("Telegram Ads’ni", font("xb", 90)), y=420, start=0.1)
    s.add(gradient_text("biz bilan boshlang!", font("xb", 90), BLUE, PURPLE), y=530, start=0.3)
    s.add(text_img("Sozlash, matn, dizayn va tahlil — hammasini G‘uzor Ads bajaradi.",
                   font("m", 44), MUTED, max_w=860), y=720, start=0.7)
    logo_card = rounded(920, 520, 44, CARD + (255,), BLUE + (255,), 3)
    logo_card.alpha_composite(text_img("G‘UZOR ADS", font("xb", 96), BLUE), ((920 - text_img("G‘UZOR ADS", font("xb", 96)).width) // 2, 60))
    logo_card.alpha_composite(text_img("Marketing & SMM Agency", font("m", 38), MUTED), ((920 - text_img("Marketing & SMM Agency", font("m", 38)).width) // 2, 185))
    tl = tg_logo(70)
    tgline = text_img("t.me/GuzorAds", font("b", 56), WHITE)
    lw = 70 + 24 + tgline.width
    logo_card.alpha_composite(tl, ((920 - lw) // 2, 290))
    logo_card.alpha_composite(tgline, ((920 - lw) // 2 + 94, 292))
    ph = text_img("+998 95 008 35 07", font("b", 52), WHITE)
    logo_card.alpha_composite(ph, ((920 - ph.width) // 2, 400))
    s.add(logo_card, y=980, start=1.1, anim="pop", dur=0.8)
    btn = rounded(700, 120, 60, BLUE + (255,))
    bt = text_img("BEPUL MASLAHAT OLING", font("xb", 44))
    btn.alpha_composite(bt, ((700 - bt.width) // 2, (120 - bt.height) // 2 + 4))
    s.add(btn, y=1600, start=1.8, anim="pop", dur=0.7)
    scenes.append(s)
    return scenes


# ------------------------------------------------------------- background

def make_background():
    base = np.zeros((H, W, 3), dtype=np.float32)
    base[:] = BG
    return Image.fromarray(base.astype(np.uint8)).convert("RGBA")


def grid_overlay():
    im = Image.new("RGBA", (W, H + 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 120):
        d.line((x, 0, x, H + 120), fill=(255, 255, 255, 8))
    for y in range(0, H + 120, 120):
        d.line((0, y, W, y), fill=(255, 255, 255, 8))
    return im


# ------------------------------------------------------------------ music

def make_music(seconds, path, sr=44100):
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n, dtype=np.float64)
    bpm = 100
    beat = 60 / bpm
    bar = beat * 4

    def midi(m):
        return 440 * 2 ** ((m - 69) / 12)

    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    bass = [45, 41, 36, 43]
    nbars = int(seconds / bar) + 1
    for b in range(nbars):
        s0 = int(b * bar * sr)
        s1 = min(n, int((b + 1) * bar * sr))
        if s0 >= n:
            break
        tt = np.arange(s1 - s0) / sr
        env = np.minimum(1, tt / 0.4) * np.minimum(1, (bar - tt) / 0.4)
        ch = chords[b % 4]
        for m in ch + [ch[0] + 12]:
            f = midi(m)
            out[s0:s1] += 0.045 * env * (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.003 * tt))
        fb = midi(bass[b % 4])
        for k in range(4):
            k0 = s0 + int(k * beat * sr)
            k1 = min(s1, k0 + int(beat * sr))
            kt = np.arange(k1 - k0) / sr
            out[k0:k1] += 0.10 * np.sin(2 * np.pi * fb * kt) * np.exp(-kt * 3)
        # arpeggio
        for k in range(8):
            a0 = s0 + int(k * beat / 2 * sr)
            a1 = min(s1, a0 + int(beat / 2 * sr))
            at = np.arange(a1 - a0) / sr
            m = (ch + [ch[0] + 12])[[0, 1, 2, 3, 2, 1, 0, 1][k]] + 12
            out[a0:a1] += 0.035 * np.sin(2 * np.pi * midi(m) * at) * np.exp(-at * 6)
    # drums
    rng = np.random.default_rng(1)
    nbeats = int(seconds / beat)
    for k in range(nbeats):
        if k < 4:
            continue
        k0 = int(k * beat * sr)
        L = min(n - k0, int(0.35 * sr))
        kt = np.arange(L) / sr
        if k % 2 == 0:
            freq = 110 * np.exp(-kt * 18) + 45
            out[k0:k0 + L] += 0.35 * np.sin(2 * np.pi * np.cumsum(freq) / sr) * np.exp(-kt * 9)
        else:
            out[k0:k0 + L] += 0.10 * rng.standard_normal(L) * np.exp(-kt * 22)
        h0 = k0 + int(beat / 2 * sr)
        if h0 < n:
            HL = min(n - h0, int(0.05 * sr))
            hn = rng.standard_normal(HL)
            hn = np.diff(hn, prepend=0)
            out[h0:h0 + HL] += 0.05 * hn * np.exp(-np.arange(HL) / sr * 60)
    fade = int(2.5 * sr)
    out[:int(0.5 * sr)] *= np.linspace(0, 1, int(0.5 * sr))
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / (np.max(np.abs(out)) + 1e-9) * 0.8
    pcm = (out * 32767).astype(np.int16)
    stereo = np.stack([pcm, pcm], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(stereo.tobytes())


# ------------------------------------------------------------------- main

def main():
    scenes = build_scenes()
    total = sum(s.dur for s in scenes)
    make_music(total, AUDIO)

    bg = make_background()
    grid = grid_overlay()
    g1, g2 = glow(1100, BLUE, 70), glow(1000, PURPLE, 60)
    bar_bg = Image.new("RGBA", (W, 8), (255, 255, 255, 25))

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", AUDIO,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    nframes = int(total * FPS)
    scene_starts = np.cumsum([0] + [s.dur for s in scenes])
    for i in range(nframes):
        gt = i / FPS
        si = int(np.searchsorted(scene_starts, gt, side="right") - 1)
        si = min(si, len(scenes) - 1)
        t = gt - scene_starts[si]

        frame = bg.copy()
        frame.alpha_composite(g1, (int(-350 + 200 * math.sin(gt * 0.35)), int(-250 + 150 * math.cos(gt * 0.27))))
        frame.alpha_composite(g2, (int(450 + 180 * math.cos(gt * 0.3)), int(1150 + 160 * math.sin(gt * 0.22))))
        frame.alpha_composite(grid, (0, -int((gt * 20) % 120)))
        scenes[si].render(frame, t)
        # progress bar
        frame.alpha_composite(bar_bg, (0, H - 8))
        pw = int(W * gt / total)
        if pw > 0:
            frame.alpha_composite(Image.new("RGBA", (pw, 8), BLUE + (255,)), (0, H - 8))
        proc.stdin.write(frame.convert("RGB").tobytes())
        if i % 300 == 0:
            print(f"{i}/{nframes}", flush=True)

    proc.stdin.close()
    proc.wait()
    os.remove(AUDIO)
    print("Tayyor:", OUT)


if __name__ == "__main__":
    main()
