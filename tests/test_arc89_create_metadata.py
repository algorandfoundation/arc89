from algokit_utils import SigningAccount, PaymentParams, CommonAppCallParams, \
    SendParams, AlgoAmount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import \
    AsaMetadataRegistryClient, Arc89CreateMetadataArgs

from tests.helpers.factories import AssetMetadata
from tests.helpers.utils import create_metadata


def test_empty_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    empty_metadata: AssetMetadata,
) -> None:
    creation_mbr_delta = empty_metadata.get_mbr_delta(old_size=None)
    mbr_payment = asa_metadata_registry_client.algorand.create_transaction.payment(
        PaymentParams(
            sender=asset_manager.address,
            receiver=asa_metadata_registry_client.app_address,
            amount=creation_mbr_delta.amount
        )
    )

    mbr_delta = asa_metadata_registry_client.send.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=empty_metadata.asset_id,
            flags=empty_metadata.flags,
            metadata_size=empty_metadata.size,
            payload=empty_metadata.metadata_bytes,
            mbr_delta_payment=mbr_payment,
        ),
        params=CommonAppCallParams(sender=asset_manager.address)
    ).abi_return
    assert mbr_delta.amount == creation_mbr_delta.amount.micro_algo
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_short_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    short_metadata: AssetMetadata,
) -> None:
    creation_mbr_delta = short_metadata.get_mbr_delta(old_size=None)
    mbr_payment = asa_metadata_registry_client.algorand.create_transaction.payment(
        PaymentParams(
            sender=asset_manager.address,
            receiver=asa_metadata_registry_client.app_address,
            amount=creation_mbr_delta.amount
        )
    )

    mbr_delta = asa_metadata_registry_client.send.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=short_metadata.asset_id,
            flags=short_metadata.flags,
            metadata_size=short_metadata.size,
            payload=short_metadata.metadata_bytes,
            mbr_delta_payment=mbr_payment,
        ),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            max_fee=AlgoAmount(algo=1)
        ),
        send_params=SendParams(cover_app_call_inner_transaction_fees=True),
    ).abi_return
    assert mbr_delta.amount == creation_mbr_delta.amount.micro_algo
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_maxed_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    maxed_metadata: AssetMetadata,
) -> None:
    creation_mbr_delta = maxed_metadata.get_mbr_delta(old_size=None)
    mbr_delta = create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        metadata=maxed_metadata,
    )
    assert mbr_delta.amount == creation_mbr_delta.amount.micro_algo
    # TODO: Verify Asset Metadata Box contents matches fixture data
