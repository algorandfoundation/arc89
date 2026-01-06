import pytest

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataPaginationArgs,
    AsaMetadataRegistryClient,
)


def _verify_metadata_pagination(
    client: AsaMetadataRegistryClient,
    metadata: AssetMetadata,
) -> None:
    """Helper function to verify metadata pagination properties."""
    pagination = client.send.arc89_get_metadata_pagination(
        args=Arc89GetMetadataPaginationArgs(asset_id=metadata.asset_id),
    ).abi_return
    assert pagination is not None
    assert pagination.metadata_size == metadata.body.size
    assert pagination.page_size == const.PAGE_SIZE
    assert pagination.total_pages == metadata.body.total_pages()


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_empty_metadata",
        "mutable_short_metadata",
        "mutable_maxed_metadata",
    ],
)
def test_arc89_metadata_pagination(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test pagination for different metadata sizes (empty, short, and maxed)."""
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    _verify_metadata_pagination(asa_metadata_registry_client, metadata)


# TODO: Test failing conditions
