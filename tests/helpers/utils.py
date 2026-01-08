from collections.abc import Callable
from typing import cast

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    CommonAppCallParams,
    PaymentParams,
    SendAtomicTransactionComposerResults,
    SendParams,
    SigningAccount,
)
from algosdk.transaction import Transaction

from asa_metadata_registry import (
    AssetMetadata,
    AssetMetadataBox,
    MetadataBody,
    MetadataFlags,
    get_default_registry_params,
)
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89CreateMetadataArgs,
    Arc89DeleteMetadataArgs,
    Arc89ExtraPayloadArgs,
    Arc89GetMetadataPaginationArgs,
    Arc89ReplaceMetadataArgs,
    Arc89ReplaceMetadataLargerArgs,
    Arc89ReplaceMetadataSliceArgs,
    Arc89SetImmutableArgs,
    Arc89SetIrreversibleFlagArgs,
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
    AsaMetadataRegistryComposer,
    MbrDelta,
)

# =============================================================================
# Test Constants
# =============================================================================

# Non-existent asset ID for testing ASA_NOT_EXIST errors
NON_EXISTENT_ASA_ID = 420

# =============================================================================
# Common Helper Functions
# =============================================================================


def _get_min_fee(client: AsaMetadataRegistryClient) -> int:
    """Get the minimum fee from the client's suggested params."""
    return int(client.algorand.get_suggested_params().min_fee)


def _get_chunks_and_fee(
    client: AsaMetadataRegistryClient,
    metadata: AssetMetadata,
    extra_txns: int = 0,
) -> tuple[list[bytes], int]:
    """Get metadata chunks and calculate the total fee.

    Args:
        client: The ASA Metadata Registry Client
        metadata: The metadata to chunk
        extra_txns: Additional transactions to include in fee calculation

    Returns:
        Tuple of (chunks list, total fee in microAlgos)
    """
    min_fee = _get_min_fee(client)
    chunks = metadata.body.chunked_payload()
    return chunks, (len(chunks) + extra_txns) * min_fee


def _extract_mbr_delta_from_response(
    response: SendAtomicTransactionComposerResults,
) -> MbrDelta:
    """Extract MbrDelta from a composer send response."""
    result = cast(tuple[int, int], response.returns[0].value)
    return MbrDelta(sign=result[0], amount=result[1])


def _create_mbr_payment_txn(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    amount: int,
    *,
    receiver_override: str | None = None,
    amount_override: int | None = None,
) -> Transaction:
    """Create an MBR payment transaction with optional overrides for testing.

    Args:
        client: The ASA Metadata Registry Client
        sender: The sender of the payment
        amount: The default amount in microAlgos
        receiver_override: Override the receiver address (for testing error cases)
        amount_override: Override the amount (for testing error cases)

    Returns:
        Payment transaction
    """
    return client.algorand.create_transaction.payment(
        PaymentParams(
            sender=sender.address,
            receiver=(
                receiver_override
                if receiver_override is not None
                else client.app_address
            ),
            amount=AlgoAmount(
                micro_algo=(amount_override if amount_override is not None else amount)
            ),
            static_fee=AlgoAmount(micro_algo=0),
        ),
    )


def _execute_flag_operation(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
    setup_composer: Callable[[AsaMetadataRegistryComposer, AlgoAmount], None],
) -> None:
    """Execute a flag operation with proper fee and extra resources handling.

    Args:
        asa_metadata_registry_client: The ASA Metadata Registry Client
        asset_manager: The asset manager account
        metadata: The metadata being modified
        setup_composer: Function that sets up the specific operation on the composer
    """
    extra_count, total_fee = total_extra_resources(
        asa_metadata_registry_client.algorand, metadata
    )
    composer = asa_metadata_registry_client.new_group()
    setup_composer(composer, AlgoAmount.from_micro_algo(total_fee))
    if extra_count > 0:
        add_extra_resources(composer, extra_count)
    composer.send()


