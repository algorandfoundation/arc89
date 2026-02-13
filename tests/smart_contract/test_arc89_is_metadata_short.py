import pytest
from algokit_utils import LogicError

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89IsMetadataShortArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


def test_short_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    is_short = asa_metadata_registry_client.send.arc89_is_metadata_short(
        args=Arc89IsMetadataShortArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert is_short is not None
    assert is_short.flag


def test_long_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    is_short = asa_metadata_registry_client.send.arc89_is_metadata_short(
        args=Arc89IsMetadataShortArgs(asset_id=mutable_maxed_metadata.asset_id),
    ).abi_return
    assert is_short is not None
    assert not is_short.flag


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_is_metadata_short(
            args=Arc89IsMetadataShortArgs(asset_id=NON_EXISTENT_ASA_ID),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_is_metadata_short(
            args=Arc89IsMetadataShortArgs(asset_id=arc_89_asa),
        )
