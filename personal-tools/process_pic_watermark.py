"""Personal image watermark helper.

This script is a standalone personal utility. It is not used by the web app.

Purpose:
- Add a centered watermark to images in a target folder.
- Rename processed images in each folder to IMG_N.
- Keep the tool separate from the main Flask application code.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_PIC_DIR = SCRIPT_DIR / "pic"
DEFAULT_FONT = REPO_ROOT / "keep-html" / "fonts" / "SourceHanSansCN-Regular.otf"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="为目标目录中的图片添加居中水印，并按文件夹内顺序重命名为 IMG_N。"
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_PIC_DIR,
        help=f"待处理图片目录，默认 {DEFAULT_PIC_DIR}",
    )
    parser.add_argument(
        "--font",
        type=Path,
        default=DEFAULT_FONT,
        help=f"水印字体路径，默认 {DEFAULT_FONT}",
    )
    parser.add_argument(
        "--text-template",
        default="Watermark {index}",
        help="水印文字模板，可使用 {index} 表示图片序号，默认 'Watermark {index}'。",
    )
    return parser


def list_images_by_folder(target_dir: Path) -> Dict[Path, List[Path]]:
    grouped: Dict[Path, List[Path]] = defaultdict(list)
    for path in target_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            grouped[path.parent].append(path)

    for folder in grouped:
        grouped[folder] = sorted(grouped[folder], key=lambda item: item.name.lower())
    return dict(sorted(grouped.items(), key=lambda item: str(item[0]).lower()))


def choose_font(font_path: Path, image_size: tuple[int, int]) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_size = max(28, min(image_size) // 24)
    if font_path.exists():
        return ImageFont.truetype(str(font_path), font_size)
    return ImageFont.load_default()


def save_with_original_format(image: Image.Image, output_path: Path) -> None:
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        flattened = Image.new("RGB", image.size, (255, 255, 255))
        flattened.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
        flattened.save(output_path, quality=95)
        return
    image.save(output_path)


def add_center_watermark(image_path: Path, text: str, font_path: Path, output_path: Path) -> None:
    base = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = choose_font(font_path, base.size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (base.width - text_width) / 2
    y = (base.height - text_height) / 2

    shadow_offset = max(2, min(base.size) // 300)
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 120))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 150))

    merged = Image.alpha_composite(base, overlay)
    save_with_original_format(merged, output_path)


def process_folder(folder: Path, images: List[Path], font_path: Path, text_template: str) -> None:
    temp_paths: List[Path] = []
    final_paths: List[Path] = []

    for index, source_path in enumerate(images, start=1):
        watermark_text = text_template.format(index=index)
        temp_path = folder / f"__watermark_tmp_{index:04d}{source_path.suffix.lower()}"
        final_path = folder / f"IMG_{index}{source_path.suffix.lower()}"
        add_center_watermark(source_path, watermark_text, font_path, temp_path)
        temp_paths.append(temp_path)
        final_paths.append(final_path)

    for original in images:
        if original.exists():
            original.unlink()

    for temp_path, final_path in zip(temp_paths, final_paths):
        if final_path.exists():
            final_path.unlink()
        temp_path.rename(final_path)


def main() -> None:
    parser = build_argparser()
    args = parser.parse_args()
    target_dir = args.target.resolve()
    font_path = args.font.resolve()

    if not target_dir.exists():
        raise FileNotFoundError(f"目标目录不存在: {target_dir}")

    grouped_images = list_images_by_folder(target_dir)
    if not grouped_images:
        print(f"未在 {target_dir} 下找到可处理图片。")
        return

    total = 0
    for folder, images in grouped_images.items():
        process_folder(folder, images, font_path, args.text_template)
        total += len(images)
        print(f"已处理 {folder} 下 {len(images)} 张图片。")

    print(f"处理完成，共处理 {total} 张图片。")


if __name__ == "__main__":
    main()