def _append_extra_payload(
    composer: AsaMetadataRegistryComposer,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
) -> None:
    chunks = metadata.body.chunked_payload()
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
    min_fee: int = algorand_client.get_suggested_params().min_fee
    total_pages = metadata.body.total_pages()
    return min_fee * (1 + (total_pages + 1) // 4)


def total_extra_resources(
    algorand_client: AlgorandClient, metadata: AssetMetadata
) -> tuple[int, int]:
    # FIXME: Add extra resources based on page count to avoid opcode budget issues
    #  in populate resources simulation
    total_pages = metadata.body.total_pages()
    extra_count = 0
    if total_pages > 15:
        # Scale: 1 extra resource per 2 pages, starting from page 16
        extra_count = ((total_pages - 15) // 2) + 1

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

    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None, f"Metadata box not found for asset {asset_id}"
    parsed_box = AssetMetadataBox.parse(asset_id=asset_id, value=box_value)
    post_set = AssetMetadata(
        asset_id=asset_id,
        body=parsed_box.body,
        flags=parsed_box.header.flags,
        deprecated_by=parsed_box.header.deprecated_by,
    )
    assert check_fn(post_set) == expected_value


def get_mbr_delta_payment(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    mbr_delta_amount: AlgoAmount,
    *,
    receiver_override: str | None = None,
    amount_override: int | None = None,
) -> Transaction:
    """Create an MBR payment transaction with optional overrides for testing error cases."""
    return asa_metadata_registry_client.algorand.create_transaction.payment(
        PaymentParams(
            sender=asset_manager.address,
            receiver=(
                receiver_override
                if receiver_override is not None
                else asa_metadata_registry_client.app_address
            ),
            amount=AlgoAmount(
                micro_algo=(
                    amount_override
                    if amount_override is not None
                    else mbr_delta_amount.micro_algo
                )
            ),
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
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=creation_mbr_delta.amount),
    )

    chunks, fee = _get_chunks_and_fee(
        asa_metadata_registry_client, metadata, extra_txns=2
    )

    create_metadata_composer = asa_metadata_registry_client.new_group()
    create_metadata_composer.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=asset_id,
            reversible_flags=metadata.flags.reversible_byte,
            irreversible_flags=metadata.flags.irreversible_byte,
            metadata_size=metadata.body.size,
            payload=chunks[0],
            mbr_delta_payment=mbr_payment,
        ),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount(micro_algo=fee),
        ),
    )
    _append_extra_payload(create_metadata_composer, asset_manager, metadata)
    response = create_metadata_composer.send(
        send_params=SendParams(cover_app_call_inner_transaction_fees=True)
    )

    return _extract_mbr_delta_from_response(response)


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
    chunks, base_fee = _get_chunks_and_fee(
        asa_metadata_registry_client, new_metadata, extra_txns=1
    )
    min_fee = _get_min_fee(asa_metadata_registry_client)
    replace_metadata_composer = asa_metadata_registry_client.new_group()

    pagination_result = asa_metadata_registry_client.send.arc89_get_metadata_pagination(
        args=Arc89GetMetadataPaginationArgs(asset_id=asset_id),
    ).abi_return
    assert (
        pagination_result is not None
    ), f"Failed to get metadata pagination for asset {asset_id}"
    current_metadata_size = pagination_result.metadata_size
    if new_metadata.body.size <= current_metadata_size:
        replace_metadata_composer.arc89_replace_metadata(
            args=Arc89ReplaceMetadataArgs(
                asset_id=asset_id,
                metadata_size=new_metadata.body.size,
                payload=chunks[0],
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(
                    micro_algo=base_fee + (extra_resources * min_fee)
                ),
            ),
        )
    else:
        mbr_delta = new_metadata.get_mbr_delta(old_size=current_metadata_size)
        mbr_payment = get_mbr_delta_payment(
            asa_metadata_registry_client,
            asset_manager,
            AlgoAmount(micro_algo=mbr_delta.amount),
        )
        replace_metadata_composer.arc89_replace_metadata_larger(
            args=Arc89ReplaceMetadataLargerArgs(
                asset_id=asset_id,
                metadata_size=new_metadata.body.size,
                payload=chunks[0],
                mbr_delta_payment=mbr_payment,
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=base_fee),
            ),
        )
    _append_extra_payload(replace_metadata_composer, asset_manager, new_metadata)
    add_extra_resources(replace_metadata_composer, extra_resources)
    response = replace_metadata_composer.send(
        send_params=SendParams(cover_app_call_inner_transaction_fees=True)
    )

    return _extract_mbr_delta_from_response(response)


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
    min_fee = _get_min_fee(asa_metadata_registry_client)
    delete_metadata_composer = asa_metadata_registry_client.new_group()

    delete_metadata_composer.arc89_delete_metadata(
        args=Arc89DeleteMetadataArgs(asset_id=asset_id),
        params=CommonAppCallParams(
            sender=caller.address,
            static_fee=AlgoAmount(micro_algo=(2 + extra_resources) * min_fee),
        ),
    ),
    add_extra_resources(delete_metadata_composer, extra_resources)
    response = delete_metadata_composer.send(
        send_params=SendParams(cover_app_call_inner_transaction_fees=True)
    )

    return _extract_mbr_delta_from_response(response)


