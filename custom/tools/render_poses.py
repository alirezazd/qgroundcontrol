"""Six calibration poses of a quadcopter, plus the six compass variants.

One solid model, six rotations, one isometric projection, painter's sort.
Body frame: X right, Y forward, Z up. Front rotors are orange so every pose
reads at thumbnail size. Writes SVG; rasterise at the SVG's own size into
src/AutoPilotPlugins/PX4/Images/, e.g. `magick MultiRotorDown.svg
MultiRotorDown.png`.

    python3 custom/tools/render_poses.py <out-dir>
"""

import math
import pathlib
import sys

OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

W, H = 792, 640
MAX_SCALE = 2.55
FIT = 0.90

# ---- model --------------------------------------------------------------

BODY = (34.0, 46.0, 14.0)  # x, y, z extents
ARM_LEN, ARM_W, ARM_H = 62.0, 7.0, 6.0
ROTOR_R, ROTOR_Z = 24.0, 4.0
LEG_H, LEG_W = 16.0, 5.0

GREY_BODY = (150, 150, 155)
GREY_ARM = (120, 120, 125)
GREY_ROTOR = (185, 185, 190)
ORANGE = (238, 136, 62)
LEG = (95, 95, 100)


def box(center, size, color):
    cx, cy, cz = center
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    p = lambda sx, sy, sz: (cx + sx * hx, cy + sy * hy, cz + sz * hz)
    faces = [
        ([p(-1, -1, 1), p(1, -1, 1), p(1, 1, 1), p(-1, 1, 1)], (0, 0, 1)),
        ([p(-1, 1, -1), p(1, 1, -1), p(1, -1, -1), p(-1, -1, -1)], (0, 0, -1)),
        ([p(1, -1, -1), p(1, 1, -1), p(1, 1, 1), p(1, -1, 1)], (1, 0, 0)),
        ([p(-1, 1, -1), p(-1, -1, -1), p(-1, -1, 1), p(-1, 1, 1)], (-1, 0, 0)),
        ([p(-1, 1, -1), p(-1, 1, 1), p(1, 1, 1), p(1, 1, -1)], (0, 1, 0)),
        ([p(1, -1, -1), p(1, -1, 1), p(-1, -1, 1), p(-1, -1, -1)], (0, -1, 0)),
    ]
    return [(pts, n, color, True) for pts, n in faces]


def disc(center, radius, color, n=28):
    cx, cy, cz = center
    pts = [
        (cx + radius * math.cos(2 * math.pi * i / n),
         cy + radius * math.sin(2 * math.pi * i / n), cz)
        for i in range(n)
    ]
    return [(pts, (0, 0, 1), color, False)]


def rot_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def apply(R, v):
    return tuple(sum(R[i][j] * v[j] for j in range(3)) for i in range(3))


def transform(faces, R, t=(0, 0, 0)):
    out = []
    for pts, n, color, closed in faces:
        pts2 = [tuple(a + b for a, b in zip(apply(R, p), t)) for p in pts]
        out.append((pts2, apply(R, n), color, closed))
    return out


def quad():
    faces = box((0, 0, 0), BODY, GREY_BODY)
    # Nose arrow on the body top.
    ay = BODY[1] / 2 - 4
    faces.append(([(0, ay, BODY[2] / 2 + 0.2), (-9, ay - 16, BODY[2] / 2 + 0.2),
                   (9, ay - 16, BODY[2] / 2 + 0.2)], (0, 0, 1), ORANGE, False))
    for angle, front in ((45, True), (135, True),
                         (225, False), (315, False)):
        R = rot_z(angle - 90)
        arm = box((0, ARM_LEN / 2 + 10, 0), (ARM_W, ARM_LEN, ARM_H), GREY_ARM)
        faces += transform(arm, R)
        hub = (0, ARM_LEN + 10, 0)
        faces += transform(box(hub, (10, 10, 12), GREY_ARM), R)
        faces += transform(
            disc((hub[0], hub[1], 6 + ROTOR_Z), ROTOR_R,
                 ORANGE if front else GREY_ROTOR), R)
    for sx in (-1, 1):
        for sy in (-1, 1):
            faces += box((sx * (BODY[0] / 2 - 4), sy * (BODY[1] / 2 - 6),
                          -BODY[2] / 2 - LEG_H / 2), (LEG_W, LEG_W, LEG_H), LEG)
    return faces


# ---- poses --------------------------------------------------------------

I = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
UPSIDE = ((-1, 0, 0), (0, 1, 0), (0, 0, -1))          # roll 180
NOSE_DOWN = ((1, 0, 0), (0, 0, 1), (0, -1, 0))         # forward -> down
TAIL_DOWN = ((1, 0, 0), (0, 0, -1), (0, 1, 0))         # forward -> up
LEFT = ((0, 0, -1), (0, 1, 0), (1, 0, 0))              # right side up
RIGHT = ((0, 0, 1), (0, 1, 0), (-1, 0, 0))             # right side down

