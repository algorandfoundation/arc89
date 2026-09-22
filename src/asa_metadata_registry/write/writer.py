from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from algokit_utils import (
    AlgoAmount,
    AssetInformation,
    CommonAppCallParams,
    PaymentParams,
    SendAtomicTransactionComposerResults,
    SendParams,
    SigningAccount,
)

from .. import constants as const
from .. import flags
from ..errors import (
    AsaNotFoundError,
    InvalidFlagIndexError,
    InvalidSliceError,
    MetadataNotFoundError,
    MissingAppClientError,
)
from ..generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
    AsaMetadataRegistryComposer,
)
from ..models import AssetMetadata, AssetMetadataBox, MbrDelta, RegistryParameters
from ..read.avm import AsaMetadataRegistryAvmRead, SimulateOptions
from ..validation import (
    ARC3_PROPERTIES_FLAG_TO_KEY,
    decode_metadata_json,
    validate_arc3_properties,
    validate_arc3_schema,
    validate_arc3_values,
)

_APP_ARGS_FREE_SIZE = 2048
_APP_ARG_BYTE_SURCHARGE_FACTOR = 100  # millionths of the min fee
_FEE_FACTOR_SCALE = 1_000_000

_ARC89_CREATE_METADATA_FIXED_SIZE = (
    const.ARC4_METHOD_SELECTOR_SIZE
    + const.UINT64_SIZE
    + const.BYTE_SIZE
    + const.BYTE_SIZE
    + const.UINT16_SIZE
    + const.ARC4_DYNAMIC_LENGTH_SIZE
)
_ARC89_EXTRA_PAYLOAD_FIXED_SIZE = (
    const.ARC4_METHOD_SELECTOR_SIZE + const.UINT64_SIZE + const.ARC4_DYNAMIC_LENGTH_SIZE
)
_ARC89_REPLACE_METADATA_SLICE_FIXED_SIZE = (
    const.ARC4_METHOD_SELECTOR_SIZE
    + const.UINT64_SIZE
    + const.UINT16_SIZE
    + const.ARC4_DYNAMIC_LENGTH_SIZE
)


_BOX_REFERENCE_BYTES = 2048  # Box I/O budget per box reference (consensus v41)
_BOX_REFERENCES_PER_APP_CALL = 8


def _chunks_for_create(
    metadata: AssetMetadata, params: RegistryParameters | None = None
) -> list[bytes]:
    return metadata.body.chunked_payload(params=params)


def _chunks_for_replace(
    metadata: AssetMetadata, params: RegistryParameters | None = None
) -> list[bytes]:
    return metadata.body.chunked_payload(params=params)


