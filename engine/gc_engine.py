#!/usr/bin/env python3
"""Gravity Candy video engine.

Everything is procedural: physics, graphics (cairo) and audio (numpy synth).
Melodies used are public-domain folk/carol/classical tunes.

Usage:
  python3 gc_engine.py short --seed 123 --out short.mp4 --meta short.json [--kind grow]
  python3 gc_engine.py long  --seed 123 --out long.mp4  --meta long.json --minutes 8
  python3 gc_engine.py thumb --seed 123 --out thumb.png --text "20 SATISFYING SIMULATIONS"
"""
import argparse, colorsys, json, math, random, subprocess, sys, wave
import numpy as np
import cairo

SR = 44100
FONT = "DejaVu Sans"

# ------------------------------------------------------------------ melodies (public domain)
MELODIES = {
    "Jingle Bells": "E5 E5 E5 E5 E5 E5 E5 G5 C5 D5 E5 F5 F5 F5 F5 F5 E5 E5 E5 E5 D5 D5 E5 D5 G5 "
                    "E5 E5 E5 E5 E5 E5 E5 G5 C5 D5 E5 F5 F5 F5 F5 F5 E5 E5 E5 G5 G5 F5 D5 C5",
    "Ode to Joy": "E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 E5 D5 D5 E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 D5 C5 C5 "
                  "D5 D5 E5 C5 D5 E5 F5 E5 C5 D5 E5 F5 E5 D5 C5 D5 G4 E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 D5 C5 C5",
    "Twinkle Twinkle Little Star": "C5 C5 G5 G5 A5 A5 G5 F5 F5 E5 E5 D5 D5 C5 G5 G5 F5 F5 E5 E5 D5 G5 G5 F5 F5 E5 E5 D5 "
                                   "C5 C5 G5 G5 A5 A5 G5 F5 F5 E5 E5 D5 D5 C5",
    "Frere Jacques": "C5 D5 E5 C5 C5 D5 E5 C5 E5 F5 G5 E5 F5 G5 G5 A5 G5 F5 E5 C5 G5 A5 G5 F5 E5 C5 C5 G4 C5 C5 G4 C5",
    "Deck the Halls": "G5 F5 E5 D5 C5 D5 E5 C5 D5 E5 F5 D5 E5 D5 C5 B4 C5 G5 F5 E5 D5 C5 D5 E5 C5 D5 E5 F5 D5 E5 D5 C5 B4 C5",
    "We Wish You a Merry Christmas": "D5 G5 G5 A5 G5 F#5 E5 E5 E5 A5 A5 B5 A5 G5 F#5 D5 D5 B5 B5 C6 B5 A5 G5 E5 D5 D5 E5 A5 F#5 G5",
    "Old MacDonald": "G5 G5 G5 D5 E5 E5 D5 B5 B5 A5 A5 G5 D5 G5 G5 G5 D5 E5 E5 D5 B5 B5 A5 A5 G5",
}
SEMI = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def note_hz(n):
    name, octv = n[:-1], int(n[-1])
    midi = 12 * (octv + 1) + SEMI[name]
    return 440.0 * 2 ** ((midi - 69) / 12)


PENTA = [note_hz(n) for n in "C5 D5 E5 G5 A5 C6 D6 E6 G6 A6".split()]


def melody(name):
    return [note_hz(n) for n in MELODIES[name].split()]


# ------------------------------------------------------------------ colours
def hsv(h, s=0.75, v=1.0):
    return colorsys.hsv_to_rgb(h % 1.0, s, v)


PALETTES = [
    [0.92, 0.12, 0.52, 0.30, 0.75],   # candy
    [0.55, 0.60, 0.68, 0.48, 0.80],   # ocean
    [0.02, 0.08, 0.14, 0.95, 0.10],   # fire
    [0.30, 0.38, 0.45, 0.22, 0.52],   # lime
    [0.75, 0.82, 0.88, 0.68, 0.95],   # galaxy
]


# ------------------------------------------------------------------ physics helpers
def wall_bounce(b, cx, cy, R):
    """Reflect ball dict b off the inside of circle. Returns hit point or None."""
    dx, dy = b["x"] - cx, b["y"] - cy
    d = math.hypot(dx, dy) or 1e-9
    if d + b["r"] >= R:
        nx, ny = dx / d, dy / d
        dot = b["vx"] * nx + b["vy"] * ny
        b["x"], b["y"] = cx + nx * (R - b["r"] - 0.3), cy + ny * (R - b["r"] - 0.3)
        if dot > 0:
            b["vx"] -= 2 * dot * nx
            b["vy"] -= 2 * dot * ny
            return (cx + nx * R, cy + ny * R)
    return None


