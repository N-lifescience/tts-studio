"""앱 아이콘(icns) 만들기: web/public/favicon.svg 와 같은 모양을 Pillow 로 그린다."""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def draw(size):
    s = size / 32
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 2 * s  # macOS 아이콘은 가장자리 여백이 조금 있다
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=7 * s, fill="#1f5c4a")
    for x, y, h in [(7, 13, 6), (12, 9, 14), (17, 6, 20), (22, 11, 10)]:
        d.rounded_rectangle([x * s, y * s, (x + 3) * s, (y + h) * s], radius=1.5 * s, fill="#e9f3ee")
    return img


def main(out):
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            draw(base).save(iconset / f"icon_{base}x{base}.png")
            draw(base * 2).save(iconset / f"icon_{base}x{base}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", out], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
