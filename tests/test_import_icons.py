"""scripts/import_icons.py keeps the pack's names and folders, cleaned mechanically.

Uses a small fake AWS pack built in memory, so nothing is downloaded.
"""

import importlib.util
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "import_icons", ROOT / "scripts" / "import_icons.py"
)
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)

TILE = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
    b'viewBox="0 0 64 64"><rect width="64" height="64" fill="#ED7100"/></svg>'
)
CATEGORY = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="90" height="90" '
    b'viewBox="0 0 90 90"><rect id="Rectangle" fill="#ED7100" x="5" y="5" '
    b'width="80" height="80"></rect><rect id="#879196-Border-Copy-5" '
    b'stroke="#879196" stroke-width="2" x="1" y="1" width="88" height="88">'
    b"</rect></svg>"
)


def _pack(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as pack:
        for name in members:
            pack.writestr(name, TILE)
    return zipfile.ZipFile(buffer)


def test_names_and_folders_come_from_the_pack():
    pack = _pack(
        [
            "Architecture-Service-Icons_07312026/Arch_Networking-Content-Delivery/64/Arch_AWS-Direct-Connect_64.svg",
            "Architecture-Service-Icons_07312026/Arch_Networking-Content-Delivery/32/Arch_AWS-Direct-Connect_32.svg",
            "Resource-Icons_07312026/Res_Networking-Content-Delivery/Res_AWS-Direct-Connect_Gateway_48.svg",
            "Resource-Icons_07312026/Res_General-Icons/Res_48_Light/Res_Users_48_Light.svg",
            "Resource-Icons_07312026/Res_General-Icons/Res_48_Dark/Res_Users_48_Dark.svg",
            "Category-Icons_07312026/Arch-Category_64/Arch-Category_Compute_64.svg",
            "Architecture-Group-Icons_07312026/Virtual-private-cloud-VPC_32.svg",
            "__MACOSX/Architecture-Service-Icons_07312026/._Arch_AWS-Direct-Connect_64.svg",
        ]
    )
    assert set(importer.plan("aws", [pack])) == {
        "networking-content-delivery/direct-connect",
        "networking-content-delivery/direct-connect-gateway",
        "general-icons/users",
        "category/compute",
        "group/virtual-private-cloud-vpc",
    }


def test_a_resource_named_like_a_service_gets_a_suffix():
    pack = _pack(
        [
            "Architecture-Service-Icons_07312026/Arch_Compute/64/Arch_Amazon-EC2-Auto-Scaling_64.svg",
            "Resource-Icons_07312026/Res_Compute/Res_Amazon-EC2_Auto-Scaling_48.svg",
        ]
    )
    assert set(importer.plan("aws", [pack])) == {
        "compute/ec2-auto-scaling",
        "compute/ec2-auto-scaling-resource",
    }


def test_service_icons_get_rounded_corners():
    image = importer.render(TILE, 256, rounded=True)
    assert image.getpixel((1, 1))[3] == 0  # corner cut away
    assert image.getpixel((128, 1))[3] == 255  # edge midpoint kept
    assert importer.render(TILE, 256, rounded=False).getpixel((1, 1))[3] == 255


def test_category_icons_lose_the_frame_round_their_tile():
    tile = importer.aws_category_tile(CATEGORY)
    assert b"Border" not in tile
    image = importer.render(tile, 90, rounded=False)
    # The tile now reaches the edge: no grey frame, no white margin
    assert image.getpixel((45, 0))[:3] == (0xED, 0x71, 0x00)


def test_icons_groups_py_uses_are_protected():
    used = importer.in_use("aws")
    assert "group/virtual-private-cloud-vpc" in used
    assert "group/public-subnet" in used
