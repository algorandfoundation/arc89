import pytest
from algokit_utils import AssetConfigParams, LogicError, SigningAccount
from algosdk.constants import ZERO_ADDRESS

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89IsMetadataImmutableArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


def test_immutable_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    is_immutable = asa_metadata_registry_client.send.arc89_is_metadata_immutable(
        args=Arc89IsMetadataImmutableArgs(asset_id=immutable_short_metadata.asset_id),
    ).abi_return
    assert is_immutable


@pytest.mark.skip("FIX algokit-utils: the ASA is destroyed instead of reconfigured")
def test_no_manager(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asa_metadata_registry_client.algorand.send.asset_config(
        params=AssetConfigParams(
            asset_id=mutable_short_metadata.asset_id,
            manager=ZERO_ADDRESS,
            sender=asset_manager.address,
        )
    )
    is_immutable = asa_metadata_registry_client.send.arc89_is_metadata_immutable(
        args=Arc89IsMetadataImmutableArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert is_immutable


def test_mutable_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    is_immutable = asa_metadata_registry_client.send.arc89_is_metadata_immutable(
        args=Arc89IsMetadataImmutableArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert not is_immutable


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_is_metadata_immutable(
            args=Arc89IsMetadataImmutableArgs(asset_id=NON_EXISTENT_ASA_ID),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_is_metadata_immutable(
            args=Arc89IsMetadataImmutableArgs(asset_id=arc_89_asa),
        )