def _box_io_extra_resources(box_size: int, *, other_app_calls: int = 0) -> int:
    """
    `extra_resources` calls needed to cover the Box I/O budget of a `box_size` bytes box.

    The head call spends one reference slot on the asset (seven box references left);
    every other app call in the group (extra payloads, extra resources) adds eight.
    """
    head_capacity = (_BOX_REFERENCES_PER_APP_CALL - 1) * _BOX_REFERENCE_BYTES
    call_capacity = _BOX_REFERENCES_PER_APP_CALL * _BOX_REFERENCE_BYTES
    needed_calls = max(0, -(-(box_size - head_capacity) // call_capacity))
    return max(0, needed_calls - other_app_calls)


def _hash_budget_txns(total_pages: int) -> int:
    """Opcode budget inner transactions to recompute the Metadata Hash over `total_pages`."""
    # Calibrated on-chain: the first at two pages, then one every five pages.
    return (total_pages + 3) // 5


def _chunks_for_slice(payload: bytes, max_size: int) -> list[bytes]:
    if max_size <= 0:
        raise ValueError("max_size must be > 0")
    if payload == b"":
        return [b""]
    return [payload[i : i + max_size] for i in range(0, len(payload), max_size)]


def _app_args_surcharge_fee(min_fee: int, app_args_total_sizes: Sequence[int]) -> int:
    """Return the pooled protocol surcharge for app args above 2,048 bytes."""
    excess_bytes = sum(
        max(0, size - _APP_ARGS_FREE_SIZE) for size in app_args_total_sizes
    )
    numerator = min_fee * excess_bytes * _APP_ARG_BYTE_SURCHARGE_FACTOR
    return (numerator + _FEE_FACTOR_SCALE - 1) // _FEE_FACTOR_SCALE


def _append_extra_payload(
    composer: AsaMetadataRegistryComposer,
    *,
    asset_id: int,
    chunks: Sequence[bytes],
    sender: str,
) -> None:
    """
    Append `arc89_extra_payload` calls for chunks[1:].
    """
    for i, chunk in enumerate(chunks[1:]):
        composer.arc89_extra_payload(
            args=(asset_id, chunk),
            params=CommonAppCallParams(
                sender=sender,
                note=i.to_bytes(8, "big", signed=False),
                static_fee=AlgoAmount(micro_algo=0),
            ),
        )


def _append_extra_resources(
    composer: AsaMetadataRegistryComposer, *, count: int, sender: str
) -> None:
    """
    Append `extra_resources` calls to increase resource budget.

    ARC-89 includes this utility method to make large read/write groups easier to simulate/send.
    """
    if count <= 0:
        return

    for i in range(count):
        composer.extra_resources(
            params=CommonAppCallParams(
                sender=sender,
                note=i.to_bytes(8, "big", signed=False),
                static_fee=AlgoAmount(micro_algo=0),
            )
        )


def _parse_metadata_box(
    client: AsaMetadataRegistryClient, asset_id: int
) -> AssetMetadataBox | None:
    """Read and parse the metadata box for `asset_id`, or return None if not found."""
    box_value = client.state.box.asset_metadata.get_value(asset_id)
    return (
        AssetMetadataBox.parse(asset_id=asset_id, value=box_value)
        if box_value is not None
        else None
    )


def _get_asa_params(
    client: AsaMetadataRegistryClient, asset_id: int
) -> AssetInformation:
    """Raise AsaNotFoundError if the ASA does not exist on-chain."""
    try:
        asa_params = client.algorand.asset.get_by_id(asset_id)
    # TODO: Use less general exception when/if AlgoKit Utils exposes Algod's errors.
    except Exception as ex:
        msg = str(ex).lower()
        if "not exist" in msg:
            raise AsaNotFoundError(f"Asset {asset_id} does not exist.") from ex
        raise
    return asa_params


@dataclass(frozen=True, slots=True)
class WriteOptions:
    """
    Controls how ARC-89 write groups are built and sent.

    Notes:
    - Algorand supports *fee pooling* in groups; this SDK sets fee=0 on most txns
      and pools fees on the first app call via `static_fee`.
    - `fee_padding_txns` adds extra min-fee units to the fee pool as a safety margin
      to cover opcode budget inner transaction (related to metadata total pages).
    """

    extra_resources: int = 0
    fee_padding_txns: int = 0
    cover_app_call_inner_transaction_fees: bool = True
    populate_app_call_resources: bool = True


@dataclass(slots=True)
class AsaMetadataRegistryWrite:
    """
    Write API for ARC-89.

    This wraps the generated AlgoKit AppClient to:
    - split metadata into payload chunks
    - build atomic groups (create/replace/delete + extra payload)
    - optionally simulate before sending
    """

    client: AsaMetadataRegistryClient
    params: RegistryParameters | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            raise MissingAppClientError(
                "Write module requires a generated AsaMetadataRegistryClient"
            )

    def _params(self) -> RegistryParameters:
        if self.params is not None:
            return self.params
        # Prefer on-chain registry parameters (simulate).
        p = AsaMetadataRegistryAvmRead(
            self.client
        ).arc89_get_metadata_registry_parameters()
        return p

    def _box_resources(self, asset_id: int, *, hashing: bool) -> tuple[int, int]:
        """(extra_resources calls, budget inner txns) to touch the current box of `asset_id`."""
        box = _parse_metadata_box(self.client, asset_id)
        if box is None:
            return 0, 0
        params = self._params()
        extra = _box_io_extra_resources(params.header_size + box.body.size)
        budget = _hash_budget_txns(box.body.total_pages(params)) if hashing else 0
        return extra, budget

    # ------------------------------------------------------------------
    # Group builders
    # ------------------------------------------------------------------

    def build_create_metadata_group(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions | None = None,
    ) -> AsaMetadataRegistryComposer:
        """
        Build (but do not send) an ARC-89 create metadata group.

        Returns the generated client's composer, so callers can `.simulate()` or `.send()`.
        """
        opt = options or WriteOptions()
        params = self._params()

        chunks = _chunks_for_create(metadata, params)
        io_extra = _box_io_extra_resources(
            params.header_size + metadata.body.size, other_app_calls=len(chunks) - 1
        )

        # Determine MBR delta via on-chain getter (simulate).
        mbr_delta = AsaMetadataRegistryAvmRead(
            self.client
        ).arc89_get_metadata_mbr_delta(
            asset_id=metadata.asset_id,
            new_size=metadata.body.size,
        )

        # Build payment txn for MBR delta (fee pooled).
        pay_amount = mbr_delta.amount if mbr_delta.is_positive else 0

        mbr_payment = self.client.algorand.create_transaction.payment(
            PaymentParams(
                sender=asset_manager.address,
                receiver=self.client.app_address,
                amount=AlgoAmount(micro_algo=pay_amount),
                static_fee=AlgoAmount(micro_algo=0),
            )
        )

        min_fee = self.client.algorand.get_suggested_params().min_fee
        # Calculate transaction count for fee pooling
        base_txn_count = (
            1  # main app call (arc89_create_metadata)
            + (len(chunks) - 1)  # extra payload calls
            + 1  # MBR payment transaction
            + io_extra
            + opt.extra_resources  # optional extra resources
        )

        # Opcode budget inner transactions: metadata hashing, native Asset URL check
        base_txn_count += int(not metadata.is_empty) + int(metadata.is_arc89_native)

        # Calculate total fee pool including padding
        app_args_sizes = [
            _ARC89_CREATE_METADATA_FIXED_SIZE + len(chunks[0]),
            *(_ARC89_EXTRA_PAYLOAD_FIXED_SIZE + len(chunk) for chunk in chunks[1:]),
        ]
        fee_pool = (
            base_txn_count + opt.fee_padding_txns
        ) * min_fee + _app_args_surcharge_fee(min_fee, app_args_sizes)

        composer = self.client.new_group()
        composer.arc89_create_metadata(
            args=(
                metadata.asset_id,
                metadata.flags.reversible_byte,
                metadata.flags.irreversible_byte,
                metadata.body.size,
                chunks[0],
                mbr_payment,
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=fee_pool),
            ),
        )

        _append_extra_payload(
            composer,
            asset_id=metadata.asset_id,
            chunks=chunks,
            sender=asset_manager.address,
        )
        _append_extra_resources(
            composer,
            count=io_extra + opt.extra_resources + int(not metadata.is_empty),
            sender=asset_manager.address,
        )
        return composer

    def build_replace_metadata_group(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions | None = None,
        assume_current_size: int | None = None,
    ) -> AsaMetadataRegistryComposer:
        """
        Build a replace group, automatically choosing `replace_metadata` or `replace_metadata_larger`.

        If you already know the current on-chain metadata size, pass `assume_current_size` to avoid
        an extra simulate read.
        """
        opt = options or WriteOptions()
        avm = AsaMetadataRegistryAvmRead(self.client)

        current_size = assume_current_size
        if current_size is None:
            pagination = avm.arc89_get_metadata_pagination(asset_id=metadata.asset_id)
            current_size = pagination.metadata_size

        if metadata.body.size <= current_size:
            return self._build_replace_smaller_or_equal(
                asset_manager=asset_manager,
                metadata=metadata,
                options=opt,
                current_size=current_size,
            )
        return self._build_replace_larger(
            asset_manager=asset_manager, metadata=metadata, options=opt
        )

    def _build_replace_smaller_or_equal(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions,
        current_size: int,
    ) -> AsaMetadataRegistryComposer:
        params = self._params()
        chunks = _chunks_for_replace(metadata, params)
        equal_size = metadata.body.size == current_size
        # The whole existing box is touched (resize), size the I/O budget on it.
        io_extra = _box_io_extra_resources(
            params.header_size + current_size, other_app_calls=len(chunks) - 1
        )

        min_fee = self.client.algorand.get_suggested_params().min_fee
        base_txn_count = (
            1  # main app call (arc89_replace_metadata)
            + (len(chunks) - 1)  # extra payload calls
            + io_extra
            + options.extra_resources  # optional extra resources
            + int(not metadata.is_empty)  # extra_resources call
            + int(not metadata.is_empty)  # hash-budget inner transaction
        )

        # MBR refund inner payment transaction (only when size is smaller, not equal)
        if not equal_size:
            base_txn_count += 1

        # Calculate total fee pool including padding
        app_args_sizes = [
            _ARC89_REPLACE_METADATA_SLICE_FIXED_SIZE + len(chunks[0]),
            *(_ARC89_EXTRA_PAYLOAD_FIXED_SIZE + len(chunk) for chunk in chunks[1:]),
        ]
        fee_pool = (
            base_txn_count + options.fee_padding_txns
        ) * min_fee + _app_args_surcharge_fee(min_fee, app_args_sizes)

        composer = self.client.new_group()
        composer.arc89_replace_metadata(
            args=(metadata.asset_id, metadata.body.size, chunks[0]),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=fee_pool),
            ),
        )
        _append_extra_payload(
            composer,
            asset_id=metadata.asset_id,
            chunks=chunks,
            sender=asset_manager.address,
        )
        _append_extra_resources(
            composer,
            count=io_extra + options.extra_resources + int(not metadata.is_empty),
            sender=asset_manager.address,
        )
        return composer

    def _build_replace_larger(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions,
    ) -> AsaMetadataRegistryComposer:
        params = self._params()
        chunks = _chunks_for_replace(metadata, params)
        io_extra = _box_io_extra_resources(
            params.header_size + metadata.body.size, other_app_calls=len(chunks) - 1
        )

        avm = AsaMetadataRegistryAvmRead(self.client)
        mbr_delta = avm.arc89_get_metadata_mbr_delta(
            asset_id=metadata.asset_id, new_size=metadata.body.size
        )

        pay_amount = mbr_delta.amount if mbr_delta.is_positive else 0
        mbr_payment = self.client.algorand.create_transaction.payment(
            PaymentParams(
                sender=asset_manager.address,
                receiver=self.client.app_address,
                amount=AlgoAmount(micro_algo=pay_amount),
                static_fee=AlgoAmount(micro_algo=0),
            )
        )

        min_fee = self.client.algorand.get_suggested_params().min_fee
        txn_count = (
            1  # main app call (arc89_replace_metadata_larger)
            + (len(chunks) - 1)  # extra payload calls
            + 1  # MBR payment transaction
            + io_extra
            + options.extra_resources  # optional extra resources
            + int(not metadata.is_empty)  # extra_resources call
            + int(not metadata.is_empty)  # hash-budget inner transaction
        )

        # Calculate total fee pool including padding
        app_args_sizes = [
            _ARC89_REPLACE_METADATA_SLICE_FIXED_SIZE + len(chunks[0]),
            *(_ARC89_EXTRA_PAYLOAD_FIXED_SIZE + len(chunk) for chunk in chunks[1:]),
        ]
        fee_pool = (
            txn_count + options.fee_padding_txns
        ) * min_fee + _app_args_surcharge_fee(min_fee, app_args_sizes)

        composer = self.client.new_group()
        composer.arc89_replace_metadata_larger(
            args=(metadata.asset_id, metadata.body.size, chunks[0], mbr_payment),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=fee_pool),
            ),
        )
        _append_extra_payload(
            composer,
            asset_id=metadata.asset_id,
            chunks=chunks,
            sender=asset_manager.address,
        )
        _append_extra_resources(
            composer,
            count=io_extra + options.extra_resources + int(not metadata.is_empty),
            sender=asset_manager.address,
        )
        return composer

    def build_replace_metadata_slice_group(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        offset: int,
        payload: bytes,
        options: WriteOptions | None = None,
    ) -> AsaMetadataRegistryComposer:
        """
        Build a group that replaces a slice of the on-chain metadata.

        If `payload` exceeds the registry's replace payload limit, this builds multiple
        `arc89_replace_metadata_slice` calls in one group, adjusting the offset for each chunk.
        """
        opt = options or WriteOptions()
        params = self._params()

        chunks = _chunks_for_slice(payload, params.replace_payload_max_size)
        io_extra, budget = self._box_resources(asset_id, hashing=True)
        io_extra = max(0, io_extra - (len(chunks) - 1))

        min_fee = self.client.algorand.get_suggested_params().min_fee
        txn_count = (
            len(chunks)  # main app calls (arc89_replace_metadata_slice)
            + budget * len(chunks)  # hash recomputed by every slice call
            + io_extra
            + opt.extra_resources  # optional extra resources
        )

        # Calculate total fee pool including padding
        app_args_sizes = [
            _ARC89_REPLACE_METADATA_SLICE_FIXED_SIZE + len(chunk) for chunk in chunks
        ]
        fee_pool = (
            txn_count + opt.fee_padding_txns
        ) * min_fee + _app_args_surcharge_fee(min_fee, app_args_sizes)

        composer = self.client.new_group()

        # First call pays pooled fees.
        composer.arc89_replace_metadata_slice(
            args=(asset_id, offset, chunks[0]),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )

        # Subsequent calls have 0 fee.
        for i, chunk in enumerate(chunks[1:], start=1):
            composer.arc89_replace_metadata_slice(
                args=(asset_id, offset + i * params.replace_payload_max_size, chunk),
                params=CommonAppCallParams(
                    sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=0)
                ),
            )

        _append_extra_resources(
            composer, count=io_extra + opt.extra_resources, sender=asset_manager.address
        )
        return composer

    def build_delete_metadata_group(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        options: WriteOptions | None = None,
    ) -> AsaMetadataRegistryComposer:
        opt = options or WriteOptions()
        io_extra, _ = self._box_resources(asset_id, hashing=False)

        min_fee = self.client.algorand.get_suggested_params().min_fee
        txn_count = (
            1  # main app call (arc89_delete_metadata)
            + 1  # MBR refund inner payment transaction
            + io_extra
            + opt.extra_resources  # optional extra resources
        )

        # Calculate total fee pool including padding
        fee_pool = (txn_count + opt.fee_padding_txns) * min_fee

        composer = self.client.new_group()
        composer.arc89_delete_metadata(
            args=(asset_id,),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=io_extra + opt.extra_resources, sender=asset_manager.address
        )
        return composer

    # ------------------------------------------------------------------
    # High-level send helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _send_group(
        *,
        send_params: SendParams | None,
        options: WriteOptions | None = None,
        composer: AsaMetadataRegistryComposer,
        simulate: SimulateOptions | None = None,
    ) -> SendAtomicTransactionComposerResults:
        """
        Send or simulate a transaction group.
        If `simulate` is provided, simulate instead of sending.
        """

        if simulate is not None:
            return composer.simulate(
                allow_more_logs=simulate.allow_more_logs,
                allow_empty_signatures=simulate.allow_empty_signatures,
                allow_unnamed_resources=simulate.allow_unnamed_resources,
                extra_opcode_budget=simulate.extra_opcode_budget,
                exec_trace_config=simulate.exec_trace_config,
                simulation_round=simulate.simulation_round,
                skip_signatures=simulate.skip_signatures,
            )

        if send_params is None:
            opt = options or WriteOptions()
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees,
                populate_app_call_resources=opt.populate_app_call_resources,
            )

        return composer.send(send_params=send_params)

    def create_metadata(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
        validate_arc3: bool = True,
    ) -> MbrDelta:

        if validate_arc3:
            body_json = metadata.body.json
            if "decimals" in body_json:
                asa_params = _get_asa_params(self.client, metadata.asset_id)
                asa_decimals = asa_params.decimals
                validate_arc3_values(body_json, asa_decimals=asa_decimals)

        composer = self.build_create_metadata_group(
            asset_manager=asset_manager, metadata=metadata, options=options
        )
        result = self._send_group(
            send_params=send_params,
            options=options,
            composer=composer,
        )
        ret_val = result.returns[0].value
        assert isinstance(ret_val, (tuple, list))
        return MbrDelta.from_tuple(ret_val)  # type: ignore[arg-type]

    def replace_metadata(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
        assume_current_size: int | None = None,
        validate_arc3: bool = True,
    ) -> MbrDelta:

        if validate_arc3:
            body_json = metadata.body.json
            if "decimals" in body_json:
                asa_params = _get_asa_params(self.client, metadata.asset_id)
                asa_decimals = asa_params.decimals
                validate_arc3_values(body_json, asa_decimals=asa_decimals)

        composer = self.build_replace_metadata_group(
            asset_manager=asset_manager,
            metadata=metadata,
            options=options,
            assume_current_size=assume_current_size,
        )
        result = self._send_group(
            send_params=send_params,
            options=options,
            composer=composer,
        )
        ret_val = result.returns[0].value
        assert isinstance(ret_val, (tuple, list))
        return MbrDelta.from_tuple(ret_val)  # type: ignore[arg-type]

    def replace_metadata_slice(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        offset: int,
        payload: bytes,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
        validate: bool = True,
    ) -> None:
        if validate:
            # ARC-89: clients MUST validate the complete post-replacement Metadata.
            box = _parse_metadata_box(self.client, asset_id)
            if box is None:
                raise MetadataNotFoundError(f"No metadata box for asset {asset_id}")
            body = box.body.raw_bytes
            if offset < 0 or offset + len(payload) > len(body):
                raise InvalidSliceError("Slice exceeds the Metadata size")
            new_body = body[:offset] + payload + body[offset + len(payload) :]
            obj = decode_metadata_json(new_body)
            if box.header.flags.irreversible.arc3:
                validate_arc3_schema(obj)

        composer = self.build_replace_metadata_slice_group(
            asset_manager=asset_manager,
            asset_id=asset_id,
            offset=offset,
            payload=payload,
            options=options,
        )
        self._send_group(
            send_params=send_params,
            options=options,
            composer=composer,
        )

    def delete_metadata(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
    ) -> MbrDelta:
        composer = self.build_delete_metadata_group(
            asset_manager=asset_manager, asset_id=asset_id, options=options
        )
        result = self._send_group(
            send_params=send_params,
            options=options,
            composer=composer,
        )
        ret_val = result.returns[0].value
        assert isinstance(ret_val, (tuple, list))
        return MbrDelta.from_tuple(ret_val)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Flag & migration
    # ------------------------------------------------------------------

    def set_reversible_flag(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        flag_index: int,
        value: bool,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
    ) -> None:
        if not flags.REV_FLG_ARC20 <= flag_index <= flags.REV_FLG_RESERVED_7:
            raise InvalidFlagIndexError(
                f"Invalid reversible flag index: {flag_index}, must be in [0, 7]"
            )

        if value and flag_index in ARC3_PROPERTIES_FLAG_TO_KEY:
            box = _parse_metadata_box(self.client, asset_id)
            if box is not None and box.header.flags.irreversible.arc3:
                validate_arc3_properties(
                    box.body.json, ARC3_PROPERTIES_FLAG_TO_KEY[flag_index]
                )

        opt = options or WriteOptions()
        io_extra, budget = self._box_resources(asset_id, hashing=True)

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (
            1 + budget + io_extra + opt.extra_resources + opt.fee_padding_txns
        ) * min_fee

        composer = self.client.new_group()
        composer.arc89_set_reversible_flag(
            args=(asset_id, flag_index, value),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=io_extra + opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees,
                populate_app_call_resources=opt.populate_app_call_resources,
            )
        composer.send(send_params=send_params)

    def set_irreversible_flag(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        flag_index: int,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
    ) -> None:
        if not flags.IRR_FLG_ARC54 <= flag_index <= flags.IRR_FLG_RESERVED_6:
            raise InvalidFlagIndexError(
                f"Invalid irreversible flag index: {flag_index}, must be in [2, 6]."
                f" Flags 0, 1 are creation only. Flag 7 is reserved to set_immutable."
            )

        opt = options or WriteOptions()
        io_extra, budget = self._box_resources(asset_id, hashing=True)

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (
            1 + budget + io_extra + opt.extra_resources + opt.fee_padding_txns
        ) * min_fee

        composer = self.client.new_group()
        composer.arc89_set_irreversible_flag(
            args=(asset_id, flag_index),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=io_extra + opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees,
                populate_app_call_resources=opt.populate_app_call_resources,
            )
        composer.send(send_params=send_params)

    def set_immutable(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
    ) -> None:
        opt = options or WriteOptions()
        io_extra, budget = self._box_resources(asset_id, hashing=True)

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (
            1 + budget + io_extra + opt.extra_resources + opt.fee_padding_txns
        ) * min_fee

        composer = self.client.new_group()
        composer.arc89_set_immutable(
            args=(asset_id,),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=io_extra + opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees,
                populate_app_call_resources=opt.populate_app_call_resources,
            )
        composer.send(send_params=send_params)

    def migrate_metadata(
        self,
        *,
        asset_manager: SigningAccount,
        asset_id: int,
        new_registry_id: int,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
    ) -> None:
        opt = options or WriteOptions()
        io_extra, budget = self._box_resources(asset_id, hashing=False)

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (
            1 + budget + io_extra + opt.extra_resources + opt.fee_padding_txns
        ) * min_fee

        composer = self.client.new_group()
        composer.arc89_migrate_metadata(
            args=(asset_id, new_registry_id),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=io_extra + opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees,
                populate_app_call_resources=opt.populate_app_call_resources,
            )
        composer.send(send_params=send_params)
