"""Generate ARC-89 conformance vectors (tests/vectors/arc89_vectors.json)."""

import base64
import json
from pathlib import Path
from urllib.parse import quote

from asa_metadata_registry import AssetMetadata, MetadataBody, MetadataFlags
from asa_metadata_registry import constants as const
from asa_metadata_registry.codec import asset_id_to_box_name

OUT = Path(__file__).with_name("arc89_vectors.json")
ASSET_IDS = [0, 1, 12345, 2**32, 2**63 - 1, 2**64 - 1]
SIZES = [0, 1006, 1007, 1008, 4096, 4097, const.MAX_METADATA_SIZE]
FLAGS = [
    (0x00, 0x00),
    (0xFF, 0xF8),
]  # (reversible, irreversible); 0xF8 avoids ASA-dependent bits


def body(size: int) -> bytes:
    return b"" if size == 0 else b'{"v":"' + b"a" * (size - 8) + b'"}'


def box_name_vector(asset_id: int) -> dict[str, object]:
    raw = asset_id_to_box_name(asset_id)
    std = base64.b64encode(raw).decode()
    return {
        "asset_id": asset_id,
        "box_name_hex": raw.hex(),
        "arc90_box_param": base64.urlsafe_b64encode(raw).decode().rstrip("="),
        "algod_box_name": "b64:" + std,
        "algod_box_name_query": quote("b64:" + std, safe=""),
    }


def metadata_vector(size: int, reversible: int, irreversible: int) -> dict[str, object]:
    raw = body(size)
    md = AssetMetadata(
        asset_id=0,
        body=MetadataBody(raw_bytes=raw),
        flags=MetadataFlags.from_bytes(reversible, irreversible),
        deprecated_by=0,
    )
    metadata_hash = md.compute_arc89_metadata_hash()
    revision, deprecated_by = 1, 0
    header = (
        bytes([md.identifiers_byte, reversible, irreversible])
        + metadata_hash
        + revision.to_bytes(8, "big")
        + deprecated_by.to_bytes(8, "big")
    )
    return {
        "name": f"size{size}_rev{reversible:02x}_irr{irreversible:02x}",
        "body": raw.decode(),
        "metadata_size": size,
        "identifiers": md.identifiers_byte,
        "reversible_flags": reversible,
        "irreversible_flags": irreversible,
        "header_hash": md.compute_header_hash().hex(),
        "page_hashes": [
            md.compute_page_hash(page_index=i).hex()
            for i in range(md.body.total_pages())
        ],
        "metadata_hash": metadata_hash.hex(),
        "revision": revision,
        "deprecated_by": deprecated_by,
        "header_hex": header.hex(),
        "box_mbr": md.get_mbr_delta().amount,
    }


def main() -> None:
    vectors = {
        "description": (
            'ARC-89 conformance vectors. Bodies are the UTF-8 JSON {"v":"a...a"} padded to '
            "metadata_size (empty for 0). header_hex uses the given revision and deprecated_by. "
            "box_mbr is the Box MBR (creation delta POS, deletion delta NEG)."
        ),
        "parameters": {
            "box_key_size": const.ASSET_METADATA_BOX_KEY_SIZE,
            "header_size": const.HEADER_SIZE,
            "page_size": const.PAGE_SIZE,
            "short_metadata_size": const.SHORT_METADATA_SIZE,
            "max_metadata_size": const.MAX_METADATA_SIZE,
            "flat_mbr": const.FLAT_MBR,
            "byte_mbr": const.BYTE_MBR,
        },
        "hash_domains": {
            "header": const.HASH_DOMAIN_HEADER.decode(),
            "page": const.HASH_DOMAIN_PAGE.decode(),
            "metadata": const.HASH_DOMAIN_METADATA.decode(),
        },
        "box_names": [box_name_vector(a) for a in ASSET_IDS],
        "metadata": [metadata_vector(s, r, i) for s in SIZES for r, i in FLAGS],
    }
    OUT.write_text(json.dumps(vectors, indent=2) + "\n")


if __name__ == "__main__":
    main()
