import pytest
from algokit_utils import LogicError

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataPaginationArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


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


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_pagination(
            args=Arc89GetMetadataPaginationArgs(asset_id=NON_EXISTENT_ASA_ID),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_pagination(
            args=Arc89GetMetadataPaginationArgs(asset_id=arc_89_asa),
        )
