import pytest
from algokit_utils import LogicError

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


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


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata(
            args=Arc89GetMetadataArgs(asset_id=NON_EXISTENT_ASA_ID, page=0),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata(
            args=Arc89GetMetadataArgs(asset_id=arc_89_asa, page=0),
        )


def test_fail_page_idx_invalid_non_empty(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    total_pages = mutable_short_metadata.body.total_pages()
    with pytest.raises(LogicError, match=err.PAGE_IDX_INVALID):
        asa_metadata_registry_client.send.arc89_get_metadata(
            args=Arc89GetMetadataArgs(
                asset_id=mutable_short_metadata.asset_id,
                page=total_pages,  # Out of range (0-indexed)
            ),
        )


def test_fail_page_idx_invalid_empty(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
) -> None:
    # For empty metadata, page 0 is valid but page 1+ is not
    with pytest.raises(LogicError, match=err.PAGE_IDX_INVALID):
        asa_metadata_registry_client.send.arc89_get_metadata(
            args=Arc89GetMetadataArgs(
                asset_id=mutable_empty_metadata.asset_id,
                page=1,  # Invalid for empty metadata
            ),
        )
