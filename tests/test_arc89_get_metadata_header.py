import pytest

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataHeaderArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


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

    assert header.identifiers == metadata.identifiers
    assert header.reversible_flags == metadata.reversible_flags
    assert header.irreversible_flags == metadata.irreversible_flags
    assert bytes(header.hash) == metadata.metadata_hash
    assert header.last_modified_round == metadata.last_modified_round
    assert header.deprecated_by == metadata.deprecated_by
