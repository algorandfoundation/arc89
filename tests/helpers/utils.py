from algokit_utils import SigningAccount, PaymentParams, CommonAppCallParams, AlgoAmount, SendParams
from algosdk.transaction import Transaction

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import \
    AsaMetadataRegistryClient, Arc89CreateMetadataArgs, Arc89ExtraPayloadArgs, \
    Arc89ReplaceMetadataArgs, AsaMetadataRegistryComposer, MbrDelta

from tests.helpers.factories import AssetMetadata


def _append_extra_payload(
    composer: AsaMetadataRegistryComposer,
    asset_manager: SigningAccount,
    metadata: AssetMetadata
) -> None:
    chunks = metadata.chunked_payload()
    for i, chunk in enumerate(chunks[1:], start=1):
        composer.arc89_extra_payload(
            args=Arc89ExtraPayloadArgs(
                asset_id=metadata.asset_id,
                payload=chunk,
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                note=i.to_bytes(8, "big"),
                static_fee=AlgoAmount(algo=0)
            ),
        )


def get_mbr_payment(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    mbr_delta_amount: AlgoAmount,
) -> Transaction:
    return asa_metadata_registry_client.algorand.create_transaction.payment(
        PaymentParams(
            sender=asset_manager.address,
            receiver=asa_metadata_registry_client.app_address,
            amount=mbr_delta_amount,
            static_fee=AlgoAmount(micro_algo=0),
        ),
    )


def create_metadata(
    *,
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_id: int,
    metadata: AssetMetadata,
) -> MbrDelta:
    """
    Create metadata, splitting payload into chunks suitable for ARC-89 extra payload calls.
    """
    creation_mbr_delta = metadata.get_mbr_delta(old_size=None)
    mbr_payment = get_mbr_payment(asa_metadata_registry_client, asset_manager, creation_mbr_delta.amount)

    chunks = metadata.chunked_payload()
    min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee

    create_metadata_composer = asa_metadata_registry_client.new_group()
    create_metadata_composer.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=asset_id,
            flags=metadata.flags,
            metadata_size=metadata.size,
            payload=chunks[0],
            mbr_delta_payment=mbr_payment,
        ),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount(micro_algo=(len(chunks) + 2) * min_fee),
        ),
    )
    _append_extra_payload(create_metadata_composer, asset_manager, metadata)
    asset_create_response = create_metadata_composer.send(
        send_params=SendParams(cover_app_call_inner_transaction_fees=True)
    ).returns[0].value

    return MbrDelta(sign=asset_create_response[0], amount=asset_create_response[1])


def replace_metadata(
    *,
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_id: int,
    new_metadata: AssetMetadata,
    extra_resources: int = 0,
) -> MbrDelta:
    """
    Replace metadata, splitting payload into chunks suitable for ARC-89 extra payload calls.
    """
    chunks = new_metadata.chunked_payload()
    min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee

    replace_metadata_composer = asa_metadata_registry_client.new_group()
    replace_metadata_composer.arc89_replace_metadata(
        args=Arc89ReplaceMetadataArgs(
            asset_id=asset_id,
            metadata_size=new_metadata.size,
            payload=chunks[0],
        ),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount(micro_algo=(len(chunks) + 1) * min_fee),
        ),
    )
    _append_extra_payload(replace_metadata_composer, asset_manager, new_metadata)
    for i in range(extra_resources):
        replace_metadata_composer.extra_resources(
            params=CommonAppCallParams(
                sender=asset_manager.address,
                note=i.to_bytes(8, "big"),
                static_fee=AlgoAmount(micro_algo=min_fee)
            ),
        )
    asset_create_response = replace_metadata_composer.send(
        send_params=SendParams(cover_app_call_inner_transaction_fees=True)
    ).returns[0].value

    return MbrDelta(sign=asset_create_response[0], amount=asset_create_response[1])
