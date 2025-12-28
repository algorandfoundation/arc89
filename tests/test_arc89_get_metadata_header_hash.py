import pytest

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataHeaderHashArgs,
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
def test_get_metadata_header_hash(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    hh = asa_metadata_registry_client.send.arc89_get_metadata_header_hash(
        args=Arc89GetMetadataHeaderHashArgs(asset_id=metadata.asset_id),
    ).abi_return
    assert hh is not None
    assert bytes(hh) == metadata.compute_header_hash()
