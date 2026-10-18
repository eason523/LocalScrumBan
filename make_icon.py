"""make_icon.py — 用 Pillow 生成多尺寸 .ico 应用图标。"""

from PIL import Image, ImageDraw

BG = (15, 23, 42)        # #0f172a 深蓝底
COL1 = (59, 130, 246)    # 蓝 — 待处理
COL2 = (245, 158, 11)    # 黄 — 进行中
COL3 = (16, 185, 129)    # 绿 — 已完成

def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 5
    # 圆角背景
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG + (255,))
    # 三列色块
    pad = size // 5
    gap = size // 12
    w = (size - 2 * pad - 2 * gap) // 3
    col_h = size - 2 * pad
    xs = [pad, pad + w + gap, pad + 2 * (w + gap)]
    hs = [int(col_h * 0.55), int(col_h * 0.8), col_h]  # 渐进高度寓意进度
    for x, h, c in zip(xs, hs, (COL1, COL2, COL3)):
        d.rounded_rectangle(
            [x, size - pad - h, x + w, size - pad],
            radius=max(2, w // 4), fill=c + (255,),
        )
    return img

base = draw(256)
base.save("assets/icon.ico",
          sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                 (128, 128), (256, 256)])
base.save("assets/icon.png")
print("icon written to assets/icon.ico")