def keep_speed(b, lo, hi=None):
    s = math.hypot(b["vx"], b["vy"]) or 1e-9
    if s < lo:
        b["vx"] *= lo / s; b["vy"] *= lo / s
    elif hi and s > hi:
        b["vx"] *= hi / s; b["vy"] *= hi / s


def ball_ball(balls):
    n = len(balls)
    for i in range(n):
        a = balls[i]
        for j in range(i + 1, n):
            c = balls[j]
            dx, dy = c["x"] - a["x"], c["y"] - a["y"]
            d = math.hypot(dx, dy)
            m = a["r"] + c["r"]
            if 0 < d < m:
                nx, ny = dx / d, dy / d
                rv = (a["vx"] - c["vx"]) * nx + (a["vy"] - c["vy"]) * ny
                if rv > 0:
                    a["vx"] -= rv * nx; a["vy"] -= rv * ny
                    c["vx"] += rv * nx; c["vy"] += rv * ny
                ov = (m - d) / 2
                a["x"] -= nx * ov; a["y"] -= ny * ov
                c["x"] += nx * ov; c["y"] += ny * ov


# ------------------------------------------------------------------ drawing helpers
def draw_ball(ctx, x, y, r, rgb):
    ctx.new_path()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source_rgb(*rgb); ctx.fill_preserve()
    ctx.set_source_rgba(1, 1, 1, 0.9); ctx.set_line_width(max(1.5, r * 0.09)); ctx.stroke()
    if r > 9:
        ctx.arc(x - r * 0.38, y - r * 0.38, r * 0.22, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.55); ctx.fill()


def draw_ring(ctx, cx, cy, R, rgb, a0=None, a1=None, width=7):
    ctx.new_path()
    for w, al in ((width * 5, 0.06), (width * 3, 0.12), (width * 1.8, 0.25)):
        ctx.set_line_width(w); ctx.set_source_rgba(*rgb, al)
        if a0 is None:
            ctx.arc(cx, cy, R, 0, 2 * math.pi)
        else:
            ctx.arc(cx, cy, R, a0, a1)
        ctx.stroke()
    ctx.set_line_width(width); ctx.set_source_rgb(1, 1, 1)
    if a0 is None:
        ctx.arc(cx, cy, R, 0, 2 * math.pi)
    else:
        ctx.arc(cx, cy, R, a0, a1)
    ctx.stroke()


def text(ctx, s, x, y, size, rgb=(1, 1, 1), anchor="center", bold=True, max_w=None):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    if max_w and ext.width > max_w:
        size *= max_w / ext.width
        ctx.set_font_size(size); ext = ctx.text_extents(s)
    tx = x - ext.width / 2 - ext.x_bearing if anchor == "center" else x
    ty = y - ext.height / 2 - ext.y_bearing
    ctx.new_path(); ctx.move_to(tx + 3, ty + 3); ctx.set_source_rgba(0, 0, 0, 0.6); ctx.show_text(s)
    ctx.move_to(tx, ty); ctx.set_source_rgb(*rgb); ctx.show_text(s)
    ctx.new_path()


def particles_step(parts, dt, g):
    for p in parts:
        p[2] += 0; p[3] += g * dt
        p[0] += p[2] * dt; p[1] += p[3] * dt; p[4] -= dt
    parts[:] = [p for p in parts if p[4] > 0]


def particles_draw(ctx, parts):
    for x, y, _, _, life, rgb in parts:
        ctx.new_path()
        ctx.arc(x, y, 4, 0, 2 * math.pi)
        ctx.set_source_rgba(*rgb, max(0, min(1, life))); ctx.fill()


def burst(parts, x, y, rgb, n, rnd, speed=500):
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi); s = rnd.uniform(0.3, 1) * speed
        parts.append([x, y, math.cos(a) * s, math.sin(a) * s, rnd.uniform(0.6, 1.4), rgb])


# ------------------------------------------------------------------ simulations
# Each sim: __init__(rnd, W, H, cx, cy, R), step(dt) -> list of (pitch_hz, gain), draw(ctx, t),
# done(t) -> bool, hook (title on screen), counter() -> (number, label), title_ideas
class Sim:
    max_time = 55.0
    min_time = 12.0
    G = 1400.0

    def __init__(self, rnd, W, H, cx, cy, R):
        self.rnd, self.W, self.H, self.cx, self.cy, self.R = rnd, W, H, cx, cy, R
        self.pal = rnd.choice(PALETTES)
        self.parts = []
        self.finished_at = None

    def col(self, i):
        return hsv(self.pal[i % len(self.pal)])

    def done(self, t):
        if self.finished_at is not None:
            return t - self.finished_at > 2.5
        return t > self.max_time


