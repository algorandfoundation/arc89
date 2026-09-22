"""The registry reproduces the published conformance vectors."""

import json
from pathlib import Path

import pytest
from algokit_utils import AssetCreateParams, SigningAccount

from asa_metadata_registry import AssetMetadata, MetadataBody, MetadataFlags
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89GetMetadataMbrDeltaArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.utils import create_metadata, get_metadata_from_state

VECTORS = json.loads(
    (Path(__file__).parents[1] / "vectors" / "arc89_vectors.json").read_text()
)


@pytest.mark.parametrize(
    "vector",
    [v for v in VECTORS["metadata"] if int(v["irreversible_flags"]) & 0x07 == 0],
    ids=lambda v: str(v["name"]),
)
def test_metadata_vector_on_chain(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    vector: dict[str, object],
) -> None:
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address, manager=asset_manager.address, total=42
        )
    ).asset_id
    metadata = AssetMetadata(
        asset_id=asset_id,
        body=MetadataBody(raw_bytes=str(vector["body"]).encode()),
        flags=MetadataFlags.from_bytes(
            int(vector["reversible_flags"]), int(vector["irreversible_flags"])
        ),
        deprecated_by=0,
    )
    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    record = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert record.header.identifiers == vector["identifiers"]
    assert record.header.metadata_hash.hex() == vector["metadata_hash"]

    delete_quote = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=asset_id, new_metadata_size=const.DELETE_METADATA_SIZE
        ),
    ).abi_return
    assert delete_quote is not None
    assert delete_quote.amount == vector["box_mbr"]