def set_reversible_flag(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
    flag: int,
    *,
    value: bool,
) -> None:
    def setup(composer: AsaMetadataRegistryComposer, fee: AlgoAmount) -> None:
        composer.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=metadata.asset_id, flag=flag, value=value
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=fee,
            ),
        )

    _execute_flag_operation(
        asa_metadata_registry_client, asset_manager, metadata, setup
    )


def set_irreversible_flag(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
    flag: int,
) -> None:
    def setup(composer: AsaMetadataRegistryComposer, fee: AlgoAmount) -> None:
        composer.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(asset_id=metadata.asset_id, flag=flag),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=fee,
            ),
        )

    _execute_flag_operation(
        asa_metadata_registry_client, asset_manager, metadata, setup
    )


def set_immutable(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    metadata: AssetMetadata,
) -> None:
    def setup(composer: AsaMetadataRegistryComposer, fee: AlgoAmount) -> None:
        composer.arc89_set_immutable(
            args=Arc89SetImmutableArgs(asset_id=metadata.asset_id),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=fee,
            ),
        )

    _execute_flag_operation(
        asa_metadata_registry_client, asset_manager, metadata, setup
    )


def create_metadata_with_page_count(
    asset_id: int, page_count: int, filler: bytes
) -> AssetMetadata:
    """
    Create metadata with a specific number of pages.

    Args:
        asset_id: The asset ID
        page_count: The desired number of pages (0 to MAX_PAGES)
        filler: A byte pattern to fill the metadata with

    Returns:
        AssetMetadata instance with the specified page count
    """
    if page_count < 0 or page_count > const.MAX_PAGES:
        raise ValueError(f"page_count must be between 0 and {const.MAX_PAGES}")

    if page_count == 0:
        # Empty metadata
        size = 0
    elif page_count == 1:
        size = 1 * const.PAGE_SIZE
    else:
        # Minimum size to trigger N pages: (N-1) * PAGE_SIZE + 1
        size = (page_count - 1) * const.PAGE_SIZE + 1

    # Create metadata with the filler bytes repeated to the desired size
    assert len(filler) >= 1, "Filler must be at least 1 byte"
    metadata_bytes = filler * size

    params = get_default_registry_params()
    metadata = AssetMetadata(
        asset_id=asset_id,
        body=MetadataBody(raw_bytes=metadata_bytes),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )
    assert (
        metadata.body.total_pages(params) == page_count
    ), f"Expected {page_count} pages, got {metadata.body.total_pages(params)}"

    return metadata


def get_create_metadata_fee(
    client: AsaMetadataRegistryClient,
    metadata: AssetMetadata,
) -> int:
    """Calculate the fee for create_metadata call."""
    chunks = metadata.body.chunked_payload()
    return (len(chunks) + 2) * _get_min_fee(client)