class Grow(Sim):
    """Every bounce = bigger ball, plays a melody."""
    def __init__(self, *a):
        super().__init__(*a)
        self.song = self.rnd.choice(list(MELODIES))
        self.notes = melody(self.song)
        while len(self.notes) < 48:
            self.notes = self.notes + melody(self.song)
        self.b = dict(x=self.cx + 30, y=self.cy - self.R * 0.5, vx=self.rnd.uniform(-300, 300), vy=0, r=self.R * 0.045)
        self.grow = (self.R * 0.95 - self.b["r"]) / len(self.notes)
        self.n = 0
        self.hue = self.rnd.random()
        self.hook = "EVERY BOUNCE = BIGGER"
        self.sub = f"...and it plays {self.song}"
        self.title = f"Every Bounce = Bigger Ball... and It Plays {self.song}"

    def step(self, dt):
        b = self.b; ev = []
        if self.finished_at is not None:
            return ev
        b["vy"] += self.G * dt; b["x"] += b["vx"] * dt; b["y"] += b["vy"] * dt
        if wall_bounce(b, self.cx, self.cy, self.R):
            keep_speed(b, self.R * 3.2)
            ev.append((self.notes[self.n % len(self.notes)], 1.0))
            self.n += 1
            b["r"] = min(b["r"] + self.grow, self.R - 3)
            if self.n >= len(self.notes):
                self.finished_at = self.t
                ev.append(("chord", 1.0))
        return ev

    def draw(self, ctx, t):
        c = hsv(self.hue + self.n * 0.03)
        draw_ring(ctx, self.cx, self.cy, self.R, c)
        draw_ball(ctx, self.b["x"], self.b["y"], self.b["r"], c)

    def counter(self):
        return self.n, "bounces"


class Multiply(Sim):
    """Every bounce = one more ball."""
    def __init__(self, *a):
        super().__init__(*a)
        self.cap = self.rnd.choice([256, 300, 400, 500])
        self.balls = [self.new_ball(self.cx, self.cy - self.R * 0.4)]
        self.hook = "EVERY BOUNCE = +1 BALL"
        self.sub = f"can it reach {self.cap}?"
        self.title = f"Every Bounce Adds a Ball... Can It Reach {self.cap}?"
        self.last_snd = -1

    def new_ball(self, x, y):
        a = self.rnd.uniform(0, 2 * math.pi); s = self.rnd.uniform(300, 700)
        return dict(x=x, y=y, vx=math.cos(a) * s, vy=math.sin(a) * s, r=self.R * 0.022, c=len(getattr(self, "balls", [])), cd=self.t if hasattr(self, "t") else 0)

    def step(self, dt):
        ev = []
        new = []
        for b in self.balls:
            b["vy"] += self.G * dt; b["x"] += b["vx"] * dt; b["y"] += b["vy"] * dt
            if wall_bounce(b, self.cx, self.cy, self.R):
                keep_speed(b, self.R * 2.0)
                if len(self.balls) + len(new) < self.cap and self.finished_at is None and self.t - b["cd"] > 2.2:
                    b["cd"] = self.t
                    new.append(self.new_ball(b["x"], b["y"]))
                if self.t - self.last_snd > 0.045:
                    ev.append((PENTA[min(len(PENTA) - 1, int(math.log2(len(self.balls) + 1)))], 0.7))
                    self.last_snd = self.t
        for nb in new:
            nb["c"] = len(self.balls); self.balls.append(nb)
        if len(self.balls) >= self.cap and self.finished_at is None:
            self.finished_at = self.t; ev.append(("chord", 1.0))
        return ev

    def draw(self, ctx, t):
        draw_ring(ctx, self.cx, self.cy, self.R, self.col(0))
        for b in self.balls:
            draw_ball(ctx, b["x"], b["y"], b["r"], self.col(b["c"]))

    def counter(self):
        return len(self.balls), "balls"


