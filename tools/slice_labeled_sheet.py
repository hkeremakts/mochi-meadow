import argparse
import os
from typing import Dict, List, Tuple

from PIL import Image


def slice_sheet(
    sheet_path: str,
    output_dir: str,
    frame_width: int,
    frame_height: int,
    label_column_width: int,
    top_margin: int = 0,
    left_margin: int = 0,
    row_gap: int = 0,
    col_gap: int = 0,
    labels: Dict[int, str] | None = None,
) -> List[Tuple[str, int]]:
    image = Image.open(sheet_path).convert("RGBA")
    sheet_w, sheet_h = image.size

    os.makedirs(output_dir, exist_ok=True)

    results: List[Tuple[str, int]] = []

    # Compute how many frames per row given right of label column
    content_left = left_margin + label_column_width
    usable_w = sheet_w - content_left
    step_x = frame_width + col_gap
    if step_x <= 0:
        raise ValueError("Invalid step_x computed. Check frame_width/col_gap.")
    frames_per_row = max(1, usable_w // step_x)

    step_y = frame_height + row_gap
    if step_y <= 0:
        raise ValueError("Invalid step_y computed. Check frame_height/row_gap.")

    row_index = 0
    y = top_margin
    while y + frame_height <= sheet_h:
        label = labels.get(row_index, f"row{row_index}") if labels else f"row{row_index}"

        for i in range(frames_per_row):
            x = content_left + i * step_x
            if x + frame_width > sheet_w:
                break
            crop_box = (x, y, x + frame_width, y + frame_height)
            frame = image.crop(crop_box)
            # Skip fully transparent frames
            if frame.getbbox() is None:
                continue
            frame_idx = i + 1
            filename = f"{label}_{frame_idx:02d}.png"
            out_path = os.path.join(output_dir, filename)
            frame.save(out_path)
            results.append((label, frame_idx))

        row_index += 1
        y += step_y

    return results


def parse_label_map(path: str | None) -> Dict[int, str] | None:
    if not path:
        return None
    mapping: Dict[int, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # format: index=label
            if "=" not in line:
                continue
            idx_str, label = line.split("=", 1)
            idx = int(idx_str)
            mapping[idx] = label.strip()
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Slice a labeled sprite sheet into individual frames.")
    parser.add_argument("sheet", help="Path to the combined PNG with labels on the left")
    parser.add_argument("output", help="Output directory for frames")
    parser.add_argument("frame_width", type=int, help="Width of each frame in pixels")
    parser.add_argument("frame_height", type=int, help="Height of each frame in pixels")
    parser.add_argument("label_column_width", type=int, help="Width of the left label column in pixels")
    parser.add_argument("--top_margin", type=int, default=0)
    parser.add_argument("--left_margin", type=int, default=0)
    parser.add_argument("--row_gap", type=int, default=0)
    parser.add_argument("--col_gap", type=int, default=0)
    parser.add_argument("--labels", help="Optional path to row-index-to-name map (index=label)")

    args = parser.parse_args()
    label_map = parse_label_map(args.labels)

    results = slice_sheet(
        sheet_path=args.sheet,
        output_dir=args.output,
        frame_width=args.frame_width,
        frame_height=args.frame_height,
        label_column_width=args.label_column_width,
        top_margin=args.top_margin,
        left_margin=args.left_margin,
        row_gap=args.row_gap,
        col_gap=args.col_gap,
        labels=label_map,
    )

    print(f"Exported {len(results)} frames to {args.output}")


if __name__ == "__main__":
    main()


