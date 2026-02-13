import pytest
from algokit_utils import LogicError

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89GetMetadataSliceArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_short_metadata",
        "mutable_maxed_metadata",
    ],
)
def test_get_slice(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    offset = 0
    size = 4

    metadata_slice = asa_metadata_registry_client.send.arc89_get_metadata_slice(
        args=Arc89GetMetadataSliceArgs(
            asset_id=metadata.asset_id,
            offset=offset,
            size=size,
        ),
    ).abi_return
    assert metadata_slice is not None
    assert bytes(metadata_slice) == metadata.body.raw_bytes[offset : offset + size]


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_slice(
            args=Arc89GetMetadataSliceArgs(
                asset_id=NON_EXISTENT_ASA_ID,
                offset=0,
                size=4,
            ),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_slice(
            args=Arc89GetMetadataSliceArgs(
                asset_id=arc_89_asa,
                offset=0,
                size=4,
            ),
        )


def test_fail_exceeds_page_size(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.EXCEEDS_PAGE_SIZE):
        asa_metadata_registry_client.send.arc89_get_metadata_slice(
            args=Arc89GetMetadataSliceArgs(
                asset_id=mutable_maxed_metadata.asset_id,
                offset=0,
                size=const.PAGE_SIZE + 1,  # Exceeds PAGE_SIZE
            ),
        )


def test_fail_exceeds_metadata_size(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # Try to read beyond the end of metadata
    with pytest.raises(LogicError, match=err.EXCEEDS_METADATA_SIZE):
        asa_metadata_registry_client.send.arc89_get_metadata_slice(
            args=Arc89GetMetadataSliceArgs(
                asset_id=mutable_short_metadata.asset_id,
                offset=mutable_short_metadata.body.size,  # Start at end of metadata
                size=1,  # Try to read 1 byte beyond
            ),
        )