class Escape(Sim):
    """Ball must escape N rotating rings through their gaps."""
    max_time = 60.0

    def __init__(self, *a):
        super().__init__(*a)
        self.N = self.rnd.choice([5, 6, 7, 8, 9, 10])
        rmin = self.R * 0.22
        self.rings = []
        for k in range(self.N):
            rr = rmin + (self.R - rmin) * k / (self.N - 1)
            self.rings.append(dict(r=rr, ang=self.rnd.uniform(0, 6.28), w=self.rnd.choice([-1, 1]) * self.rnd.uniform(0.8, 2.2),
                                   gap=self.rnd.uniform(0.8, 1.1), hue=self.pal[k % 5]))
        self.b = dict(x=self.cx, y=self.cy, vx=self.rnd.uniform(-250, 250), vy=-200, r=self.R * 0.035)
        self.hook = f"CAN IT ESCAPE {self.N} RINGS?"
        self.sub = "each ring has one tiny gap"
        self.title = f"Can One Ball Escape {self.N} Spinning Rings?"
        self.trail = []

    def step(self, dt):
        ev = []
        b = self.b
        for rg in self.rings:
            rg["ang"] += rg["w"] * dt
        if self.finished_at is not None:
            particles_step(self.parts, dt, self.G); return ev
        b["vy"] += self.G * 0.6 * dt; b["x"] += b["vx"] * dt; b["y"] += b["vy"] * dt
        keep_speed(b, self.R * 2.0, self.R * 3.2)
        if self.rings:
            rg = self.rings[0]
            dx, dy = b["x"] - self.cx, b["y"] - self.cy
            d = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            diff = (ang - rg["ang"] + math.pi) % (2 * math.pi) - math.pi
            in_gap = abs(diff) < rg["gap"] / 2 - b["r"] / rg["r"] * 0.6
            if d - b["r"] > rg["r"] + 2:
                self.rings.pop(0)
                hx, hy = self.cx + dx / d * rg["r"], self.cy + dy / d * rg["r"]
                for k in range(24):
                    a2 = rg["ang"] + rg["gap"] / 2 + k * (2 * math.pi - rg["gap"]) / 24
                    burst(self.parts, self.cx + math.cos(a2) * rg["r"], self.cy + math.sin(a2) * rg["r"], hsv(rg["hue"]), 3, self.rnd, 300)
                ev.append((PENTA[min(9, self.N - len(self.rings))], 1.0)); ev.append(("boom", 0.8))
                if not self.rings:
                    self.finished_at = self.t; ev.append(("chord", 1.0))
            elif d + b["r"] >= rg["r"] and not in_gap:
                nx, ny = dx / d, dy / d
                dot = b["vx"] * nx + b["vy"] * ny
                b["x"], b["y"] = self.cx + nx * (rg["r"] - b["r"] - 0.3), self.cy + ny * (rg["r"] - b["r"] - 0.3)
                if dot > 0:
                    b["vx"] -= 2 * dot * nx; b["vy"] -= 2 * dot * ny
                    ev.append((PENTA[(self.N - len(self.rings)) % 5], 0.55))
        particles_step(self.parts, dt, self.G)
        return ev

    def draw(self, ctx, t):
        for rg in self.rings:
            a0 = rg["ang"] + rg["gap"] / 2
            draw_ring(ctx, self.cx, self.cy, rg["r"], hsv(rg["hue"]), a0, a0 + 2 * math.pi - rg["gap"], width=6)
        particles_draw(ctx, self.parts)
        if self.finished_at is None or True:
            draw_ball(ctx, self.b["x"], self.b["y"], self.b["r"], (1, 0.95, 0.4))

    def counter(self):
        return len(self.rings), ("ring left" if len(self.rings) == 1 else "rings left")

    def done(self, t):
        if self.finished_at is None and t > self.max_time:
            return True
        return super().done(t)


class Lines(Sim):
    """Every bounce leaves a line attached to the ball."""
    def __init__(self, *a):
        super().__init__(*a)
        self.song = self.rnd.choice(list(MELODIES))
        self.notes = melody(self.song)
        self.target = max(50, len(self.notes))
        self.b = dict(x=self.cx - 40, y=self.cy - self.R * 0.3, vx=self.rnd.uniform(200, 500), vy=0, r=self.R * 0.04)
        self.pts = []
        self.hook = "EVERY BOUNCE = A NEW LINE"
        self.sub = f"plays {self.song}"
        self.title = f"Every Bounce Draws a Line ({self.song})"
        self.hue = self.rnd.random()

    def step(self, dt):
        ev = []
        if self.finished_at is not None:
            return ev
        b = self.b
        b["vy"] += self.G * dt; b["x"] += b["vx"] * dt; b["y"] += b["vy"] * dt
        hit = wall_bounce(b, self.cx, self.cy, self.R)
        if hit:
            keep_speed(b, self.R * 3.0)
            self.pts.append((hit, len(self.pts)))
            ev.append((self.notes[(len(self.pts) - 1) % len(self.notes)], 0.9))
            if len(self.pts) >= self.target:
                self.finished_at = self.t; ev.append(("chord", 1.0))
        return ev

    def draw(self, ctx, t):
        draw_ring(ctx, self.cx, self.cy, self.R, hsv(self.hue))
        ctx.set_line_width(2.2)
        for (px, py), i in self.pts:
            ctx.set_source_rgba(*hsv(self.hue + i * 0.02), 0.85)
            ctx.move_to(px, py); ctx.line_to(self.b["x"], self.b["y"]); ctx.stroke()
        draw_ball(ctx, self.b["x"], self.b["y"], self.b["r"], hsv(self.hue + len(self.pts) * 0.02))

    def counter(self):
        return len(self.pts), "lines"


