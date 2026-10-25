"""Builds the macOS-style app icon (rounded square with a margin and a soft shadow, as Apple's
icon grid) from launcher/io.github.sacredfire.Launcher.png: icon.png (1024) and the .iconset."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

source, out = Path(sys.argv[1]), Path(sys.argv[2])
size, body, radius = 1024, 824, 185
art = Image.open(source).convert("RGBA")
# Art that is already a rounded square on an opaque black background: crop to it (the black
# corners would show in the Dock), then the mask below makes the corners transparent.
gray = art.convert("L").point(lambda v: 255 if v > 24 else 0)
box = gray.getbbox()
if box and (box[2] - box[0]) < art.width or (box and art.getpixel((2, 2))[:3] == (0, 0, 0)):
    art = art.crop(box)
art = art.resize((body, body), Image.LANCZOS)
mask = Image.new("L", (body, body), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, body - 1, body - 1), radius=radius, fill=255)
icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
offset = (size - body) // 2
shadow_mask = Image.new("L", (size, size), 0)
ImageDraw.Draw(shadow_mask).rounded_rectangle((offset, offset + 12, offset + body, offset + body + 12),
                                              radius=radius, fill=110)
shadow.putalpha(shadow_mask.filter(ImageFilter.GaussianBlur(18)))
icon.alpha_composite(shadow)
icon.paste(art, (offset, offset), mask)
out.mkdir(parents=True, exist_ok=True)
icon.save(out / "icon.png")
iconset = out / "CTR-Online.iconset"
iconset.mkdir(exist_ok=True)
for s in (16, 32, 128, 256, 512):
    icon.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
    icon.resize((s * 2, s * 2), Image.LANCZOS).save(iconset / f"icon_{s}x{s}@2x.png")
