import pytest
from algokit_utils import LogicError

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89GetMetadataHeaderHashArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


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


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_header_hash(
            args=Arc89GetMetadataHeaderHashArgs(asset_id=NON_EXISTENT_ASA_ID),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_header_hash(
            args=Arc89GetMetadataHeaderHashArgs(asset_id=arc_89_asa),
        )
