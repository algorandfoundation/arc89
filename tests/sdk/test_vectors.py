"""The SDK reproduces the published conformance vectors."""

import base64
import json
from pathlib import Path
from urllib.parse import quote

import pytest

from asa_metadata_registry import AssetMetadata, MetadataBody, MetadataFlags
from asa_metadata_registry import constants as const
from asa_metadata_registry.codec import asset_id_to_box_name

VECTORS = json.loads(
    (Path(__file__).parents[1] / "vectors" / "arc89_vectors.json").read_text()
)


def test_parameters() -> None:
    p = VECTORS["parameters"]
    assert p["header_size"] == const.HEADER_SIZE
    assert p["page_size"] == const.PAGE_SIZE
    assert p["short_metadata_size"] == const.SHORT_METADATA_SIZE
    assert p["max_metadata_size"] == const.MAX_METADATA_SIZE
    assert (p["flat_mbr"], p["byte_mbr"]) == (const.FLAT_MBR, const.BYTE_MBR)


@pytest.mark.parametrize(
    "vector", VECTORS["box_names"], ids=lambda v: str(v["asset_id"])
)
def test_box_name_vector(vector: dict[str, object]) -> None:
    raw = asset_id_to_box_name(int(vector["asset_id"]))
    std = base64.b64encode(raw).decode()
    assert raw.hex() == vector["box_name_hex"]
    assert (
        base64.urlsafe_b64encode(raw).decode().rstrip("=") == vector["arc90_box_param"]
    )
    assert "b64:" + std == vector["algod_box_name"]
    assert quote("b64:" + std, safe="") == vector["algod_box_name_query"]


@pytest.mark.parametrize("vector", VECTORS["metadata"], ids=lambda v: str(v["name"]))
def test_metadata_vector(vector: dict[str, object]) -> None:
    md = AssetMetadata(
        asset_id=0,
        body=MetadataBody(raw_bytes=str(vector["body"]).encode()),
        flags=MetadataFlags.from_bytes(
            int(vector["reversible_flags"]), int(vector["irreversible_flags"])
        ),
        deprecated_by=0,
    )
    assert md.body.size == vector["metadata_size"]
    assert md.identifiers_byte == vector["identifiers"]
    assert md.compute_header_hash().hex() == vector["header_hash"]
    assert [
        md.compute_page_hash(page_index=i).hex() for i in range(md.body.total_pages())
    ] == vector["page_hashes"]
    assert md.compute_arc89_metadata_hash().hex() == vector["metadata_hash"]
    assert md.get_mbr_delta().amount == vector["box_mbr"]
    assert md.get_delete_mbr_delta().amount == vector["box_mbr"]
    header = bytes.fromhex(str(vector["header_hex"]))
    assert len(header) == const.HEADER_SIZE
    assert (
        header[: 3 + 32]
        == bytes(
            [
                md.identifiers_byte,
                int(vector["reversible_flags"]),
                int(vector["irreversible_flags"]),
            ]
        )
        + md.compute_arc89_metadata_hash()
    )
