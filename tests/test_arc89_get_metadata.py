import pytest

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_empty_metadata",
        "mutable_short_metadata",
        "mutable_maxed_metadata",
        "mutable_json_obj_metadata",
        "immutable_empty_metadata",
        "immutable_short_metadata",
        "immutable_maxed_metadata",
        "immutable_json_obj_metadata",
    ],
)
def test_get_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    for p in range(metadata.total_pages):
        page = asa_metadata_registry_client.send.arc89_get_metadata(
            args=Arc89GetMetadataArgs(asset_id=metadata.asset_id, page=p),
        ).abi_return
        assert bytes(page.page_content).decode() == metadata.get_page(p).decode()
        assert page.has_next_page if p < metadata.total_pages - 1 else not page.has_next_page


# TODO: Test failing conditions
