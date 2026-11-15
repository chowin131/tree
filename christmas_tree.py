"""
christmas_tree.py - 회전하는 3D ASCII 문자 크리스마스 트리

    python christmas_tree.py                    # 실시간 미리보기 창 (tkinter)
    python christmas_tree.py --save tree.mp4    # 영상으로 저장 (mp4 / gif)
    python christmas_tree.py --save tree.mp4 --dur 15 --scale 0.75
    python christmas_tree.py --workers 4        # 렌더 프로세스 수 (기본: 코어 수 - 1)

    pip install pillow numpy 필요 (mp4 저장 시 추가: pip install imageio imageio-ffmpeg)
"""
import argparse
import math
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
FPS = 30
CX = W // 2
Y_TOP = 300          # 잎 시작 y
TREE_H = 760         # 트리 높이
R_BASE = 330         # 바닥 반지름
TIERS = 6            # 가지 층 수
TILT = 0.10          # 위에서 내려다보는 정도 (z → y)
FOCAL = 1500         # 원근
SPIN = 0.55          # rad/s

N_LEAF = 3000
N_LIGHT = 97
N_GAR = 520
GAR_TURNS = 5.5

BG = (7, 11, 26)
GOLD = np.array([255, 205, 80])
TRUNK = (150, 95, 50)

rng = np.random.default_rng(2026)