class Race(Sim):
    """N colored balls, one gap at the bottom. Which escapes first?"""
    NAMES = [("RED", (1, 0.25, 0.3)), ("BLUE", (0.25, 0.55, 1)), ("GREEN", (0.3, 0.95, 0.4)),
             ("YELLOW", (1, 0.85, 0.2)), ("PURPLE", (0.7, 0.4, 1)), ("ORANGE", (1, 0.55, 0.15))]
    max_time = 60.0

    def __init__(self, *a):
        super().__init__(*a)
        n = self.rnd.choice([3, 4, 5, 6])
        self.balls = []
        for i in range(n):
            a2 = 2 * math.pi * i / n
            self.balls.append(dict(x=self.cx + math.cos(a2) * self.R * 0.4, y=self.cy + math.sin(a2) * self.R * 0.4,
                                   vx=self.rnd.uniform(-500, 500), vy=self.rnd.uniform(-500, 0), r=self.R * 0.07,
                                   name=self.NAMES[i][0], c=self.NAMES[i][1]))
        self.gap = 0.24
        self.ang = math.pi / 2
        self.w = self.rnd.choice([-1, 1]) * 0.6
        self.winner = None
        names = " vs ".join(b["name"].title() for b in self.balls)
        self.hook = "WHICH COLOR ESCAPES FIRST?"
        self.sub = "comment your guess!"
        self.title = f"Which Color Escapes First? {names}"

    def step(self, dt):
        ev = []
        self.ang += self.w * dt
        self.gap = min(1.2, 0.24 + 0.012 * max(0, self.t - 12))
        particles_step(self.parts, dt, self.G)
        if self.winner:
            return ev
        for b in self.balls:
            b["vy"] += self.G * 0.8 * dt; b["x"] += b["vx"] * dt; b["y"] += b["vy"] * dt
            keep_speed(b, self.R * 1.6, self.R * 3.2)
        ball_ball(self.balls)
        for b in self.balls:
            dx, dy = b["x"] - self.cx, b["y"] - self.cy
            d = math.hypot(dx, dy)
            diff = (math.atan2(dy, dx) - self.ang + math.pi) % (2 * math.pi) - math.pi
            in_gap = abs(diff) < self.gap / 2 - b["r"] / self.R * 0.5
            if d - b["r"] > self.R + 1:
                self.winner = b; self.finished_at = self.t
                burst(self.parts, b["x"], b["y"], b["c"], 60, self.rnd, 700)
                ev.append(("chord", 1.0)); ev.append(("boom", 1.0))
                return ev
            if d + b["r"] >= self.R and not in_gap:
                nx, ny = dx / d, dy / d
                dot = b["vx"] * nx + b["vy"] * ny
                b["x"], b["y"] = self.cx + nx * (self.R - b["r"] - 0.3), self.cy + ny * (self.R - b["r"] - 0.3)
                if dot > 0:
                    b["vx"] -= 2 * dot * nx; b["vy"] -= 2 * dot * ny
                    ev.append((PENTA[self.balls.index(b) + 2], 0.5))
        return ev

    def draw(self, ctx, t):
        a0 = self.ang + self.gap / 2
        draw_ring(ctx, self.cx, self.cy, self.R, (1, 1, 1), a0, a0 + 2 * math.pi - self.gap)
        for b in self.balls:
            if b is self.winner:
                continue
            draw_ball(ctx, b["x"], b["y"], b["r"], b["c"])
        particles_draw(ctx, self.parts)
        if self.winner:
            text(ctx, f"{self.winner['name']} WINS!", self.cx, self.cy, self.R * 0.22, self.winner["c"])

    def counter(self):
        return (self.winner["name"] if self.winner else len(self.balls)), ("winner" if self.winner else "racers")


