import pytest

from src.asa_metadata_registry import AssetMetadata
from src.asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataHeaderArgs,
    AsaMetadataRegistryClient,
)


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_empty_metadata",
        "mutable_short_metadata",
        "mutable_maxed_metadata",
        "immutable_empty_metadata",
        "immutable_short_metadata",
        "immutable_maxed_metadata",
    ],
)
def test_get_metadata_header(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)

    header = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=metadata.asset_id),
    ).abi_return
    assert header is not None

    assert header.identifiers == metadata.identifiers_byte
    assert header.reversible_flags == metadata.flags.reversible_byte
    assert header.irreversible_flags == metadata.flags.irreversible_byte
    assert bytes(header.hash) == metadata.compute_metadata_hash()
    assert header.deprecated_by == metadata.deprecated_by
