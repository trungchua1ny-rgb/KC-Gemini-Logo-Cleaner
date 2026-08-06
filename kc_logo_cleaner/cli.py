from __future__ import annotations

import argparse
from pathlib import Path

from .models import MaskConfig
from .processor import process_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xử lý hàng loạt logo góc phải dưới ảnh Gemini.")
    parser.add_argument("input", type=Path, help="Thư mục ảnh nguồn")
    parser.add_argument("--output", type=Path, help="Thư mục kết quả")
    parser.add_argument("--width", type=float, default=4.0, help="Chiều rộng vùng logo theo %")
    parser.add_argument("--height", type=float, default=7.5, help="Chiều cao vùng logo theo %")
    parser.add_argument("--right", type=float, default=5.0, help="Lề phải theo %")
    parser.add_argument("--bottom", type=float, default=9.3, help="Lề dưới theo %")
    parser.add_argument("--padding", type=float, default=0.4, help="Padding theo cạnh ngắn, đơn vị %")
    parser.add_argument("--no-recursive", action="store_true", help="Không quét thư mục con")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    source = args.input.resolve()
    output = args.output.resolve() if args.output else source / "KC_Logo_Cleaned"
    config = MaskConfig(
        width_percent=args.width,
        height_percent=args.height,
        right_margin_percent=args.right,
        bottom_margin_percent=args.bottom,
        padding_percent=args.padding,
    )

    def show_progress(index: int, total: int, path: Path, _result: object) -> None:
        print(f"[{index}/{total}] {path.name}")

    results = process_batch(source, output, config, not args.no_recursive, show_progress)
    completed = sum(item.status == "completed" for item in results)
    failed = sum(item.status == "failed" for item in results)
    print(f"Hoàn tất: {completed} ảnh; lỗi: {failed}; kết quả: {output}")


if __name__ == "__main__":
    main()
