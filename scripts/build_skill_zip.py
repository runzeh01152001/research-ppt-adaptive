#!/usr/bin/env python
"""打包技能分发 zip：内部顶层直接是 SKILL.md，上传即用。

用法：
    python scripts/build_skill_zip.py                 # 输出到 dist/
    python scripts/build_skill_zip.py --out custom.zip

只打包运行所需内容（SKILL.md、references/、scripts/、requirements.txt），
不含 tests/、.git/、dist/，避免技能包里混入开发文件。
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "research-ppt-adaptive"

INCLUDE_DIRS = ("references", "scripts")
INCLUDE_FILES = ("SKILL.md", "LICENSE", "requirements.txt")
EXCLUDE = {"__pycache__", "build_skill_zip.py"}


def collect() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_FILES:
        path = ROOT / name
        if path.is_file():
            files.append(path)
    for dirname in INCLUDE_DIRS:
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if EXCLUDE & set(path.parts):
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            files.append(path)
    return files


def build(out: Path) -> tuple[Path, int, int]:
    files = collect()
    missing = [n for n in INCLUDE_FILES[:1] if not (ROOT / n).is_file()]
    if missing:
        raise SystemExit(f"缺少必需文件：{', '.join(missing)}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())

    total = sum(p.stat().st_size for p in files)
    return out, len(files), total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="打包技能分发 zip")
    parser.add_argument(
        "--out",
        default=str(ROOT / "dist" / f"{NAME}.zip"),
        help="输出路径（默认 dist/research-ppt-adaptive.zip）",
    )
    args = parser.parse_args(argv)

    out = Path(args.out).resolve()
    path, count, raw = build(out)
    ratio = path.stat().st_size / raw * 100 if raw else 0
    print(f"已生成 {path}")
    print(f"文件数 {count}　原始 {raw / 1024:.1f} KB　压缩后 {path.stat().st_size / 1024:.1f} KB（{ratio:.0f}%）")
    print("zip 内顶层为 SKILL.md，可直接在技能管理里上传。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
