from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def main():
    out = Path(__file__).parent / "synthetic_xray.png"
    y, x = np.mgrid[-1:1:512j, -1:1:512j]
    image = np.clip(20 + 155 * np.exp(-2.5 * (x*x + y*y)), 0, 255).astype("uint8")
    canvas = Image.fromarray(image, "L")
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((140, 70, 250, 430), outline=205, width=7)
    draw.ellipse((262, 70, 372, 430), outline=205, width=7)
    draw.line((256, 50, 256, 460), fill=230, width=10)
    canvas.save(out)
    print(out)


if __name__ == "__main__":
    main()
