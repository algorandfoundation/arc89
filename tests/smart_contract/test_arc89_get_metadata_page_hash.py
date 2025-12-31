import pytest

from src.generated.asa_metadata_registry_client import (
    Arc89GetMetadataPageHashArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_short_metadata",
        "mutable_maxed_metadata",
        "immutable_short_metadata",
        "immutable_maxed_metadata",
    ],
)
def test_not_empty_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    for p in range(metadata.total_pages):
        page_hash = asa_metadata_registry_client.send.arc89_get_metadata_page_hash(
            args=Arc89GetMetadataPageHashArgs(asset_id=metadata.asset_id, page=p)
        ).abi_return
        assert page_hash is not None
        assert bytes(page_hash) == metadata.compute_page_hash(p)


# TODO: Test failing conditions