def build_create_metadata_composer(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    asset_id: int,
    metadata: AssetMetadata,
    mbr_payment: Transaction,
    *,
    metadata_size_override: int | None = None,
    payload_override: bytes | None = None,
) -> AsaMetadataRegistryComposer:
    """Build a composer for arc89_create_metadata with common parameters."""
    chunks = metadata.body.chunked_payload()
    fee = get_create_metadata_fee(client, metadata)

    composer = client.new_group()
    composer.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=asset_id,
            reversible_flags=metadata.flags.reversible_byte,
            irreversible_flags=metadata.flags.irreversible_byte,
            metadata_size=(
                metadata_size_override
                if metadata_size_override is not None
                else metadata.body.size
            ),
            payload=payload_override if payload_override is not None else chunks[0],
            mbr_delta_payment=mbr_payment,
        ),
        params=CommonAppCallParams(
            sender=sender.address,
            static_fee=AlgoAmount(micro_algo=fee),
        ),
    )
    return composer


def create_mbr_payment(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    metadata: AssetMetadata,
    *,
    receiver_override: str | None = None,
    amount_override: int | None = None,
) -> Transaction:
    """Create an MBR payment transaction for metadata creation with optional overrides."""
    creation_mbr_delta = metadata.get_mbr_delta(old_size=None)
    return get_mbr_delta_payment(
        client,
        sender,
        AlgoAmount(micro_algo=creation_mbr_delta.amount),
        receiver_override=receiver_override,
        amount_override=amount_override,
    )


def build_replace_metadata_composer(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    asset_id: int,
    metadata: AssetMetadata,
    *,
    metadata_size_override: int | None = None,
    payload_override: bytes | None = None,
) -> AsaMetadataRegistryComposer:
    """Build a composer for arc89_replace_metadata with common parameters."""
    chunks = metadata.body.chunked_payload()
    min_fee = _get_min_fee(client)

    composer = client.new_group()
    composer.arc89_replace_metadata(
        args=Arc89ReplaceMetadataArgs(
            asset_id=asset_id,
            metadata_size=(
                metadata_size_override
                if metadata_size_override is not None
                else metadata.body.size
            ),
            payload=payload_override if payload_override is not None else chunks[0],
        ),
        params=CommonAppCallParams(
            sender=sender.address,
            static_fee=AlgoAmount(micro_algo=(len(chunks) + 1) * min_fee),
        ),
    )
    return composer


def build_replace_metadata_larger_composer(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    asset_id: int,
    metadata: AssetMetadata,
    mbr_payment: Transaction,
    *,
    metadata_size_override: int | None = None,
    payload_override: bytes | None = None,
) -> AsaMetadataRegistryComposer:
    """Build a composer for arc89_replace_metadata_larger with common parameters."""
    chunks = metadata.body.chunked_payload()
    min_fee = _get_min_fee(client)

    composer = client.new_group()
    composer.arc89_replace_metadata_larger(
        args=Arc89ReplaceMetadataLargerArgs(
            asset_id=asset_id,
            metadata_size=(
                metadata_size_override
                if metadata_size_override is not None
                else metadata.body.size
            ),
            payload=payload_override if payload_override is not None else chunks[0],
            mbr_delta_payment=mbr_payment,
        ),
        params=CommonAppCallParams(
            sender=sender.address,
            static_fee=AlgoAmount(micro_algo=(len(chunks) + 1) * min_fee),
        ),
    )
    return composer


def build_replace_metadata_slice_composer(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    asset_id: int,
    offset: int,
    payload: bytes,
) -> AsaMetadataRegistryComposer:
    """Build a composer for arc89_replace_metadata_slice with common parameters."""
    composer = client.new_group()
    composer.arc89_replace_metadata_slice(
        args=Arc89ReplaceMetadataSliceArgs(
            asset_id=asset_id,
            offset=offset,
            payload=payload,
        ),
        params=CommonAppCallParams(sender=sender.address),
    )
    return composer
