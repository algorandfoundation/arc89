import pytest
from algokit_utils import AssetConfigParams, SigningAccount
from algosdk.constants import ZERO_ADDRESS

from src.asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89IsMetadataImmutableArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


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


# TODO: Test failing conditions
