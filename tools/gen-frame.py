# -*- coding: utf-8 -*-
"""
首页照片：不规则的涟漪轮廓 + 顺着轮廓起伏的波浪花边。

改这几处就能调：
  RADII      —— 四个角不同的圆角半径 (左上, 右上, 右下, 左下)
  WAVE_LEN   —— 波长，越小涟漪越密
  AMP        —— 涟漪起伏幅度，越大越"荡"
  BAND       —— 花边厚度（那一圈灰蓝有多粗）
  STEP       —— 采样间隔，越小曲线越圆滑（也会让文件变大）
"""
import io, math, re

VB_W, VB_H = 800, 1060
PHOTO = (40, 50, 720, 960)          # 照片在画布上的矩形区域

INSET    = 22.0                     # 基础轮廓从矩形边界内缩多少（给涟漪往外荡留余量）
RADII    = (86, 52, 94, 66)         # 四角圆角半径，各不相同 —— 破除"正正方方"
WAVE_LEN = 100.0
AMP      = 14.0
BAND     = 36.0
STEP     = 7.0
ARC_STEPS = 18


def base_outline():
    """圆角矩形，顺时针一串点。"""
    x, y = PHOTO[0] + INSET, PHOTO[1] + INSET
    w, h = PHOTO[2] - 2 * INSET, PHOTO[3] - 2 * INSET
    rt, rr, rb, rl = RADII
    corners = [
        ((x + rt,     y + rt),     rt, 180, 270),
        ((x + w - rr, y + rr),     rr, 270, 360),
        ((x + w - rb, y + h - rb), rb,   0,  90),
        ((x + rl,     y + h - rl), rl,  90, 180),
    ]
    pts = []
    for (cx, cy), r, a0, a1 in corners:
        for i in range(ARC_STEPS + 1):
            a = math.radians(a0 + (a1 - a0) * i / ARC_STEPS)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def resample(pts, step):
    """按弧长均匀重采样，顺便返回周长。"""
    n = len(pts)
    segs = []
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        segs.append((p0, p1, math.hypot(p1[0] - p0[0], p1[1] - p0[1])))
    total = sum(s[2] for s in segs)
    m = max(16, int(round(total / step)))
    out = []
    for k in range(m):
        d = total * k / m
        acc = 0.0
        for p0, p1, L in segs:
            if acc + L >= d:
                t = (d - acc) / L if L else 0.0
                out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
                break
            acc += L
        else:
            out.append(pts[0])
    return out, total


def outward_normals(pts):
    """顺时针闭合曲线，外法线 = 切线逆时针转 90°（屏幕坐标 y 向下）。"""
    m = len(pts)
    out = []
    for i in range(m):
        px, py = pts[(i - 1) % m]
        qx, qy = pts[(i + 1) % m]
        tx, ty = qx - px, qy - py
        L = math.hypot(tx, ty) or 1.0
        tx, ty = tx / L, ty / L
        out.append((ty, -tx))
    return out


def poly_path(pts):
    return "M" + " L".join("%.1f,%.1f" % p for p in pts) + " Z"


# ---------- 算轮廓 ----------
base, total = resample(base_outline(), STEP)
nrm = outward_normals(base)

inner, outer = [], []
for i, (x, y) in enumerate(base):
    nx, ny = nrm[i]
    s = total * i / len(base)
    w = AMP * math.sin(2 * math.pi * s / WAVE_LEN)
    ix, iy = x + nx * w, y + ny * w
    inner.append((ix, iy))
    outer.append((ix + nx * BAND, iy + ny * BAND))

# 花边 = 内圈轮廓 + 外圈轮廓，evenodd 挖空中间
d = poly_path(inner) + " " + poly_path(outer)

# 照片裁剪路径（百分比，相对 img 盒子）
px, py, pw, ph = PHOTO
clip = "polygon(" + ", ".join(
    "%.2f%% %.2f%%" % ((x - px) / pw * 100.0, (y - py) / ph * 100.0) for x, y in inner
) + ")"

# ---------- 写入 index.html ----------
html_path = r"E:\PortfolioSite\website\index.html"
html = io.open(html_path, encoding="utf-8").read()

svg_new = (
    "<!-- 波浪花边：内圈贴着照片的涟漪轮廓，外圈是同一道波向外荡开一圈 -->\n"
    '        <svg class="hero-frame" viewBox="0 0 %d %d" preserveAspectRatio="none" aria-hidden="true">\n'
    '          <path d="%s" fill="var(--accent-soft)" fill-rule="evenodd"/>\n'
    "        </svg>"
) % (VB_W, VB_H, d)

html2, n1 = re.subn(r"<!-- (?:锯齿花边|波浪花边)[\s\S]*?</svg>", lambda m: svg_new, html, count=1)
if n1 != 1:
    raise SystemExit("index.html: hero-frame 区块没匹配到")
io.open(html_path, "w", encoding="utf-8").write(html2)

# ---------- 写入 style.css ----------
css_path = r"E:\PortfolioSite\website\assets\css\style.css"
css = io.open(css_path, encoding="utf-8").read()
css2, n2 = re.subn(r"clip-path: polygon\([\s\S]*?\);", lambda m: "clip-path: " + clip + ";", css, count=1)
if n2 != 1:
    raise SystemExit("style.css: clip-path 没匹配到")
io.open(css_path, "w", encoding="utf-8").write(css2)

print("ok | 采样点 =", len(inner), "| 周长 =", round(total, 1))
print("path 长度 =", len(d), "| clip 长度 =", len(clip))
