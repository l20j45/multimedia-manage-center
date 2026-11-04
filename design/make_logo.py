"""Genera el logo/app-icon 'sala de edición': carbón + film strip + waveform."""
import random

from PIL import Image, ImageDraw

BG = (11, 13, 16, 255)
SURFACE = (18, 22, 28, 255)
AMBER = (245, 184, 65, 255)
AMBER_DIM = (138, 101, 22, 255)
TANGERINE = (255, 107, 53, 255)
TEXT_DARK = (11, 13, 16, 255)

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

R = 190
d.rounded_rectangle((16, 16, S - 16, S - 16), radius=R, fill=BG)
d.rounded_rectangle((28, 28, S - 28, S - 28), radius=R - 14, fill=SURFACE)
d.rounded_rectangle((40, 40, S - 40, S - 40), radius=R - 28, fill=BG)

# film strip vertical a la izquierda
strip_x0, strip_x1 = 190, 330
strip_y0, strip_y1 = 175, 849
d.rounded_rectangle((strip_x0, strip_y0, strip_x1, strip_y1), radius=24, fill=AMBER)
hole_w, hole_h = 34, 52
for cy in range(strip_y0 + 46, strip_y1 - 20, 95):
    for cx in (strip_x0 + 26, strip_x1 - 26 - hole_w):
        d.rounded_rectangle((cx, cy, cx + hole_w, cy + hole_h), radius=8, fill=TEXT_DARK)

# waveform: barras de alturas variables
bars_x_start = strip_x1 + 60
bars_x_end = S - 185
heights = [0.32, 0.55, 0.80, 1.00, 0.62, 0.88, 0.45, 0.70, 0.95, 0.50, 0.30, 0.16]
n = len(heights)
gap = (bars_x_end - bars_x_start) / n
bar_w = gap * 0.52
center_y = 512
for i, h in enumerate(heights):
    x = bars_x_start + i * gap
    bar_h = 520 * h
    color = TANGERINE if i in (3, 7) else (AMBER if h >= 0.45 else AMBER_DIM)
    d.rounded_rectangle(
        (x, center_y - bar_h / 2, x + bar_w, center_y + bar_h / 2),
        radius=int(bar_w / 2),
        fill=color,
    )

# playhead oscuro cruzando
d.rectangle((bars_x_start - 10, center_y - 4, bars_x_end + 8, center_y + 4), fill=TEXT_DARK)

# grain sutil
random.seed(7)
for _ in range(1400):
    gx = random.randint(46, S - 46)
    gy = random.randint(46, S - 46)
    a = random.randint(6, 16)
    color = (255, 255, 255, a) if random.random() < 0.5 else (0, 0, 0, a * 2)
    d.point((gx, gy), fill=color)

img.convert("RGB").save(r"C:\Proyectos\templatesIA\design\logo-1024.png", "PNG")
img.resize((512, 512), Image.LANCZOS).convert("RGB").save(
    r"C:\Proyectos\templatesIA\design\logo-512.png", "PNG"
)
print("logo generado: design/logo-1024.png + logo-512.png")
