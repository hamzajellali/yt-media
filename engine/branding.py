"""Gravity Candy logo (800x800) and banner (2560x1440)."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG = (10, 12, 24)
CANDY = [(255, 92, 168), (255, 196, 60), (80, 220, 255), (140, 255, 120), (190, 120, 255)]


def glow_ring(img, cx, cy, r, col, width, blur):
    g = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(g).ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=width * 3)
    g = g.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.blend(img, Image.eval(g, lambda v: v), 0.0), (0, 0))
    out = Image.composite(g, img, g.convert("L").point(lambda v: min(255, v * 2)))
    d = ImageDraw.Draw(out)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=width)
    return out


def balls(d, cx, cy, R, scale=1.0):
    spec = [(-0.35, 0.30, 0.30), (0.30, 0.38, 0.22), (0.05, -0.05, 0.16), (-0.12, 0.62, 0.12), (0.42, -0.02, 0.10)]
    for (fx, fy, fr), col in zip(spec, CANDY):
        x, y, r = cx + fx * R, cy + fy * R, fr * R
        d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(255, 255, 255), width=max(3, int(5 * scale)))
        hr = r * 0.28
        d.ellipse([x - r * 0.45 - hr, y - r * 0.45 - hr, x - r * 0.45 + hr, y - r * 0.45 + hr], fill=(255, 255, 255))


def logo(path):
    S = 800
    img = Image.new("RGB", (S, S), BG)
    img = glow_ring(img, S // 2, S // 2, 300, (255, 92, 168), 14, 22)
    balls(ImageDraw.Draw(img), S // 2, S // 2, 300)
    img.save(path)


def banner(path):
    W, H = 2560, 1440
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # scattered background balls
    import random
    random.seed(7)
    for _ in range(70):
        x, y, r = random.randint(0, W), random.randint(0, H), random.randint(8, 46)
        if 480 < x < 2080 and 480 < y < 960:
            continue
        col = tuple(int(c * 0.45) for c in random.choice(CANDY))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    cy = H // 2
    img = glow_ring(img, 680, cy, 150, (80, 220, 255), 10, 16)
    balls(ImageDraw.Draw(img), 680, cy, 150, 0.7)
    d = ImageDraw.Draw(img)
    d.text((865, cy - 36), "GRAVITY CANDY", font=ImageFont.truetype(FONT, 112), fill=(255, 255, 255), anchor="lm")
    d.text((869, cy + 62), "Satisfying physics simulations  •  New Short every day",
           font=ImageFont.truetype(FONT, 38), fill=(255, 196, 60), anchor="lm")
    img.save(path)


if __name__ == "__main__":
    logo("/home/claude/gc/logo.png")
    banner("/home/claude/gc/banner.png")
