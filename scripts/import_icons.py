#!/usr/bin/env python3
"""Import a cloud's official icon pack into resource_images/<cloud>/.

    poetry run python scripts/import_icons.py aws               # download the pinned pack(s)
    poetry run python scripts/import_icons.py azure --zip PATH  # or use a local copy
    poetry run python scripts/import_icons.py gcp --dry-run     # report, write nothing

The clouds are aws, azure and gcp. Icons keep the pack's own names, cleaned
only mechanically (prefixes, numbers and size suffixes, case), and its own
folders:

    AWS    Arch_Networking-Content-Delivery/64/Arch_AWS-Direct-Connect_64.svg
           -> networking-content-delivery/direct-connect.png
    Azure  Icons/ai + machine learning/00028-icon-service-Batch-AI.svg
           -> ai-machine-learning/batch-ai.png
    GCP    Unique Icons/Cloud Storage/SVG/Cloud_Storage-512-color.svg
           -> unique/cloud-storage.png

Every icon is rendered from the pack's SVG at one size per cloud, the size
its diagrams lay out with: Azure (256 px) and GCP (512 px) draw icons at
their pixel size, AWS scales them to the node. AWS service and category icons
get mingrammer's rounded corners (12.5% radius).

Two folders are never touched: retired/ holds icons of services the
provider discontinued, still drawn for their Terraform types, and
terravision/ holds TerraVision's own (tv_blank, Karpenter). Anything else not
in the pack is deleted, so the import stops first if terraform_icons.yml or
groups.py uses an icon the pack no longer has: remap the entry to the new
icon, or, for a discontinued service, move the file to retired/ and point the
entry there. Afterwards run scripts/generate_icon_classes.py.
"""

import argparse
import io
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import cairosvg
import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path.home() / ".cache" / "terravision" / "icon-packs"

# The pack each cloud imports. Bump the URL deliberately: AWS and Azure put a
# version in the file name, so there is no stable "latest" link.
PACKS = {
    "aws": {
        "urls": [
            "https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_07312026.5846e92413caa21490223536cc97f1269e44fa92.zip"
        ],
        "size": 512,
    },
    "azure": {
        "urls": [
            "https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V24.zip"
        ],
        "size": 256,
    },
    "gcp": {
        # Google's names carry no version: the same URLs serve each release
        "urls": [
            "https://services.google.com/fh/files/misc/category-icons.zip",
            "https://services.google.com/fh/files/misc/core-products-icons.zip",
        ],
        "size": 512,
    },
}

# Folders the import leaves alone (see the module docstring)
KEPT = ("retired", "terravision")
# Rounded corners on AWS service icons: radius as a share of the icon size,
# the look of mingrammer's round tool that TerraVision's icons always had.
CORNER = 0.125


def aws_entries(packs):
    """(folder, name, (pack, member), kind) for each icon in the AWS pack.

    Service icons: Architecture-Service-Icons_*/Arch_<Category>/64/*.svg.
    Resource icons: Resource-Icons_*/Res_<Category>/*.svg, the Light variant
    where there are Light and Dark ones (diagrams are drawn on white).
    Category and group icons: one folder each.
    """
    for pack, member in _svgs(packs):
        parts = member.split("/")
        stem = Path(member).stem
        if stem.endswith("_Dark"):
            continue
        source = (pack, member)
        if "Architecture-Service-Icons_" in member and parts[-2] == "64":
            yield clean(parts[-3]), aws_name(stem), source, "service"
        elif "Resource-Icons_" in member:
            # Res_<Category>/, or Res_General-Icons/Res_48_Light/
            category = next(p for p in parts if p.startswith("Res_"))
            yield clean(category), aws_name(stem), source, "resource"
        elif "Category-Icons_" in member and parts[-2].endswith("_64"):
            yield "category", aws_name(stem), source, "category"
        elif "Architecture-Group-Icons_" in member:
            yield "group", aws_name(stem), source, "group"