class Speed(Sim):
    """Every bounce = 5% faster, glowing trail."""
    max_time = 50.0

    def __init__(self, *a):
        super().__init__(*a)
        self.mult = 1.0
        self.goal = self.rnd.choice([10, 15, 20])
        self.b = dict(x=self.cx, y=self.cy - self.R * 0.5, vx=self.R * 0.6, vy=0, r=self.R * 0.05)
        self.base = self.R * 1.5
        self.trail = []
        self.hook = "EVERY BOUNCE = 5% FASTER"
        self.sub = f"how long until {self.goal}x speed?"
        self.title = f"Every Bounce Makes It 5% Faster... Until {self.goal}x Speed"
        self.n = 0
        self.G = 0.0

    def step(self, dt):
        ev = []
        if self.finished_at is not None:
            particles_step(self.parts, dt, 1400); return ev
        b = self.b
        b["x"] += b["vx"] * dt; b["y"] += b["vy"] * dt
        self.trail.append((b["x"], b["y"]))
        self.trail = self.trail[-int(60 + self.mult * 40):]
        if wall_bounce(b, self.cx, self.cy, self.R):
            self.n += 1
            self.mult *= 1.05
            # small angular nudge so the path keeps changing
            a = math.atan2(b["vy"], b["vx"]) + self.rnd.uniform(-0.15, 0.15)
            s = self.base * self.mult
            b["vx"], b["vy"] = math.cos(a) * s, math.sin(a) * s
            ev.append((PENTA[self.n % len(PENTA)], 0.6))
            if self.mult >= self.goal:
                self.finished_at = self.t
                burst(self.parts, b["x"], b["y"], (1, 1, 1), 80, self.rnd, 900)
                ev.append(("boom", 1.0)); ev.append(("chord", 1.0))
        return ev

    def draw(self, ctx, t):
        c = hsv(self.pal[0] + self.n * 0.01)
        draw_ring(ctx, self.cx, self.cy, self.R, c)
        if len(self.trail) > 2:
            ctx.set_line_width(self.b["r"] * 1.2); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            n = len(self.trail)
            for i in range(1, n, 2):
                ctx.set_source_rgba(*c, i / n * 0.6)
                ctx.move_to(*self.trail[i - 1]); ctx.line_to(*self.trail[i]); ctx.stroke()
        particles_draw(ctx, self.parts)
        if self.finished_at is None:
            draw_ball(ctx, self.b["x"], self.b["y"], self.b["r"], c)

    def counter(self):
        return f"{self.mult:.1f}x", "speed"


KINDS = {"grow": Grow, "multiply": Multiply, "escape": Escape, "lines": Lines, "race": Race, "speed": Speed}


# ------------------------------------------------------------------ audio
def synth(events, dur):
    out = np.zeros(int(SR * (dur + 3)))
    cache = {}

    def tone(f):
        if f not in cache:
            n = int(SR * 1.1); t = np.arange(n) / SR
            w = (np.sin(2 * np.pi * f * t) * np.exp(-t * 5)
                 + 0.35 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 14)
                 + 0.15 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 8))
            cache[f] = w * np.minimum(1, t / 0.002)
        return cache[f]

    rng = np.random.default_rng(0)
    for t, f, g in events:
        s = int(t * SR)
        if s >= len(out):
            continue
        if f == "chord":
            n = int(SR * 2.4); tt = np.arange(n) / SR
            w = sum(np.sin(2 * np.pi * note_hz(k) * tt) for k in ("C5", "E5", "G5", "C6")) * np.exp(-tt * 1.5) * 0.45
        elif f == "boom":
            n = int(SR * 0.6); tt = np.arange(n) / SR
            w = (rng.standard_normal(n) * np.exp(-tt * 12) * 0.5 + np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 6))
        else:
            w = tone(f)
        e = min(len(out), s + len(w))
        out[s:e] += g * w[: e - s]
    out = out[: int(SR * dur)]
    peak = np.abs(out).max() or 1
    out = np.tanh(out / peak * 1.4) * 0.8
    return out


