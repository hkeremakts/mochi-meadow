import argparse
import os
from typing import Tuple

from PIL import Image


def normalize_image(img: Image.Image, out_size: Tuple[int, int]) -> Image.Image:
    # Trim transparent edges
    bbox = img.getbbox()
    if bbox is None:
        # empty frame, return blank canvas
        return Image.new("RGBA", out_size, (0, 0, 0, 0))
    trimmed = img.crop(bbox)

    out_w, out_h = out_size
    canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))

    # Bottom-center align: place trimmed so its bottom touches canvas bottom,
    # and horizontally centered
    tw, th = trimmed.size
    x = (out_w - tw) // 2
    y = out_h - th
    canvas.paste(trimmed, (x, y), trimmed)
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize PNG frames to a fixed size with bottom-center alignment.")
    parser.add_argument("input_dir", help="Directory containing PNG frames")
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=64)
    args = parser.parse_args()

    out_size = (args.width, args.height)

    count = 0
    for root, _, files in os.walk(args.input_dir):
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            path = os.path.join(root, f)
            img = Image.open(path).convert("RGBA")
            norm = normalize_image(img, out_size)
            norm.save(path)
            count += 1

    print(f"Normalized {count} frames in {args.input_dir}")


if __name__ == "__main__":
    main()



