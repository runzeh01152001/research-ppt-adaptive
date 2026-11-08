#!/usr/bin/env python
"""生成 README 用的「硬套模板 vs 自适应重排」对比图。

全部为合成示意图，数据非真实实验数据，仅用于说明版式差异。
示例课题特意选为钙钛矿太阳能电池，与技能作者本人的研究对象无关。

用法：
    python docs/make_demo.py
输出：
    docs/compare-before.png   1600x900   硬套模板的一页
    docs/compare-after.png    1600x900   同一母版、重排内容区的一页
    docs/compare.png          左右拼接，标注在幻灯片外框
"""
from __future__ import annotations

import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1600, 900
S = 2  # 超采样，输出 3200x1800 后缩放

FONT_DIR = Path("C:/Windows/Fonts")
REG = FONT_DIR / "msyh.ttc"
BOLD = FONT_DIR / "msyhbd.ttc"

NAVY = (31, 56, 100)
BLUE = (46, 116, 181)
LIGHT = (234, 241, 248)
GRAY = (122, 130, 140)
LINE = (208, 214, 222)
DARK = (38, 38, 38)
RED = (192, 0, 0)
GREEN = (0, 112, 74)
WHITE = (255, 255, 255)

WARN: list[str] = []

# ---- 缺字检测：字体没有的字符会渲染成方框（tofu），中文字体尤其常见 ----
_GLYPH_OK: dict[str, bool] = {}
_MISSING_INK: int | None = None


def _ink(ch: str) -> int:
    probe = ImageFont.truetype(str(REG), 64)
    im = Image.new("L", (100, 100), 0)
    ImageDraw.Draw(im).text((12, 12), ch, font=probe, fill=255)
    return sum(1 for p in im.getdata() if p > 60)


def glyph_ok(ch: str) -> bool:
    global _MISSING_INK
    if ch in _GLYPH_OK:
        return _GLYPH_OK[ch]
    if ch.isspace() or ch in "\n":
        _GLYPH_OK[ch] = True
        return True
    if _MISSING_INK is None:
        _MISSING_INK = _ink("\uE000")
    ok = _ink(ch) != _MISSING_INK
    _GLYPH_OK[ch] = ok
    return ok


def audit_glyphs() -> None:
    bad = sorted({c for c, ok in _GLYPH_OK.items() if not ok})
    if bad:
        WARN.append("字体缺字（会显示为方框）: " + " ".join(repr(c) for c in bad))


def f(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size * S)


def tw(draw, s: str, font) -> float:
    return draw.textbbox((0, 0), s, font=font)[2] / S


def put(draw, xy, s, font, fill, max_w=None, anchor="la"):
    if max_w is not None:
        w = tw(draw, s, font)
        if w > max_w:
            WARN.append(f"超宽 {w:.0f}>{max_w:.0f}: {s[:34]}")
    for ch in s:
        if not glyph_ok(ch):
            break
    draw.text((xy[0] * S, xy[1] * S), s, font=font, fill=fill, anchor=anchor)


