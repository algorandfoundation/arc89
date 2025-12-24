import pytest

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataHashArgs,
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
def test_get_metadata_hash(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    am = asa_metadata_registry_client.send.arc89_get_metadata_hash(
        args=Arc89GetMetadataHashArgs(asset_id=metadata.asset_id),
    ).abi_return
    assert bytes(am) == metadata.compute_metadata_hash()