def write_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ render
class Renderer:
    def __init__(self, W, H, fps, out_path, wav_path, crf=20):
        self.W, self.H, self.fps = W, H, fps
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        self.ctx = cairo.Context(self.surf)
        self.ctx.set_antialias(cairo.ANTIALIAS_GOOD)
        self.out_path, self.wav_path = out_path, wav_path
        self.ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
             "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
             "-pix_fmt", "yuv420p", "/tmp/gc_video_only.mp4"], stdin=subprocess.PIPE)
        self.frames = 0

    def background(self):
        g = cairo.LinearGradient(0, 0, 0, self.H)
        g.add_color_stop_rgb(0, 0.05, 0.05, 0.11); g.add_color_stop_rgb(1, 0.02, 0.02, 0.05)
        self.ctx.set_source(g); self.ctx.paint()

    def emit(self):
        self.surf.flush()
        self.ff.stdin.write(bytes(self.surf.get_data()))
        self.frames += 1

    def finish(self):
        self.ff.stdin.close(); self.ff.wait()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/tmp/gc_video_only.mp4", "-i", self.wav_path,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                        self.out_path], check=True)


def run_sim(r, sim, t0, events, layout, scene_label=None, intro=0.0):
    """Simulate + draw one scene. Returns (duration, snapshot_png_bytes)."""
    sub = 8
    dt = 1.0 / (r.fps * sub)
    t = 0.0
    snap = None
    best_t = None
    while True:
        for _ in range(sub):
            sim.t = t
            for f, g in sim.step(dt):
                events.append((t0 + t, f, g))
            t += dt
        r.background()
        sim.draw(r.ctx, t)
        W, H = r.W, r.H
        if layout == "short":
            text(r.ctx, sim.hook, W / 2, 230, 64, max_w=W - 90)
            text(r.ctx, sim.sub, W / 2, 315, 42, (1, 0.84, 0.35), max_w=W - 110)
            num, lab = sim.counter()
            text(r.ctx, str(num), W / 2, 1640, 120, (1, 1, 1))
            text(r.ctx, lab, W / 2, 1745, 44, (0.7, 0.7, 0.8))
        else:
            text(r.ctx, sim.hook, W / 2, 60, 44, max_w=W - 200)
            text(r.ctx, sim.sub, W / 2, 112, 28, (1, 0.84, 0.35), max_w=W - 300)
            num, lab = sim.counter()
            text(r.ctx, f"{num} {lab}", W - 40, H - 50, 34, (0.85, 0.85, 0.95), anchor="left") if False else None
            text(r.ctx, f"{num} {lab}", W / 2, H - 45, 34, (0.85, 0.85, 0.95))
            if scene_label:
                text(r.ctx, scene_label, 90, 60, 30, (0.6, 0.6, 0.75))
        r.emit()
        if (sim.finished_at is not None and best_t is None) or (snap is None and t > sim.min_time):
            r.surf.flush(); import io; buf = io.BytesIO(); r.surf.write_to_png(buf); snap = buf.getvalue()
        if sim.done(t) and t > sim.min_time:
            break
        if sim.finished_at is not None and best_t is None:
            best_t = t
    return t, snap


def title_card(r, lines, secs, events, t0):
    n = int(secs * r.fps)
    for i in range(n):
        r.background()
        a = min(1, i / (r.fps * 0.4))
        for k, (s, size, col) in enumerate(lines):
            text(r.ctx, s, r.W / 2, r.H / 2 - 60 + k * (size + 30), size, tuple(c * a for c in col), max_w=r.W - 160)
        r.emit()
    events.append((t0 + 0.05, "chord", 0.6))
    return secs


def fmt_ts(s):
    s = int(s); return f"{s // 60}:{s % 60:02d}"


HASHTAGS = "#satisfying #physics #simulation #oddlysatisfying #asmr #relaxing"


def make_short(seed, out, meta_path, kind=None):
    rnd = random.Random(seed)
    kind = kind or rnd.choice(list(KINDS))
    W, H, fps = 1080, 1920, 60
    r = Renderer(W, H, fps, out, "/tmp/gc_audio.wav")
    sim = KINDS[kind](rnd, W, H, W / 2, 1000, 470)
    sim.min_time = 10; sim.max_time = min(sim.max_time, 45)
    events = []
    dur, snap = run_sim(r, sim, 0, events, "short")
    write_wav("/tmp/gc_audio.wav", synth(events, r.frames / fps))
    r.finish()
    title = (sim.title + " #satisfying #shorts")[:100]
    desc = (f"{sim.title}. Turn the sound on! Every sound is a real collision from a physics simulation.\n\n"
            f"Subscribe to Gravity Candy for a new satisfying simulation every day.\n\n{HASHTAGS} #shorts")
    meta = dict(type="short", kind=kind, seed=seed, title=title, description=desc, duration=round(r.frames / fps, 1))
    json.dump(meta, open(meta_path, "w"), indent=2)
    return meta


