#!/usr/bin/env python3
"""Make web-sized copies of the example diagrams for the docs gallery.

    python scripts/make_gallery_images.py            # only out-of-date files
    python scripts/make_gallery_images.py --force    # redo every file

The example diagrams in examples/graphs/*.png are the full-size renders, often
8,000 px wide and close to 1 MB each. The gallery page used to embed all of
them, which made it heavy enough that Google's live URL test timed out. This
script trims the white margin off each PNG, scales it to at most MAX_WIDTH px
wide and writes it as WebP to docs/assets/gallery/<name>.webp, so the page
loads a small copy and links to the full-size PNG.

docs/assets/gallery/sources.json records the SHA-256 of the PNG each WebP was
made from, along with the WebP's pixel size. A file whose hash and settings
have not changed is skipped, so the script is safe to rerun and does not depend
on file modification times, which git does not preserve. Needs Pillow
(``pip install pillow``).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "examples" / "graphs"
OUTPUT_DIR = ROOT / "docs" / "assets" / "gallery"
MANIFEST = OUTPUT_DIR / "sources.json"

MAX_WIDTH = 1400
QUALITY = 85
# Pixels of white kept around the trimmed diagram, measured in the full-size
# PNG, so borders and arrowheads at the edge do not touch the frame.
MARGIN = 40
# Bump when the processing above changes so every file is regenerated.
SETTINGS = f"trim-margin{MARGIN}-w{MAX_WIDTH}-q{QUALITY}-webp"

# The full-size renders are larger than Pillow's decompression-bomb limit.
Image.MAX_IMAGE_PIXELS = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def flatten(image: Image.Image) -> Image.Image:
    """Return the image as RGB with any transparency filled white."""
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")
    return image.convert("RGB")


def trim(image: Image.Image) -> Image.Image:
    """Crop surrounding white space, keeping MARGIN px around the content."""
    white = Image.new("RGB", image.size, (255, 255, 255))
    bbox = ImageChops.difference(image, white).getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    return image.crop(
        (
            max(left - MARGIN, 0),
            max(top - MARGIN, 0),
            min(right + MARGIN, image.width),
            min(bottom + MARGIN, image.height),
        )
    )


def scale(image: Image.Image) -> Image.Image:
    if image.width <= MAX_WIDTH:
        return image
    height = round(image.height * MAX_WIDTH / image.width)
    return image.resize((MAX_WIDTH, height), Image.Resampling.LANCZOS)


def convert(source: Path, target: Path) -> Image.Image:
    with Image.open(source) as original:
        image = scale(trim(flatten(original)))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "WEBP", quality=QUALITY, method=6)
    return image


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="regenerate every file")
    args = parser.parse_args()

    sources = sorted(SOURCE_DIR.glob("*.png"))
    if not sources:
        print(f"no PNG files in {SOURCE_DIR}", file=sys.stderr)
        return 1

    manifest = load_manifest()
    written = skipped = 0
    for source in sources:
        name = source.stem
        target = OUTPUT_DIR / f"{name}.webp"
        digest = sha256(source)
        entry = manifest.get(name)
        if (
            not args.force
            and target.exists()
            and entry
            and entry.get("source_sha256") == digest
            and entry.get("settings") == SETTINGS
        ):
            skipped += 1
            continue
        image = convert(source, target)
        manifest[name] = {
            "source": source.relative_to(ROOT).as_posix(),
            "source_sha256": digest,
            "settings": SETTINGS,
            "width": image.width,
            "height": image.height,
        }
        written += 1
        print(
            f"{target.relative_to(ROOT)}  {image.width}x{image.height}"
            f"  {target.stat().st_size / 1024:.0f} kB"
        )

    # Drop entries whose source PNG has been removed.
    names = {source.stem for source in sources}
    for stale in sorted(set(manifest) - names):
        del manifest[stale]
        (OUTPUT_DIR / f"{stale}.webp").unlink(missing_ok=True)
        print(f"removed {stale}.webp (source gone)")

    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"{written} written, {skipped} up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