# Pose, and the yaw it is viewed at. The side poses turn so the vehicle's top
# faces the camera: one then shows rotors, the other legs.
POSES = {
    "Down": (I, -20),
    "UpsideDown": (UPSIDE, -20),
    "NoseDown": (NOSE_DOWN, -20),
    "TailDown": (TAIL_DOWN, -20),
    "Left": (LEFT, 30),
    "Right": (RIGHT, 30),
}

# ---- projection ---------------------------------------------------------

C30, S30 = math.cos(math.radians(30)), math.sin(math.radians(30))
LIGHT = (-0.35, -0.45, 0.82)
lnorm = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / lnorm for c in LIGHT)


def project(p, scale=1.0):
    x, y, z = p
    return ((x - y) * C30 * scale, ((x + y) * S30 - z) * scale)


def depth(pts):
    return sum(x + y + z for x, y, z in pts) / len(pts)


def shade(color, n, closed):
    d = max(0.0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
    k = (0.55 + 0.45 * d) if closed else (0.78 + 0.22 * d)
    return "#%02x%02x%02x" % tuple(min(255, int(c * k)) for c in color)


def svg(faces, yaw_deg, rotate, path):
    YAW = rot_z(yaw_deg)
    faces = transform(faces, YAW)
    low = min(p[2] for f in faces for p in f[0])
    faces = transform(faces, I, (0, 0, -low))

    ground = 118
    gpts = [(-ground, -ground, 0), (ground, -ground, 0),
            (ground, ground, 0), (-ground, ground, 0)]
    gpts = [apply(YAW, p) for p in gpts]

    visible = []
    for pts, n, color, closed in faces:
        if closed and (n[0] + n[1] + n[2]) < 0:
            continue
        visible.append((depth(pts), pts, n, color, closed))
    visible.sort(key=lambda f: f[0])

    xs = [project(p)[0] for p in gpts] + [project(p)[0] for f in visible for p in f[1]]
    ys = [project(p)[1] for p in gpts] + [project(p)[1] for f in visible for p in f[1]]
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    scale = min(MAX_SCALE, FIT * W / span_x, FIT * H / span_y)
    ox = W / 2 - scale * (min(xs) + max(xs)) / 2
    oy = H / 2 - scale * (min(ys) + max(ys)) / 2

    def pt(p):
        x, y = project(p, scale)
        return f"{x + ox:.1f},{y + oy:.1f}"

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}">']
    parts.append('<polygon points="' + " ".join(pt(p) for p in gpts) +
                 '" fill="#2e2e30" stroke="#5a5a5e" stroke-width="2"/>')
    for _, pts, n, color, closed in visible:
        nn = n if (n[0] + n[1] + n[2]) >= 0 else tuple(-c for c in n)
        parts.append('<polygon points="' + " ".join(pt(p) for p in pts) +
                     f'" fill="{shade(color, nn, closed)}" stroke="#1c1c1e" stroke-width="1"/>')

    if rotate:
        # A circle about the world vertical at mid height, three quarters of
        # the way round, arrowhead at the open end.
        z = (max(p[2] for f in visible for p in f[1])) / 2
        r = ground * 0.88
        arc = [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), z)
               for a in range(20, 300, 6)]
        parts.append('<polyline points="' + " ".join(pt(p) for p in arc) +
                     '" fill="none" stroke="#6ec1e4" stroke-width="7" '
                     'stroke-linecap="round"/>')
        tip = arc[-1]
        prev = arc[-4]
        tx, ty = project(tip, scale)
        px, py = project(prev, scale)
        dx, dy = tx - px, ty - py
        ln = math.hypot(dx, dy) or 1
        dx, dy = dx / ln, dy / ln
        hx, hy = tx + ox, ty + oy
        head = [(hx + dx * 22, hy + dy * 22),
                (hx - dy * 13, hy + dx * 13),
                (hx + dy * 13, hy - dx * 13)]
        parts.append('<polygon points="' +
                     " ".join(f"{x:.1f},{y:.1f}" for x, y in head) +
                     '" fill="#6ec1e4"/>')

    parts.append("</svg>")
    path.write_text("\n".join(parts))


model = quad()
for name, (R, yaw) in POSES.items():
    posed = transform(model, R)
    svg(posed, yaw, False, OUT / f"MultiRotor{name}.svg")
    svg(posed, yaw, True, OUT / f"MultiRotor{name}Rotate.svg")
print("wrote", len(POSES) * 2, "svgs")