def make_long(seed, out, meta_path, minutes=8.0):
    rnd = random.Random(seed)
    W, H, fps = 1920, 1080, 30
    r = Renderer(W, H, fps, out, "/tmp/gc_audio.wav", crf=25)
    events, chapters = [], []
    target = minutes * 60
    order = []
    for _ in range(6):
        perm = list(KINDS); rnd.shuffle(perm)
        if order and perm[0] == order[-1]:
            perm.append(perm.pop(0))
        order += perm
    # avoid same kind twice in a row
    for i in range(1, len(order)):
        if order[i] == order[i - 1]:
            j = next((k for k in range(i + 1, len(order)) if order[k] != order[i]), None)
            if j: order[i], order[j] = order[j], order[i]
    # estimate scene count from average ~32s
    n_scenes = 0
    t = title_card(r, [("THE MOST SATISFYING PHYSICS SIMULATIONS", 64, (1, 1, 1)), ("turn the sound on", 34, (1, 0.84, 0.35))], 3.0, events, 0)
    chapters.append((0, "Intro"))
    snaps = []
    for i in range(len(order)):
        kind = order[i]
        sim = KINDS[kind](rnd, W, H, W / 2, 575, 410)
        sim.min_time = 18
        chapters.append((t, sim.title))
        d, snap = run_sim(r, sim, t, events, "long", scene_label=f"#{i + 1}")
        t += d
        snaps.append((kind, snap))
        n_scenes = i + 1
        if t >= target:
            break
    title_text = f"{n_scenes} Most Satisfying Physics Simulations"
    write_wav("/tmp/gc_audio.wav", synth(events, r.frames / fps))
    r.finish()
    hook = rnd.choice(["(Every Sound Is a Real Collision)", "to Relax Your Brain", "You Can't Stop Watching",
                       "(Turn the Sound On)", "| Oddly Satisfying ASMR"])
    title = f"{title_text} {hook}"[:100]
    ch = "\n".join(f"{fmt_ts(s)} {name}" for s, name in chapters)
    desc = (f"{n_scenes} satisfying physics simulations in one video: bouncing balls that grow, multiply, race, "
            f"escape spinning rings and play music. Every sound is a real collision.\n\n"
            f"Chapters:\n{ch}\n\nSubscribe to Gravity Candy for new simulations every week!\n\n{HASHTAGS}")
    # thumbnail from the most visual snapshot
    pick = next((s for k, s in snaps if k in ("multiply", "lines", "escape")), snaps[0][1])
    thumb_path = meta_path.replace(".json", "_thumb.png")
    make_thumb(pick, thumb_path, f"{n_scenes}\nSATISFYING\nSIMS")
    meta = dict(type="long", seed=seed, title=title, description=desc, duration=round(r.frames / fps, 1),
                chapters=[(round(s, 1), n) for s, n in chapters], thumbnail=thumb_path)
    json.dump(meta, open(meta_path, "w"), indent=2)
    return meta


def make_thumb(png_bytes, out, label):
    """1280x720: simulation arena on the left, big text on the right."""
    import io
    src = cairo.ImageSurface.create_from_png(io.BytesIO(png_bytes))
    W, H = 1280, 720
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); c = cairo.Context(s)
    g = cairo.LinearGradient(0, 0, W, H); g.add_color_stop_rgb(0, 0.06, 0.05, 0.14); g.add_color_stop_rgb(1, 0.02, 0.02, 0.05)
    c.set_source(g); c.paint()
    # arena of the long layout: centre (960,575) R 410 -> crop 880x880 box, scale into 690x690 on the left
    box, x0, y0 = 880, 960 - 440, 575 - 440
    k = 690 / box
    c.save(); c.translate(15, 15); c.scale(k, k); c.rectangle(0, 0, box, box); c.clip()
    c.set_source_surface(src, -x0, -y0); c.paint(); c.restore()
    lines = label.split("\n")
    for i, ln in enumerate(lines):
        text(c, ln, 990, 175 + i * 140, 112, (1, 0.85, 0.15) if i == 0 else (1, 1, 1), max_w=540)
    text(c, "turn the sound on", 990, 150 + len(lines) * 140, 40, (0.75, 0.9, 1), max_w=520)
    s.write_to_png(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["short", "long"])
    ap.add_argument("--seed", type=int, default=random.randrange(10**6))
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--kind", choices=list(KINDS))
    ap.add_argument("--minutes", type=float, default=8.0)
    a = ap.parse_args()
    if a.mode == "short":
        print(json.dumps(make_short(a.seed, a.out, a.meta, a.kind), indent=2))
    else:
        print(json.dumps(make_long(a.seed, a.out, a.meta, a.minutes), indent=2))
