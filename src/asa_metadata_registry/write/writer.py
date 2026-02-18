from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from algokit_utils import (
    AlgoAmount,
    CommonAppCallParams,
    PaymentParams,
    SendAtomicTransactionComposerResults,
    SendParams,
    SigningAccount,
)

from .. import flags
from ..errors import InvalidFlagIndexError, MissingAppClientError
from ..generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
    AsaMetadataRegistryComposer,
)
from ..models import AssetMetadata, MbrDelta, RegistryParameters
from ..read.avm import AsaMetadataRegistryAvmRead, SimulateOptions


def _chunks_for_create(metadata: AssetMetadata) -> list[bytes]:
    return metadata.body.chunked_payload()


def _chunks_for_replace(metadata: AssetMetadata) -> list[bytes]:
    return metadata.body.chunked_payload()


def _chunks_for_slice(payload: bytes, max_size: int) -> list[bytes]:
    if max_size <= 0:
        raise ValueError("max_size must be > 0")
    if payload == b"":
        return [b""]
    return [payload[i : i + max_size] for i in range(0, len(payload), max_size)]


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

        chunks = _chunks_for_create(metadata)

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
            + opt.extra_resources  # optional extra resources
        )

        # Add extra transaction for non-empty metadata opcode budget
        if not metadata.is_empty:
            base_txn_count += 1

        # Calculate total fee pool including padding
        fee_pool = (base_txn_count + opt.fee_padding_txns) * min_fee

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
            composer, count=opt.extra_resources, sender=asset_manager.address
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
                equal_size=metadata.body.size == current_size,
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
        equal_size: bool,
    ) -> AsaMetadataRegistryComposer:
        chunks = _chunks_for_replace(metadata)

        min_fee = self.client.algorand.get_suggested_params().min_fee
        base_txn_count = (
            1  # main app call (arc89_replace_metadata)
            + (len(chunks) - 1)  # extra payload calls
            + options.extra_resources  # optional extra resources
        )

        # MBR refund inner payment transaction (only when size is smaller, not equal)
        if not equal_size:
            base_txn_count += 1

        # Calculate total fee pool including padding
        fee_pool = (base_txn_count + options.fee_padding_txns) * min_fee

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
            composer, count=options.extra_resources, sender=asset_manager.address
        )
        return composer

    def _build_replace_larger(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions,
    ) -> AsaMetadataRegistryComposer:
        chunks = _chunks_for_replace(metadata)

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
            + options.extra_resources  # optional extra resources
        )

        # Calculate total fee pool including padding
        fee_pool = (txn_count + options.fee_padding_txns) * min_fee

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
            composer, count=options.extra_resources, sender=asset_manager.address
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

        min_fee = self.client.algorand.get_suggested_params().min_fee
        txn_count = (
            len(chunks)  # main app calls (arc89_replace_metadata_slice)
            + opt.extra_resources  # optional extra resources
        )

        # Calculate total fee pool including padding
        fee_pool = (txn_count + opt.fee_padding_txns) * min_fee

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
            composer, count=opt.extra_resources, sender=asset_manager.address
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

        min_fee = self.client.algorand.get_suggested_params().min_fee
        txn_count = (
            1  # main app call (arc89_delete_metadata)
            + 1  # MBR refund inner payment transaction
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
            composer, count=opt.extra_resources, sender=asset_manager.address
        )
        return composer

    # ------------------------------------------------------------------
    # High-level send helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _send_group(
        *,
        simulate_before_send: bool,
        simulate_options: SimulateOptions | None,
        send_params: SendParams | None,
        options: WriteOptions | None = None,
        composer: AsaMetadataRegistryComposer,
    ) -> SendAtomicTransactionComposerResults:
        if simulate_before_send:
            # Use user's simulate options if provided.
            sim = simulate_options or SimulateOptions(
                allow_empty_signatures=True, skip_signatures=True
            )
            composer.simulate(
                allow_more_logs=sim.allow_more_logs,
                allow_empty_signatures=sim.allow_empty_signatures,
                allow_unnamed_resources=sim.allow_unnamed_resources,
                extra_opcode_budget=sim.extra_opcode_budget,
                exec_trace_config=sim.exec_trace_config,
                simulation_round=sim.simulation_round,
                skip_signatures=sim.skip_signatures,
            )

        if send_params is None:
            opt = options or WriteOptions()
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees
            )

        return composer.send(send_params=send_params)

    def create_metadata(
        self,
        *,
        asset_manager: SigningAccount,
        metadata: AssetMetadata,
        options: WriteOptions | None = None,
        send_params: SendParams | None = None,
        simulate_before_send: bool = False,
        simulate_options: SimulateOptions | None = None,
    ) -> MbrDelta:
        composer = self.build_create_metadata_group(
            asset_manager=asset_manager, metadata=metadata, options=options
        )
        result = self._send_group(
            simulate_before_send=simulate_before_send,
            simulate_options=simulate_options,
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
        simulate_before_send: bool = False,
        simulate_options: SimulateOptions | None = None,
        assume_current_size: int | None = None,
    ) -> MbrDelta:
        composer = self.build_replace_metadata_group(
            asset_manager=asset_manager,
            metadata=metadata,
            options=options,
            assume_current_size=assume_current_size,
        )
        result = self._send_group(
            simulate_before_send=simulate_before_send,
            simulate_options=simulate_options,
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
        simulate_before_send: bool = False,
        simulate_options: SimulateOptions | None = None,
    ) -> None:
        composer = self.build_replace_metadata_slice_group(
            asset_manager=asset_manager,
            asset_id=asset_id,
            offset=offset,
            payload=payload,
            options=options,
        )
        self._send_group(
            simulate_before_send=simulate_before_send,
            simulate_options=simulate_options,
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
        simulate_before_send: bool = False,
        simulate_options: SimulateOptions | None = None,
    ) -> MbrDelta:
        composer = self.build_delete_metadata_group(
            asset_manager=asset_manager, asset_id=asset_id, options=options
        )
        result = self._send_group(
            simulate_before_send=simulate_before_send,
            simulate_options=simulate_options,
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

        opt = options or WriteOptions()

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (1 + opt.extra_resources + opt.fee_padding_txns) * min_fee

        composer = self.client.new_group()
        composer.arc89_set_reversible_flag(
            args=(asset_id, flag_index, value),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees
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
        if not flags.IRR_FLG_ARC54 <= flag_index <= flags.IRR_FLG_IMMUTABLE:
            raise InvalidFlagIndexError(
                f"Invalid irreversible flag index: {flag_index}, must be in [2, 7]. Flags 0, 1 are creation only."
            )

        opt = options or WriteOptions()

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (1 + opt.extra_resources + opt.fee_padding_txns) * min_fee

        composer = self.client.new_group()
        composer.arc89_set_irreversible_flag(
            args=(asset_id, flag_index),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees
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

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (1 + opt.extra_resources + opt.fee_padding_txns) * min_fee

        composer = self.client.new_group()
        composer.arc89_set_immutable(
            args=(asset_id,),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees
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

        min_fee = self.client.algorand.get_suggested_params().min_fee
        fee_pool = (1 + opt.extra_resources + opt.fee_padding_txns) * min_fee

        composer = self.client.new_group()
        composer.arc89_migrate_metadata(
            args=(asset_id, new_registry_id),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=fee_pool)
            ),
        )
        _append_extra_resources(
            composer, count=opt.extra_resources, sender=asset_manager.address
        )

        if send_params is None:
            send_params = SendParams(
                cover_app_call_inner_transaction_fees=opt.cover_app_call_inner_transaction_fees
            )
        composer.send(send_params=send_params)