# 폰트
def load_font(size, bold=False):
    names = (["consolab.ttf", "DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf", "Menlo.ttc", "courbd.ttf"]
             if bold else
             ["consola.ttf", "DejaVuSansMono.ttf", "LiberationMono-Regular.ttf", "Menlo.ttc", "cour.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


LEAF_SIZES = [12, 13, 14, 15, 16, 17, 18]
FONTS = [load_font(s) for s in LEAF_SIZES] + [load_font(15, True), load_font(19, True)]
F_GAR, F_LIGHT = len(LEAF_SIZES), len(LEAF_SIZES) + 1
f12, f13, f14, f15 = load_font(12), load_font(13), load_font(14, True), load_font(15, True)
f_star = load_font(15, True)
f_banner = load_font(26, True)


# 형상
def radius(h):
    """h: 0(꼭대기) ~ 1(바닥). 층마다 살짝 퍼지는 톱니 모양."""
    return R_BASE * h * (0.80 + 0.20 * ((h * TIERS) % 1.0))


# 잎 (문자)
leaf_h = rng.random(N_LEAF) ** 0.62
leaf_phi = rng.random(N_LEAF) * 2 * np.pi
leaf_r = radius(leaf_h) * (0.62 + 0.38 * np.sqrt(rng.random(N_LEAF)))
LEAF_CHARS = list("#@%&*oxWMvV^=+~")
leaf_ch = rng.choice(LEAF_CHARS, N_LEAF, p=[.13, .09, .10, .09, .07, .08, .07, .08, .08, .07, .04, .03, .03, .02, .02])
GREENS = np.array([(40, 140, 80), (60, 170, 95), (30, 120, 70), (80, 195, 110), (45, 160, 125), (110, 205, 120)])
leaf_col = GREENS[rng.integers(0, len(GREENS), N_LEAF)] * rng.uniform(0.75, 1.1, (N_LEAF, 1))
spark = rng.random(N_LEAF) < 0.025 # 간간이 섞인 반짝이 문자
leaf_col[spark] = rng.choice([(255, 140, 200), (190, 140, 255), (255, 240, 200), (140, 200, 255)], spark.sum())
leaf_ch[spark] = "*"
leaf_t0 = 0.3 + leaf_h * 2.2 # 위에서부터 자라남

# 갈런드 (나선)
gar_f = np.linspace(0.06, 0.97, N_GAR)
gar_phi = gar_f * GAR_TURNS * 2 * np.pi
gar_r = radius(gar_f) * 1.05 + 4
gar_ch = np.array([("-=~=-=*"[i % 7]) for i in range(N_GAR)])
gar_t0 = 4.0 + gar_f * 1.6

# 전구
light_h = rng.uniform(0.08, 0.98, N_LIGHT)
light_phi = rng.random(N_LIGHT) * 2 * np.pi
light_r = radius(light_h) * 1.04
light_ch = rng.choice(list("o0O@"), N_LIGHT)
LIGHT_COLS = np.array([(255, 75, 75), (255, 150, 60), (90, 160, 255), (190, 110, 255), (255, 120, 190), (255, 215, 90)])
light_col = LIGHT_COLS[rng.integers(0, len(LIGHT_COLS), N_LIGHT)]
light_ph = rng.random(N_LIGHT) * 2 * np.pi
light_sp = rng.uniform(2.0, 4.5, N_LIGHT)
light_t0 = 3.0 + light_h * 1.0


# 별 (문자 아트)
def _inside(x, y, poly):
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i - 1], poly[i]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def make_star(r1=78, r2=31):
    poly = [((r1 if k % 2 == 0 else r2) * math.cos(-math.pi / 2 + k * math.pi / 5),
             (r1 if k % 2 == 0 else r2) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]
    cells = []
    for gy in range(-(r1 // 12) * 12, r1 + 1, 12):
        for gx in range(-(r1 // 9) * 9, r1 + 1, 9):
            if _inside(gx, gy, poly):
                cells.append((gx, gy, "@" if math.hypot(gx, gy) < 25 else "*"))
    return cells


STAR = make_star()
STAR_Y = Y_TOP - 62

# 선물 상자: (x 오프셋, 열, 행, 색, 리본색)
PRESENTS = [(-300, 9, 6, (235, 70, 70), (255, 200, 90)),
            (-175, 6, 5, (185, 110, 255), (255, 255, 255)),
            (105, 6, 5, (255, 105, 80), (255, 230, 120)),
            (215, 7, 6, (90, 150, 255), (255, 255, 255)),
            (325, 7, 7, (235, 235, 245), (255, 80, 80))]
BOX_CH = list("%&*ox#")
PRES_BASE = Y_TOP + TREE_H + 72

# 배경 별 / 눈
N_STAR, N_SNOW = 170, 150
bg_xy = rng.random((N_STAR, 2)) * (W, H * 0.95)
bg_ch = rng.choice(list("+*.·"), N_STAR, p=[.35, .15, .35, .15])
bg_ph = rng.random(N_STAR) * 2 * np.pi
bg_sp = rng.uniform(0.6, 2.5, N_STAR)
sn_xy = rng.random((N_SNOW, 2)) * (W, H)
sn_v = rng.uniform(25, 70, N_SNOW)
sn_ph = rng.random(N_SNOW) * 2 * np.pi
sn_ch = rng.choice(list(".*+"), N_SNOW, p=[.5, .3, .2])

BANNER = "MERRY CHRISTMAS"


# 렌더
def project(r, phi, h, rot):
    a = phi + rot
    x, z = r * np.cos(a), r * np.sin(a)
    s = FOCAL / (FOCAL - z)
    return CX + x * s, Y_TOP + h * TREE_H + z * TILT, z


def ease_out(p):
    p = np.clip(p, 0, 1)
    return 1 - (1 - p) ** 3


def soft(im, radius):
    """1/4 해상도에서 블러 → 업스케일 (빠른 블룸)"""
    small = im.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius / 4))
    return small.resize((W, H), Image.BILINEAR)


def render(t):
    rot = t * SPIN
    img = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    d, g = ImageDraw.Draw(img), ImageDraw.Draw(glow)

    # 배경 별
    tw = 0.45 + 0.55 * (0.5 + 0.5 * np.sin(t * bg_sp + bg_ph))
    for (x, y), ch, b in zip(bg_xy.tolist(), bg_ch, tw.tolist()):
        v = int(200 * b)
        d.text((x, y), ch, font=f12, fill=(v, v, min(255, v + 30)), anchor="mm")

    # 눈
    sy = (sn_xy[:, 1] + sn_v * t) % H
    sx = sn_xy[:, 0] + 14 * np.sin(t * 0.8 + sn_ph)
    for x, y, ch in zip(sx.tolist(), sy.tolist(), sn_ch):
        d.text((x, y), ch, font=f13, fill=(225, 230, 245), anchor="mm")

    # 줄기
    if t > 0.2:
        for r in range(4):
            d.text((CX, Y_TOP + TREE_H + 12 + r * 14), "#|H|#", font=f15, fill=TRUNK, anchor="mm")

    # 트리 본체: 잎 + 갈런드 + 전구를 z 순서로 한 번에
    PX, PY, PZ, CH, COL, FI = [], [], [], [], [], []

    lx, ly, lz = project(leaf_r, leaf_phi, leaf_h, rot)
    fade = np.clip((t - leaf_t0) / 0.35, 0, 1)
    vis = fade > 0
    zn = lz / (radius(leaf_h) + 1e-6) # -1(뒤) ~ 1(앞)
    shade = (0.5 + 0.6 * (zn + 1) / 2) * fade
    PX.append(lx[vis]); PY.append(ly[vis]); PZ.append(lz[vis]); CH.append(leaf_ch[vis])
    COL.append((leaf_col * shade[:, None])[vis])
    FI.append(np.clip(((zn + 1) / 2 * len(LEAF_SIZES)).astype(int), 0, len(LEAF_SIZES) - 1)[vis])

    # 갈런드 - 앞쪽 절반만 보이게
    gx, gy, gz = project(gar_r, gar_phi, gar_f, rot)
    gvis = (gz > -0.12 * gar_r) & (t > gar_t0)
    gshade = 0.55 + 0.45 * np.clip(gz / gar_r, 0, 1)
    PX.append(gx[gvis]); PY.append(gy[gvis]); PZ.append(gz[gvis] + 2); CH.append(gar_ch[gvis])
    COL.append((GOLD * gshade[:, None])[gvis]); FI.append(np.full(gvis.sum(), F_GAR))

    # 전구 - 깜빡임
    bx, by, bz = project(light_r, light_phi, light_h, rot)
    bvis = (bz > -0.35 * light_r) & (t > light_t0)
    blink = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(t * light_sp + light_ph))
    bshade = blink * (0.5 + 0.5 * np.clip((bz / light_r + 0.35) / 1.35, 0, 1))
    bcol = light_col * bshade[:, None]
    PX.append(bx[bvis]); PY.append(by[bvis]); PZ.append(bz[bvis] + 3); CH.append(light_ch[bvis])
    COL.append(bcol[bvis]); FI.append(np.full(bvis.sum(), F_LIGHT))

    PX, PY, PZ = np.concatenate(PX), np.concatenate(PY), np.concatenate(PZ)
    CH, FI = np.concatenate(CH), np.concatenate(FI)
    COL = np.clip(np.concatenate(COL), 0, 255).astype(int)
    order = np.argsort(PZ)
    for px, py, ch, c, fi in zip(PX[order].tolist(), PY[order].tolist(), CH[order].tolist(),
                                 COL[order].tolist(), FI[order].tolist()):
        d.text((px, py), ch, font=FONTS[fi], fill=tuple(c), anchor="mm")

    # 빛 번짐 레이어
    for x, y, c in zip(bx[bvis].tolist(), by[bvis].tolist(), bcol[bvis].astype(int).tolist()):
        g.ellipse((x - 9, y - 9, x + 9, y + 9), fill=tuple(c))
    for x, y in zip(gx[gvis][::3].tolist(), gy[gvis][::3].tolist()):
        g.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(120, 90, 30))

    # 별
    if t > 2.4:
        p = np.clip((t - 2.4) / 0.6, 0, 1)
        s = 1 + 0.25 * math.sin(p * math.pi) if p < 1 else 1.0 # 살짝 튀어나오는 등장
        s *= p ** 0.5
        pulse = 0.85 + 0.15 * math.sin(t * 4)
        for dx, dy, ch in STAR:
            col = (np.array([255, 165, 55]) if ch == "@" else GOLD) * pulse
            xy = (CX + dx * s, STAR_Y + dy * s)
            d.text(xy, ch, font=f_star, fill=tuple(col.astype(int)), anchor="mm")
            g.text(xy, ch, font=f_star, fill=tuple((col * 0.9).astype(int)), anchor="mm")
        g.ellipse((CX - 60 * s, STAR_Y - 60 * s, CX + 60 * s, STAR_Y + 60 * s), fill=(70, 50, 10))

    # 선물 상자 - 위에서 떨어짐
    for i, (ox, cols, rows, col, bow) in enumerate(PRESENTS):
        t0 = 5.2 + i * 0.25
        if t < t0:
            continue
        drop = (1 - ease_out((t - t0) / 0.55)) * 280
        br = np.random.default_rng(int(t * 4) * 31 + i)
        x0 = CX + ox - (cols - 1) * 11 / 2
        y0 = PRES_BASE - rows * 15 - drop
        for r in range(rows):
            line = "".join(br.choice(BOX_CH, cols))
            for k, ch in enumerate(line):
                d.text((x0 + k * 11, y0 + r * 15), ch, font=f14, fill=col, anchor="mm")
        d.text((CX + ox, y0 - 15), "%&%", font=f14, fill=bow, anchor="mm")

    # 블룸 합성
    img = ImageChops.add(img, soft(glow, 10))
    img = ImageChops.screen(img, soft(img, 6).point(lambda v: v * 0.45))
    d = ImageDraw.Draw(img)

    # HUD
    hud = (165, 175, 195)
    letters = int(vis.sum())
    d.text((52, H - 205), f"rotation {math.degrees(rot) % 360:7.2f}°", font=f13, fill=hud)
    d.text((52, H - 184), f"lights   {int(bvis.sum()):>3d}", font=f13, fill=hud)
    d.text((52, H - 163), f"letters  {letters:,}", font=f13, fill=hud)
    d.text((W - 220, 262), f"t  {t:5.2f}s", font=f13, fill=(255, 220, 140))

    # MERRY CHRISTMAS 타이핑
    cw, chh, gap = 33, 38, 8
    total = len(BANNER) * cw + gap
    bx0, by0 = CX - total / 2, H - 142
    shown = int(max(0, (t - 7.2) / 0.18)) if t > 7.2 else -1
    if shown >= 0:
        words = [(0, 5, (18, 62, 36), (120, 255, 150)), (6, 15, (72, 12, 18), (255, 95, 95))]
        for a, b, bgc, fg in words:
            if shown >= a or a == 0:
                xa = bx0 + a * cw + (gap if a else 0)
                d.rectangle((xa - 4, by0 - 4, xa + (b - a) * cw + 4, by0 + chh), fill=bgc)
        for i, ch in enumerate(BANNER[:shown]):
            if ch == " ":
                continue
            fg = (120, 255, 150) if i < 5 else (255, 95, 95)
            x = bx0 + i * cw + (gap if i > 5 else 0) + cw / 2
            d.text((x, by0 + chh / 2 - 2), ch, font=f_banner, fill=fg, anchor="mm")
        if shown < len(BANNER) and int(t * 3) % 2 == 0:       # 커서
            i = shown
            x = bx0 + i * cw + (gap if i > 5 else 0) + 4
            d.rectangle((x, by0 + chh - 8, x + cw - 8, by0 + chh - 4), fill=(230, 230, 230))
    return img


# 병렬 렌더
# 프레임은 시간 t만의 함수라서 서로 독립 → 여러 프로세스가 미리 그려두고 순서대로 보여줌
def out_size(scale):
    return int(W * scale) // 2 * 2, int(H * scale) // 2 * 2


def _frame(t, scale):
    im = render(t)
    if scale != 1:
        im = im.resize(out_size(scale), Image.BILINEAR if scale < 1 else Image.LANCZOS)
    return im.tobytes()


def _frame_star(args):
    return _frame(*args)


def default_workers():
    return max(1, (os.cpu_count() or 2) - 1)


# 출력
def save(path, dur, scale, workers):
    from multiprocessing import Pool

    n = int(dur * FPS)
    size = out_size(scale)
    gif = path.lower().endswith(".gif")
    step = 2 if gif else 1                                  # gif는 15fps
    jobs = [(i / FPS, scale) for i in range(0, n, step)]
    start = time.time()

    def prog(i):
        el = time.time() - start
        sys.stdout.write(f"\r  {i + 1}/{len(jobs)} frames  ({el:5.1f}s, ETA {el / (i + 1) * (len(jobs) - i - 1):5.1f}s)")
        sys.stdout.flush()

    if not gif:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                sys.exit("mp4 저장엔 ffmpeg가 필요:  pip install imageio-ffmpeg   (또는 --save tree.gif)")
        proc = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "-",
                                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                                 "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    imgs = []
    with Pool(workers) as pool:
        for i, data in enumerate(pool.imap(_frame_star, jobs, chunksize=2)):
            if gif:
                imgs.append(Image.frombytes("RGB", size, data).quantize(colors=200))
            else:
                proc.stdin.write(data)
            prog(i)
    if gif:
        imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=1000 // (FPS // step), loop=0)
    else:
        proc.stdin.close()
        proc.wait()
    print(f"\n저장 완료 → {path}  ({time.time() - start:.1f}s, workers={workers})")


def live(scale, workers):
    import tkinter as tk
    from collections import deque
    from multiprocessing import Pool
    from PIL import ImageTk

    size = out_size(scale)
    pool = Pool(workers)
    inflight = deque()                 # 순서대로 쌓인 AsyncResult
    ahead = max(4, workers * 3)        # 미리 그려둘 프레임 수
    st = {"next": 0, "due": None, "shown": 0, "t0": time.time(), "fps": 0.0}

    root = tk.Tk()
    root.title("christmas_tree.py  ●  warming up…")
    root.configure(bg="#070b1a")
    label = tk.Label(root, bg="#070b1a", bd=0, width=size[0], height=size[1])
    label.pack()

    def refill():
        while len(inflight) < ahead:
            inflight.append(pool.apply_async(_frame, (st["next"] / FPS, scale)))
            st["next"] += 1

    def tick():
        refill()
        now = time.time()
        if st["due"] is not None and now < st["due"]:          # 30fps 넘지 않게
            root.after(max(1, int((st["due"] - now) * 1000)), tick)
            return
        if not inflight[0].ready():                           # 아직 안 그려졌으면 잠깐 대기
            root.after(2, tick)
            return
        photo = ImageTk.PhotoImage(Image.frombytes("RGB", size, inflight.popleft().get()))
        label.configure(image=photo)
        label.image = photo

        now = time.time()
        st["due"] = now + 1 / FPS if st["due"] is None else max(st["due"] + 1 / FPS, now - 0.05)
        st["shown"] += 1
        if now - st["t0"] >= 0.5:
            st["fps"] = st["shown"] / (now - st["t0"])
            st["shown"], st["t0"] = 0, now
            root.title(f"christmas_tree.py  ●  running · {st['fps']:.0f} fps  (workers={workers})")
        root.after(1, tick)

    def close():
        pool.terminate()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(1, tick)
    root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ASCII 크리스마스 트리")
    ap.add_argument("--save", metavar="PATH", help="mp4 또는 gif로 저장")
    ap.add_argument("--dur", type=float, default=12.0, help="저장할 길이(초)")
    ap.add_argument("--scale", type=float, default=None, help="출력 배율 (미리보기 기본 0.6, 저장 기본 1.0)")
    ap.add_argument("--workers", type=int, default=default_workers(), help="렌더 프로세스 수 (기본: 코어 수 - 1)")
    a = ap.parse_args()
    if a.save:
        save(a.save, a.dur, a.scale or 1.0, a.workers)
    else:
        live(a.scale or 0.6, a.workers)
