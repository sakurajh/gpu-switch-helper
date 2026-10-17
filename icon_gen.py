# -*- coding: utf-8 -*-
"""生成 GPU 切换助手图标 icon.png / icon.ico（Pillow 绘制）"""
from PIL import Image, ImageDraw, ImageFilter

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# ---------- 圆角深蓝渐变背景 ----------
bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
db = ImageDraw.Draw(bg)
top, bottom = (31, 35, 60), (17, 21, 42)
for y in range(S):
    t = y / S
    c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    db.line([(0, y), (S, y)], fill=(c[0], c[1], c[2], 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([4, 4, S - 4, S - 4], radius=54, fill=255)
bg.putalpha(mask)
img.alpha_composite(bg)

# ---------- 芯片背后光晕 ----------
glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse([66, 66, 190, 190], fill=(124, 140, 248, 90))
glow = glow.filter(ImageFilter.GaussianBlur(14))
img.alpha_composite(glow)

# ---------- 四角电路连线 + 节点 ----------
trace = (56, 189, 248, 200)
for (x1, y1, x2, y2) in [
    (58, 58, 84, 84), (198, 58, 172, 84), (58, 198, 84, 172), (198, 198, 172, 172),
    (58, 128, 84, 128), (198, 128, 172, 128), (128, 58, 128, 84), (128, 198, 128, 172),
]:
    ImageDraw.Draw(img).line([x1, y1, x2, y2], fill=trace, width=3)
dot = (124, 140, 248, 255)
for (cx, cy) in [(58, 58), (198, 58), (58, 198), (198, 198), (58, 128), (198, 128), (128, 58), (128, 198)]:
    ImageDraw.Draw(img).ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=dot)

# ---------- 芯片主体 ----------
chip = Image.new("RGBA", (S, S), (0, 0, 0, 0))
cd = ImageDraw.Draw(chip)
cd.rounded_rectangle([78, 78, 178, 178], radius=18, fill=(38, 44, 70, 255))
cd.rounded_rectangle([78, 78, 178, 178], radius=18, outline=(124, 140, 248, 255), width=4)
img.alpha_composite(chip)

# ---------- 芯片引脚 ----------
pin = (56, 189, 248, 220)
for i in range(5):
    y = 92 + i * 16
    ImageDraw.Draw(img).line([70, y, 78, y], fill=pin, width=3)
    ImageDraw.Draw(img).line([178, y, 186, y], fill=pin, width=3)
for i in range(5):
    x = 92 + i * 16
    ImageDraw.Draw(img).line([x, 70, x, 78], fill=pin, width=3)
    ImageDraw.Draw(img).line([x, 178, x, 186], fill=pin, width=3)

# ---------- 芯片内部走线 ----------
ImageDraw.Draw(img).line([92, 92, 112, 92], fill=(56, 189, 248, 210), width=2)
ImageDraw.Draw(img).line([112, 92, 112, 104], fill=(56, 189, 248, 210), width=2)
ImageDraw.Draw(img).line([164, 164, 150, 164], fill=(124, 140, 248, 200), width=2)
ImageDraw.Draw(img).line([150, 164, 150, 152], fill=(124, 140, 248, 200), width=2)

# ---------- 闪电（带光晕）----------
bolt = [(140, 92), (106, 140), (128, 140), (120, 168), (154, 120), (132, 120), (146, 92)]
bglow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(bglow).polygon(bolt, fill=(56, 189, 248, 230))
bglow = bglow.filter(ImageFilter.GaussianBlur(6))
img.alpha_composite(bglow)
ImageDraw.Draw(img).polygon(bolt, fill=(228, 242, 255, 255))

img.save("icon.png")
img.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon OK:", img.size)
