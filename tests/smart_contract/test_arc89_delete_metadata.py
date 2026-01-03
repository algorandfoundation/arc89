from algokit_utils import AssetDestroyParams, SigningAccount

from smart_contracts.asa_metadata_registry.enums import MBR_DELTA_NEG
from src._generated.asa_metadata_registry_client import (
    Arc89CheckMetadataExistsArgs,
    AsaMetadataRegistryClient,
)
from src.models import AssetMetadata
from tests.helpers.utils import delete_metadata


def test_delete_metadata_existing_asa(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    pre_delete_balance = asa_metadata_registry_client.algorand.account.get_information(
        asset_manager.address
    ).amount.micro_algo
    deletion_mbr_delta = mutable_maxed_metadata.get_delete_mbr_delta()
    mbr_delta = delete_metadata(
        caller=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_maxed_metadata.asset_id,
        extra_resources=1,
    )
    post_delete_balance = asa_metadata_registry_client.algorand.account.get_information(
        asset_manager.address
    ).amount.micro_algo
    assert post_delete_balance > pre_delete_balance
    assert -mbr_delta.amount == deletion_mbr_delta.signed_amount
    assert mbr_delta.amount == deletion_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NEG

    metadata_existence = asa_metadata_registry_client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=mutable_maxed_metadata.asset_id),
    ).abi_return
    assert metadata_existence is not None
    assert metadata_existence.asa_exists
    assert not metadata_existence.metadata_exists


def test_delete_metadata_nonexistent_asa(
    asset_manager: SigningAccount,
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    asa_metadata_registry_client.algorand.send.asset_destroy(
        params=AssetDestroyParams(
            asset_id=mutable_maxed_metadata.asset_id, sender=asset_manager.address
        )
    )

    pre_delete_balance = asa_metadata_registry_client.algorand.account.get_information(
        untrusted_account.address
    ).amount.micro_algo
    deletion_mbr_delta = mutable_maxed_metadata.get_delete_mbr_delta()
    mbr_delta = delete_metadata(
        caller=untrusted_account,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_maxed_metadata.asset_id,
        extra_resources=1,
    )
    post_delete_balance = asa_metadata_registry_client.algorand.account.get_information(
        untrusted_account.address
    ).amount.micro_algo
    assert post_delete_balance > pre_delete_balance
    assert -mbr_delta.amount == deletion_mbr_delta.signed_amount
    assert mbr_delta.amount == deletion_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NEG

    metadata_existence = asa_metadata_registry_client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=mutable_maxed_metadata.asset_id),
    ).abi_return
    assert metadata_existence is not None
    assert not metadata_existence.asa_exists
    assert not metadata_existence.metadata_exists


# TODO: Test failing conditions
