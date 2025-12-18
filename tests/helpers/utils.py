from collections.abc import Callable

from algokit_utils import (
    AlgoAmount,
    CommonAppCallParams,
    PaymentParams,
    SendParams,
    SigningAccount,
)
from algosdk.transaction import Transaction

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89CreateMetadataArgs,
    Arc89DeleteMetadataArgs,
    Arc89ExtraPayloadArgs,
    Arc89GetMetadataPaginationArgs,
    Arc89ReplaceMetadataArgs,
    Arc89ReplaceMetadataLargerArgs,
    Arc89SetIrreversibleFlagArgs,
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
    AsaMetadataRegistryComposer,
    MbrDelta,
)
from tests.helpers.factories import AssetMetadata


def _append_extra_payload(
    composer: AsaMetadataRegistryComposer,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
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
                static_fee=AlgoAmount(algo=0),
            ),
        )


def set_flag_and_verify(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    asset_id: int,
    flag: int,
    check_fn: Callable[[AssetMetadata], bool],
    *,
    reversible: bool = True,
    value: bool | None = None,
) -> None:
    if reversible:
        assert value is not None, "Flag value must be provided when reversible=True"
        asa_metadata_registry_client.send.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=asset_id,
                flag=flag,
                value=value,
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )
        expected_value = value
    else:
        # Irreversible flags are always set to True
        asa_metadata_registry_client.send.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(
                asset_id=asset_id,
                flag=flag,
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )
        expected_value = True

    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert check_fn(post_set) == expected_value


def get_mbr_delta_payment(
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

    Args:
        asset_manager: The Manager of the ASA to create metadata for
        asa_metadata_registry_client: The ASA Metadata Registry Client
        asset_id: The ASA ID to create metadata for
        metadata: The metadata payload to set

    Returns:
        MBR Delta
    """
    creation_mbr_delta = metadata.get_mbr_delta(old_size=None)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client, asset_manager, creation_mbr_delta.amount
    )

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
    create_metadata_response = (
        create_metadata_composer.send(
            send_params=SendParams(cover_app_call_inner_transaction_fees=True)
        )
        .returns[0]
        .value
    )

    return MbrDelta(
        sign=create_metadata_response[0], amount=create_metadata_response[1]
    )


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

    Args:
        asset_manager: The Manager of the ASA to replace metadata for
        asa_metadata_registry_client: The ASA Metadata Registry Client
        asset_id: The ASA ID to replace metadata for
        new_metadata: The new metadata payload to set
        extra_resources (Optional): Extra App Call for additional AVM resources

    Returns:
        MBR Delta
    """
    chunks = new_metadata.chunked_payload()
    min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee
    replace_metadata_composer = asa_metadata_registry_client.new_group()

    current_metadata_size = (
        asa_metadata_registry_client.send.arc89_get_metadata_pagination(
            args=Arc89GetMetadataPaginationArgs(asset_id=asset_id),
        ).abi_return.metadata_size
    )
    if new_metadata.size <= current_metadata_size:
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
    else:
        mbr_payment = get_mbr_delta_payment(
            asa_metadata_registry_client,
            asset_manager,
            new_metadata.get_mbr_delta(current_metadata_size).amount,
        )
        replace_metadata_composer.arc89_replace_metadata_larger(
            args=Arc89ReplaceMetadataLargerArgs(
                asset_id=asset_id,
                metadata_size=new_metadata.size,
                payload=chunks[0],
                mbr_delta_payment=mbr_payment,
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
                static_fee=AlgoAmount(micro_algo=min_fee),
            ),
        )
    replace_metadata_response = (
        replace_metadata_composer.send(
            send_params=SendParams(cover_app_call_inner_transaction_fees=True)
        )
        .returns[0]
        .value
    )

    return MbrDelta(
        sign=replace_metadata_response[0], amount=replace_metadata_response[1]
    )


def delete_metadata(
    *,
    caller: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_id: int,
    extra_resources: int = 0,
) -> MbrDelta:
    """
    Delete metadata for existing or non-existent ASA.

    Args:
        caller: Who deletes the metadata (must be the ASA Manager if ASA exists)
        asa_metadata_registry_client: The ASA Metadata Registry Client
        asset_id: The ASA ID to delete metadata for
        extra_resources (Optional): Extra App Call for additional AVM resources

    Returns:
        MBR Delta
    """
    min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee
    delete_metadata_composer = asa_metadata_registry_client.new_group()

    delete_metadata_composer.arc89_delete_metadata(
        args=Arc89DeleteMetadataArgs(asset_id=asset_id),
        params=CommonAppCallParams(
            sender=caller.address,
            static_fee=AlgoAmount(micro_algo=2 * min_fee),
        ),
    ),
    for i in range(extra_resources):
        delete_metadata_composer.extra_resources(
            params=CommonAppCallParams(
                sender=caller.address,
                note=i.to_bytes(8, "big"),
                static_fee=AlgoAmount(micro_algo=min_fee),
            ),
        )
    delete_metadata_response = (
        delete_metadata_composer.send(
            send_params=SendParams(cover_app_call_inner_transaction_fees=True)
        )
        .returns[0]
        .value
    )

    return MbrDelta(
        sign=delete_metadata_response[0], amount=delete_metadata_response[1]
    )
