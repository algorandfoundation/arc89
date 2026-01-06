import pytest

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataArgs,
    AsaMetadataRegistryClient,
)


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_short_metadata",
        "mutable_maxed_metadata",
        "immutable_short_metadata",
        "immutable_maxed_metadata",
    ],
)
def test_non_empty_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    for p in range(metadata.body.total_pages()):
        page = asa_metadata_registry_client.send.arc89_get_metadata(
            args=Arc89GetMetadataArgs(asset_id=metadata.asset_id, page=p),
        ).abi_return
        assert page is not None
        assert bytes(page.page_content).decode() == metadata.body.get_page(p).decode()
        assert (
            page.has_next_page
            if p < metadata.body.total_pages() - 1
            else not page.has_next_page
        )


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_empty_metadata",
        "immutable_empty_metadata",
    ],
)
def test_empty_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    page = asa_metadata_registry_client.send.arc89_get_metadata(
        args=Arc89GetMetadataArgs(asset_id=metadata.asset_id, page=0),
    ).abi_return
    assert page is not None
    assert not page.page_content


# TODO: Test failing conditions
