from collections.abc import Callable

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
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
    Arc89SetImmutableArgs,
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
                note=i.to_bytes(),
                static_fee=AlgoAmount(algo=0),
            ),
        )


def add_extra_resources(composer: AsaMetadataRegistryComposer, count: int = 1) -> None:
    for i in range(count):
        composer.extra_resources(
            params=CommonAppCallParams(
                note=i.to_bytes(),
                static_fee=AlgoAmount(
                    micro_algo=0
                ),  # Don't charge, otherwise breaks min fee calibration
            )
        )


def pages_min_fee(algorand_client: AlgorandClient, metadata: AssetMetadata) -> int:
    """
    Estimate the total minimum fee in microAlgos for operations that scale with
    the number of metadata pages.

    The Algorand protocol charges a minimum fee per transaction. When working
    with ARC-89 metadata, updating or appending metadata may require multiple
    transactions depending on how many pages of metadata need to be processed.

    This helper approximates the total fee as:

        min_fee * (1 + (metadata.total_pages + 1) // 4)

    where `min_fee` is the current suggested minimum fee from the network, and
    `total_pages` is the number of metadata pages. The `1 + ...` accounts for
    a base transaction plus one additional minimum-fee "unit" for each group
    of up to four pages, with `(total_pages + 1) // 4` performing an integer
    division that effectively rounds up to the next group of four pages.

    Args:
        algorand_client: AlgorandClient to use for fetching the current params
        metadata: AssetMetadata whose ``total_pages`` attribute determines how
            many minimum-fee units are required.

    Returns:
        int: The estimated total minimum fee, in microAlgos.
    """
    min_fee = algorand_client.get_suggested_params().min_fee
    return min_fee * (1 + (metadata.total_pages + 1) // 4)


def total_extra_resources(algorand_client: AlgorandClient, metadata: AssetMetadata) -> tuple[int, int]:
    # FIXME: Add extra resources based on page count to avoid opcode budget issues
    #  in populate resources simulation
    extra_count = 0
    if metadata.total_pages > 15:
        # Scale: 1 extra resource per 2 pages, starting from page 16
        extra_count = ((metadata.total_pages - 15) // 2) + 1

    min_fee = algorand_client.get_suggested_params().min_fee
    base_fee = pages_min_fee(algorand_client, metadata)
    # Account for extra resource transactions in total fee
    total_fee = base_fee + (extra_count * min_fee)
    return extra_count, total_fee


def set_flag_and_verify(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
    flag: int,
    check_fn: Callable[[AssetMetadata], bool],
    *,
    reversible: bool = True,
    value: bool | None = None,
) -> None:
    asset_id = metadata.asset_id
    if reversible:
        assert value is not None, "Flag value must be provided when reversible=True"
        set_reversible_flag(
            asa_metadata_registry_client, asset_manager, metadata, flag, value=value
        )
        expected_value = value
    else:
        # Irreversible flags are always set to True
        set_irreversible_flag(
            asa_metadata_registry_client, asset_manager, metadata, flag
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
            reversible_flags=metadata.reversible_flags,
            irreversible_flags=metadata.irreversible_flags,
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
                static_fee=AlgoAmount(
                    micro_algo=(len(chunks) + extra_resources + 1) * min_fee
                ),
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
    add_extra_resources(replace_metadata_composer, extra_resources)
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
            static_fee=AlgoAmount(micro_algo=(2 + extra_resources) * min_fee),
        ),
    ),
    add_extra_resources(delete_metadata_composer, extra_resources)
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


def set_reversible_flag(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
    flag: int,
    *,
    value: bool,
) -> None:
    extra_count, total_fee = total_extra_resources(asa_metadata_registry_client.algorand, metadata)
    composer = asa_metadata_registry_client.new_group()
    composer.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=metadata.asset_id, flag=flag, value=value
        ),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount.from_micro_algo(total_fee),
        ),
    )
    if extra_count > 0:
        add_extra_resources(composer, extra_count)
    composer.send()


def set_irreversible_flag(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
    flag: int,
) -> None:
    extra_count, total_fee = total_extra_resources(asa_metadata_registry_client.algorand, metadata)
    composer = asa_metadata_registry_client.new_group()
    composer.arc89_set_irreversible_flag(
        args=Arc89SetIrreversibleFlagArgs(asset_id=metadata.asset_id, flag=flag),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount.from_micro_algo(total_fee),
        ),
    )
    if extra_count > 0:
        add_extra_resources(composer, extra_count)
    composer.send()


def set_immutable(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
) -> None:
    extra_count, total_fee = total_extra_resources(asa_metadata_registry_client.algorand, metadata)
    composer = asa_metadata_registry_client.new_group()
    composer.arc89_set_immutable(
        args=Arc89SetImmutableArgs(asset_id=metadata.asset_id),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount.from_micro_algo(total_fee),
        ),
    )
    if extra_count > 0:
        add_extra_resources(composer, extra_count)
    composer.send()