def azure_entries(packs):
    """Icons/<folder>/<number>-icon-service-<Name>.svg, one folder each."""
    for pack, member in _svgs(packs):
        parts = member.split("/")
        if len(parts) < 3 or parts[-3] != "Icons":
            continue
        name = re.sub(r"^\d+-icon-service-", "", Path(member).stem)
        yield clean(parts[-2]), clean(name), (pack, member), "service"


def gcp_entries(packs):
    """<Kind> Icons/<Product>/SVG/*.svg, named after the product folder."""
    kinds = {"Category Icons": "category", "Unique Icons": "unique"}
    for pack, member in _svgs(packs):
        parts = member.split("/")
        if len(parts) == 4 and parts[0] in kinds and parts[2] == "SVG":
            kind = kinds[parts[0]]
            yield kind, clean(parts[1]), (pack, member), kind


def _svgs(packs):
    for pack in packs:
        for member in pack.namelist():
            if member.endswith(".svg") and "__MACOSX" not in member:
                yield pack, member


def clean(text: str) -> str:
    """Arch_Networking-Content-Delivery -> networking-content-delivery."""
    text = re.sub(r"^(Arch|Res|Arch-Category)_", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def aws_name(stem: str) -> str:
    """Res_Amazon-EC2_Elastic-IP-Address_48_Light -> ec2-elastic-ip-address."""
    stem = re.sub(r"^(Arch|Res|Arch-Category)_", "", stem)
    stem = re.sub(r"_(16|32|48|64)(@5x)?(_Light)?$", "", stem)
    stem = re.sub(r"^(Amazon|AWS)-", "", stem)
    stem = re.sub(r"_(Amazon|AWS)-", "_", stem)
    return clean(stem)


ENTRIES = {"aws": aws_entries, "azure": azure_entries, "gcp": gcp_entries}


def fetch(cloud: str, zip_paths=None) -> list:
    """The cloud's pack(s): the given local zips, or the pinned URLs (cached)."""
    if zip_paths:
        return [zipfile.ZipFile(p) for p in zip_paths]
    packs = []
    for url in PACKS[cloud]["urls"]:
        target = CACHE / url.rsplit("/", 1)[-1]
        if not target.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            print(f"downloading {url}")
            with urllib.request.urlopen(url) as resp, open(target, "wb") as out:
                shutil.copyfileobj(resp, out)
        packs.append(zipfile.ZipFile(target))
    return packs


def plan(cloud: str, packs: list) -> dict:
    """<folder>/<name> -> ((pack, member), kind); fails on two icons with one name.

    A resource icon that cleans to a service icon's name (AWS's
    Res_Amazon-EC2_Auto-Scaling and Arch_Amazon-EC2-Auto-Scaling) gets
    "-resource" after it, and the second of two numbered Azure files with one
    name gets its number.
    """
    entries = sorted(ENTRIES[cloud](packs), key=lambda e: (e[3] != "service", e[2][1]))
    found, clashes = {}, []
    for folder, name, source, kind in entries:
        key = f"{folder}/{name}"
        if key in found and kind == "resource" and found[key][1] == "service":
            key += "-resource"
        number = re.match(r"(\d+)-", Path(source[1]).name)
        if key in found and number:
            # Azure ships some names twice, numbered apart (00330- and
            # 00400-icon-service-Workspaces): the later one keeps its number
            key += f"-{number.group(1)}"
        if key in found:
            clashes.append(f"{key}: {found[key][0][1]} and {source[1]}")
            continue
        found[key] = (source, kind)
    if clashes:
        sys.exit("two pack icons clean to one name:\n  " + "\n  ".join(clashes))
    return dict(sorted(found.items()))


def aws_category_tile(svg: bytes) -> bytes:
    """An AWS category icon without the grey frame drawn round its tile.

    The category SVGs put the coloured tile at 5..85 of a 90-unit canvas and a
    "#879196-Border" rectangle around it; keep just the tile, so it renders
    edge to edge like a service icon.
    """
    text = svg.decode()
    text = re.sub(r'<rect id="[^"]*Border[^"]*"[^>]*>\s*(</rect>)?', "", text)
    text = text.replace('viewBox="0 0 90 90"', 'viewBox="5 5 80 80"', 1)
    return text.encode()


def render(svg: bytes, size: int, rounded: bool) -> Image.Image:
    """The SVG as a size x size PNG; a non-square one is fitted and centred."""
    image = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg, output_width=size)))
    if image.height > size:
        png = cairosvg.svg2png(bytestring=svg, output_height=size)
        image = Image.open(io.BytesIO(png))
    image = image.convert("RGBA")
    if image.size != (size, size):
        square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        square.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
        image = square
    if rounded:
        # Mask drawn at 4x and scaled down, for smooth corners
        big = size * 4
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, big - 1, big - 1), radius=round(big * CORNER), fill=255
        )
        mask = mask.resize((size, size), Image.LANCZOS)
        alpha = Image.composite(image.getchannel("A"), mask, mask)
        image.putalpha(alpha)
    return image