def rrect(draw, box, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(
        [v * S for v in box], radius=r * S, fill=fill, outline=outline, width=width * S
    )


def rect(draw, box, fill=None, outline=None, width=1):
    draw.rectangle([v * S for v in box], fill=fill, outline=outline, width=width * S)


def line(draw, pts, fill, width=1):
    draw.line([(x * S, y * S) for x, y in pts], fill=fill, width=width * S)


def polyline(draw, pts, fill, width=1):
    line(draw, pts, fill, width)


def vtext(img: Image.Image, cx: float, cy: float, s: str, font, fill) -> None:
    """在 (cx, cy) 处绘制逆时针旋转 90° 的纵轴标题。"""
    box = font.getbbox(s)
    w, h = box[2] - box[0] + 8, box[3] - box[1] + 8
    tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((4 - box[0], 4 - box[1]), s, font=font, fill=fill)
    tmp = tmp.rotate(90, expand=True)
    img.alpha_composite(tmp, (int(cx * S - tmp.width / 2), int(cy * S - tmp.height / 2)))


# ------------------------------------------------------------------ 模板外框


def chrome(draw) -> None:
    """两版完全相同的模板框架——这是"视觉身份被保留"的证据。"""
    rect(draw, (0, 0, W, H), fill=WHITE)
    rect(draw, (0, 0, W, 6), fill=NAVY)
    rect(draw, (64, 44, 76, 92), fill=BLUE)
    put(draw, (96, 52), "研究现状——材料体系", f(BOLD, 34), NAVY)
    rrect(draw, (1330, 52, 1490, 92), 6, fill=LIGHT)
    put(draw, (1410, 72), "研究现状", f(REG, 17), NAVY, anchor="mm")
    rect(draw, (64, 108, 1536, 110), fill=(214, 220, 228))
    put(draw, (64, 848), "机电工程与自动化研究院", f(REG, 13), GRAY)
    put(draw, (1536, 848), "06", f(REG, 13), GRAY, anchor="ra")


# ------------------------------------------------------------------ BEFORE 元件


def tiny_panel(draw, box, letter: str, seed: int) -> None:
    x0, y0, x1, y1 = box
    rect(draw, box, fill=WHITE, outline=(226, 231, 237))
    px0, py0 = x0 + 13, y0 + 11
    px1, py1 = x1 - 5, y1 - 9
    line(draw, [(px0, py0), (px0, py1), (px1, py1)], (168, 168, 168), 1)
    t = px0
    while t < px1 - 2:  # 密集到读不出的刻度
        line(draw, [(t, py1), (t, py1 + 2)], (190, 190, 190), 1)
        t += 5
    pts = []
    n = 22
    for i in range(n + 1):
        u = i / n
        v = 0.30 + 0.42 * (0.5 + 0.5 * math.sin(u * (5 + seed % 4) + seed))
        pts.append((px0 + (px1 - px0) * u, py1 - (py1 - py0) * v))
    polyline(draw, pts, (86, 122, 168), 1)
    put(draw, (x0 + 3, y0 + 1), letter, f(REG, 9), (120, 120, 120))


def dense_figure(draw, box, seed: int) -> None:
    x0, y0, x1, y1 = box
    rect(draw, box, fill=(250, 251, 253), outline=LINE)
    cw, ch = (x1 - x0) / 3, (y1 - y0) / 3
    for k in range(9):
        r, c = divmod(k, 3)
        tiny_panel(
            draw,
            (x0 + c * cw + 4, y0 + r * ch + 4, x0 + (c + 1) * cw - 4, y0 + (r + 1) * ch - 4),
            "abcdefghi"[k],
            seed + k,
        )


# ------------------------------------------------------------------ AFTER 元件


def axis_frame(draw, box, yticks, xticks):
    """yticks/xticks 为字符串列表，首末项即显示范围。"""
    x0, y0, x1, y1 = box
    n = len(yticks)
    for i in range(1, n):
        gy = y1 - (y1 - y0) * i / (n - 1)
        line(draw, [(x0, gy), (x1, gy)], (238, 241, 245), 1)
    line(draw, [(x0, y0), (x0, y1), (x1, y1)], (92, 92, 92), 2)
    for i, lab in enumerate(yticks):
        gy = y1 - (y1 - y0) * i / (n - 1)
        line(draw, [(x0 - 7, gy), (x0, gy)], (92, 92, 92), 2)
        put(draw, (x0 - 12, gy), lab, f(REG, 14), DARK, anchor="rm")
    m = len(xticks)
    for i, lab in enumerate(xticks):
        gx = x0 + (x1 - x0) * i / (m - 1)
        line(draw, [(gx, y1), (gx, y1 + 7)], (92, 92, 92), 2)
        put(draw, (gx, y1 + 12), lab, f(REG, 14), DARK, anchor="ma")


def panel_curve(draw, box, seed, yticks, xticks, rising=True):
    x0, y0, x1, y1 = box
    axis_frame(draw, box, yticks, xticks)
    top = float(yticks[-1]) or 1.0
    pts = []
    n = 60
    for i in range(n + 1):
        u = i / n
        if rising:
            v = 0.10 + 0.78 * (1 - math.exp(-2.8 * u)) + 0.012 * math.sin(u * 9 + seed)
        else:
            v = 0.95 - 0.70 * (1 - math.exp(-1.9 * u)) ** 0.8
        pts.append((x0 + (x1 - x0) * u, y1 - (y1 - y0) * max(0.0, min(v, 1.0))))
    polyline(draw, pts, BLUE, 3)


def panel_bars(draw, box, yticks, xticks, values):
    x0, y0, x1, y1 = box
    axis_frame(draw, box, yticks, xticks)
    lo, hi = float(yticks[0]), float(yticks[-1])
    n = len(values)
    slot = (x1 - x0) / n
    bw = slot * 0.50
    for i, v in enumerate(values):
        cx = x0 + slot * (i + 0.5)
        top = y1 - (y1 - y0) * (v - lo) / (hi - lo)
        rect(draw, (cx - bw / 2, top, cx + bw / 2, y1), fill=BLUE)
        put(draw, (cx, top - 9), f"{v:.1f}", f(REG, 13), DARK, anchor="mb")


def clean_panel(img, draw, box, fig_tag, ylab, xlab, kind, yticks, xticks, seed=1):
    x0, y0, x1, y1 = box
    rect(draw, box, fill=WHITE, outline=LINE)
    # 标题条与绘图区完全分开，避免压刻度
    rect(draw, (x0, y0, x1, y0 + 30), fill=(248, 250, 252))
    line(draw, [(x0, y0 + 30), (x1, y0 + 30)], LINE, 1)
    put(draw, (x0 + 12, y0 + 15), fig_tag, f(BOLD, 15), BLUE, anchor="lm")

    plot = (x0 + 96, y0 + 54, x1 - 34, y1 - 58)
    if kind == "bars":
        panel_bars(draw, plot, yticks, xticks, [-3.2, -3.4, -3.6, -3.1, -3.3])
    else:
        panel_curve(draw, plot, seed, yticks, xticks, rising=(kind == "curve"))

    vtext(img, x0 + 26, (plot[1] + plot[3]) / 2, ylab, f(REG, 15), DARK)
    put(draw, ((plot[0] + plot[2]) / 2, plot[3] + 36), xlab, f(REG, 15), DARK, anchor="ma")


# ------------------------------------------------------------------ BEFORE


def make_before() -> Image.Image:
    img = Image.new("RGBA", (W * S, H * S), WHITE + (255,))
    draw = ImageDraw.Draw(img)
    chrome(draw)

    cols = [
        ("① 吸光层", ["MAPbI3 带隙 1.6 eV，吸收边至 800 nm", "膜厚与结晶质量决定短路电流"], "Fig. 2a–i"),
        ("② 传输层", ["SnO2 电子层 / Spiro-OMeTAD 空穴层", "能级错配 0.2 eV 损失 80 mV 开路电压"], "Fig. 3a–i"),
        ("③ 电极", ["Au 功函数 5.1 eV，形成欧姆接触", "Ag 成本低但易与碘离子反应"], "Fig. 4a–i"),
        ("④ 封装", ["EVA + 玻璃盖板，水汽阻隔", "85 ℃ / 85% RH 老化 1000 h"], "Fig. 5a–i"),
    ]
    x_start, col_w, gap = 64, 352, 30
    for i, (head, body, cite) in enumerate(cols):
        x = x_start + i * (col_w + gap)
        rrect(draw, (x, 130, x + col_w, 172), 4, fill=LIGHT)
        put(draw, (x + 12, 142), head, f(BOLD, 17), NAVY, max_w=col_w - 24)
        dense_figure(draw, (x, 182, x + col_w, 512), seed=i * 9)

        yy = 526
        for sent in body:
            for ln in textwrap.wrap(sent, 17):
                put(draw, (x + 2, yy), ln, f(REG, 13), DARK, max_w=col_w - 4)
                yy += 20
            yy += 2
        put(draw, (x + 2, yy + 4), cite + "（示意）", f(REG, 11), GRAY)

    rect(draw, (64, 700, 1536, 758), fill=(247, 249, 251), outline=(224, 229, 235))
    put(draw, (80, 714), "四类要素共同决定器件效率与稳定性，单一优化难以兼顾全部指标。", f(REG, 15), DARK)
    put(draw, (80, 776), "示意图 · 非真实实验数据", f(REG, 12), GRAY)
    return img.convert("RGB").resize((W, H), Image.LANCZOS)


# ------------------------------------------------------------------ AFTER


def make_after() -> Image.Image:
    img = Image.new("RGBA", (W * S, H * S), WHITE + (255,))
    draw = ImageDraw.Draw(img)
    chrome(draw)

    cells = [
        (64, 128, 780, 392, "① 吸光层：带隙决定可吸收光谱", "Fig. 2a", "Absorbance (a.u.)", "Wavelength (nm)", "curve",
         ["0", "0.4", "0.8", "1.2"], ["400", "500", "600", "700", "800"], 1),
        (820, 128, 1536, 392, "② 传输层：能级匹配决定开路电压", "Fig. 3a", "Energy (eV)", "Layer index", "bars",
         ["-6.0", "-5.0", "-4.0", "-3.0"], ["1", "2", "3", "4", "5"], 3),
        (64, 404, 780, 668, "③ 电极：功函数决定接触电阻", "Fig. 4c", "Current (mA/cm²)", "Voltage (V)", "decay",
         ["0", "8", "16", "24"], ["0", "0.3", "0.6", "0.9", "1.2"], 5),
        (820, 404, 1536, 668, "④ 封装：水汽阻隔决定寿命", "Fig. 5b", "Efficiency (%)", "Time (h)", "decay",
         ["0", "10", "20", "30"], ["0", "250", "500", "750", "1000"], 7),
    ]
    for x0, y0, x1, y1, head, tag, ylab, xlab, kind, yt, xt, seed in cells:
        put(draw, (x0, y0), head, f(BOLD, 20), NAVY, max_w=x1 - x0)
        clean_panel(img, draw, (x0, y0 + 32, x1, y1), tag, ylab, xlab, kind, yt, xt, seed)

    rrect(draw, (64, 690, 1536, 754), 8, fill=NAVY)
    put(draw, (800, 722), "结论：四类要素互相牵制 —— 提效率与保寿命不可同时最优化", f(BOLD, 23), WHITE, anchor="mm")
    put(draw, (80, 772), "示意图 · 非真实实验数据　　母版、配色、页眉与标题带与左图完全一致，仅内容区重排", f(REG, 14), GRAY)
    return img.convert("RGB").resize((W, H), Image.LANCZOS)


# ------------------------------------------------------------------ 拼接


def txt(d, xy, s, font, fill, anchor="la"):
    for ch in s:
        glyph_ok(ch)
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


LEFT = [
    "四栏各塞一张 3×3 整版 Figure，整体压到 3 cm",
    "坐标轴与刻度读不出，只剩「这里有张图」",
    "结论条 13 px，投影上糊成一片",
    "四栏都用同一句套话兜底，看不出差异",
]
RIGHT = [
    "母版、配色、页眉、标题带一点没动",
    "每栏只留一张支持论点的子图，放大 5 倍",
    "结论单独成带，23 pt，投影上读得出来",
    "四栏各给一句可检验的结论，不再是套话",
]
HEADLINE = "同一套学校模板，两种排法"
FOOTNOTE = "示意图，非真实实验数据　·　两页出自同一份 SKILL.md"


def make_compare(before: Image.Image, after: Image.Image) -> Image.Image:
    """左右并排：适合 README 内嵌，高度可控。"""
    gap = 28
    head, foot = 112, 300
    canvas = Image.new("RGB", (W * 2 + gap, head + H + foot), (247, 248, 250))
    canvas.paste(before, (0, head))
    canvas.paste(after, (W + gap, head))
    d = ImageDraw.Draw(canvas)

    f_tag = ImageFont.truetype(str(BOLD), 30)
    f_body = ImageFont.truetype(str(REG), 25)

    txt(d, (canvas.width // 2, 36), HEADLINE, ImageFont.truetype(str(BOLD), 40), NAVY, anchor="mm")
    txt(d, (W // 2, head - 34), "×  硬套模板", f_tag, RED, anchor="mm")
    txt(d, (W + gap + W // 2, head - 34), "√  自适应重排", f_tag, GREEN, anchor="mm")

    y0 = head + H + 26
    for i, (lt, rt) in enumerate(zip(LEFT, RIGHT)):
        y = y0 + i * 56
        txt(d, (60, y), "•", f_body, RED)
        txt(d, (86, y), lt, f_body, (60, 60, 60))
        txt(d, (W + gap + 60, y), "•", f_body, GREEN)
        txt(d, (W + gap + 86, y), rt, f_body, (60, 60, 60))

    txt(
        d,
        (canvas.width // 2, canvas.height - 34),
        FOOTNOTE,
        ImageFont.truetype(str(REG), 22),
        (140, 146, 154),
        anchor="mm",
    )
    return canvas


def make_vertical(before: Image.Image, after: Image.Image) -> Image.Image:
    """上下堆叠：适合小红书 / 知乎 / PPT 里单页展示，字更大。"""
    pad = 44
    head_h, cap_h, slide_h, foot_h = 96, 52, H * 5 // 6, 70
    slide_w = W * 5 // 6
    bullet_h = 4 * 50 + 24

    height = head_h + (cap_h + slide_h + bullet_h) * 2 + foot_h
    canvas = Image.new("RGB", (slide_w + pad * 2, height), (247, 248, 250))
    d = ImageDraw.Draw(canvas)

    f_tag = ImageFont.truetype(str(BOLD), 30)
    f_body = ImageFont.truetype(str(REG), 24)
    f_note = ImageFont.truetype(str(REG), 21)

    txt(d, (canvas.width // 2, 48), HEADLINE, ImageFont.truetype(str(BOLD), 38), NAVY, anchor="mm")

    blocks = [
        ("×  硬套模板", RED, before, LEFT),
        ("√  自适应重排", GREEN, after, RIGHT),
    ]
    y = head_h
    for tag, color, img, bullets in blocks:
        txt(d, (pad, y + cap_h // 2), tag, f_tag, color, anchor="lm")
        y += cap_h
        canvas.paste(img.resize((slide_w, slide_h), Image.LANCZOS), (pad, y))
        y += slide_h + 14
        for b in bullets:
            txt(d, (pad + 12, y), "•", f_body, color)
            txt(d, (pad + 40, y), b, f_body, (60, 60, 60))
            y += 50
        y += 20

    txt(d, (canvas.width // 2, height - 36), FOOTNOTE, f_note, (140, 146, 154), anchor="mm")
    return canvas


def main() -> int:
    before = make_before()
    after = make_after()
    before.save(ROOT / "compare-before.png")
    after.save(ROOT / "compare-after.png")

    combo = make_compare(before, after)
    combo.save(ROOT / "compare.png")

    vert = make_vertical(before, after)
    vert.save(ROOT / "compare-vertical.png")

    audit_glyphs()

    print(f"compare-before.png    {before.size}")
    print(f"compare-after.png     {after.size}")
    print(f"compare.png           {combo.size}   左右并排，README 用")
    print(f"compare-vertical.png  {vert.size}   上下堆叠，社媒用")
    if WARN:
        print("\n警告：")
        for w in WARN:
            print("  -", w)
    else:
        print("\n无警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
