from algokit_utils import SigningAccount, PaymentParams, CommonAppCallParams, AlgoAmount, SendParams

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import \
    AsaMetadataRegistryClient, Arc89CreateMetadataArgs, Arc89ExtraPayloadArgs, MbrDelta

from tests.helpers.factories import AssetMetadata


def create_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata: AssetMetadata,
) -> MbrDelta:
    """
    Create large metadata payload split into chunks suitable for ARC-89 extra payload calls.
    """
    creation_mbr_delta = metadata.get_mbr_delta(old_size=None)
    mbr_payment = asa_metadata_registry_client.algorand.create_transaction.payment(
        PaymentParams(
            sender=asset_manager.address,
            receiver=asa_metadata_registry_client.app_address,
            amount=creation_mbr_delta.amount,
            static_fee=AlgoAmount(micro_algo=0),
        ),
    )

    chunks = metadata.chunked_payload()
    min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee

    create_metadata_composer = asa_metadata_registry_client.new_group()
    create_metadata_composer.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=metadata.asset_id,
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
    for i in range(1, len(chunks)):
        create_metadata_composer.arc89_extra_payload(
            args=Arc89ExtraPayloadArgs(
                asset_id=metadata.asset_id,
                payload=chunks[i],
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                note=i.to_bytes(),
                static_fee=AlgoAmount(algo=0)
            ),
        )

    asset_create_response = create_metadata_composer.send(
        send_params=SendParams(cover_app_call_inner_transaction_fees=True)
    ).returns[0].value

    return MbrDelta(sign=asset_create_response[0], amount=asset_create_response[1])