def in_use(cloud: str) -> set:
    """Icon keys terraform_icons.yml, groups.py and the cloud's config use."""
    keys = set()
    mapping = ROOT / "resource_classes" / cloud / "terraform_icons.yml"
    for key in yaml.safe_load(mapping.read_text()).values():
        if key.count("/") == 1:
            keys.add(key)
    groups = (ROOT / "resource_classes" / cloud / "groups.py").read_text()
    groups += (ROOT / "modules" / "config" / f"cloud_config_{cloud}.py").read_text()
    # "group/region.png" in a label cell, or a full resource_images/ path
    for folder, name in re.findall(
        rf'(?:resource_images/{cloud}/|")([a-z0-9_-]+)/([a-z0-9_.-]+)\.png', groups
    ):
        keys.add(f"{folder}/{name}")
    return keys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("cloud", choices=sorted(PACKS))
    parser.add_argument(
        "--zip", action="append", help="a local copy of the pack (repeat for GCP's two)"
    )
    parser.add_argument("--dry-run", action="store_true", help="report only")
    args = parser.parse_args()

    cloud, settings = args.cloud, PACKS[args.cloud]
    packs = fetch(cloud, args.zip)
    icons = plan(cloud, packs)
    base = ROOT / "resource_images" / cloud
    current = {
        f"{p.parent.name}/{p.stem}": p
        for p in base.glob("*/*.png")
        if p.parent.name not in KEPT
    }
    used = {k for k in in_use(cloud) if k.split("/")[0] not in KEPT}
    added = sorted(set(icons) - set(current))
    gone = sorted(set(current) - set(icons))
    lost = sorted(used - set(icons))
    print(f"{cloud}: {len(icons)} icons in the pack")
    print(f"  {len(set(icons) & set(current))} already here under the same name")
    print(f"  {len(added)} new, {len(gone)} here but not in the pack")
    if lost:
        sys.exit(
            "in use but not in the pack; remap these in terraform_icons.yml or "
            "groups.py, or move a discontinued service's icon to retired/:\n  "
            + "\n  ".join(lost)
        )
    if args.dry_run:
        return

    for key in gone:
        current[key].unlink()
    for key, ((pack, member), kind) in icons.items():
        target = base / f"{key}.png"
        target.parent.mkdir(exist_ok=True)
        svg = pack.read(member)
        if cloud == "aws" and kind == "category":
            svg = aws_category_tile(svg)
        # AWS service and category icons are square tiles: round their corners
        rounded = cloud == "aws" and kind in ("service", "category")
        render(svg, settings["size"], rounded).save(target, optimize=True)
    for folder in base.iterdir():
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    print(f"wrote {len(icons)} icons; now run scripts/generate_icon_classes.py")


if __name__ == "__main__":
    main()
