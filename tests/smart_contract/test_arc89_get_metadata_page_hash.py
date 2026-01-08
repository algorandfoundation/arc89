import pytest
from algokit_utils import LogicError

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataPageHashArgs,
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
def test_not_empty_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    for p in range(metadata.body.total_pages()):
        page_hash = asa_metadata_registry_client.send.arc89_get_metadata_page_hash(
            args=Arc89GetMetadataPageHashArgs(asset_id=metadata.asset_id, page=p)
        ).abi_return
        assert page_hash is not None
        assert bytes(page_hash) == metadata.compute_page_hash(page_index=p)


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_page_hash(
            args=Arc89GetMetadataPageHashArgs(asset_id=NON_EXISTENT_ASA_ID, page=0),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_page_hash(
            args=Arc89GetMetadataPageHashArgs(asset_id=arc_89_asa, page=0),
        )


def test_fail_empty_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.EMPTY_METADATA):
        asa_metadata_registry_client.send.arc89_get_metadata_page_hash(
            args=Arc89GetMetadataPageHashArgs(
                asset_id=mutable_empty_metadata.asset_id, page=0
            ),
        )


def test_fail_page_idx_invalid(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    total_pages = mutable_short_metadata.body.total_pages()
    with pytest.raises(LogicError, match=err.PAGE_IDX_INVALID):
        asa_metadata_registry_client.send.arc89_get_metadata_page_hash(
            args=Arc89GetMetadataPageHashArgs(
                asset_id=mutable_short_metadata.asset_id,
                page=total_pages,  # Out of range (0-indexed)
            ),
        )
