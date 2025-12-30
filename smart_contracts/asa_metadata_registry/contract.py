from algopy import (
    Account,
    Asset,
    BoxMap,
    Bytes,
    Global,
    OnCompleteAction,
    String,
    TemplateVar,
    TransactionType,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    gtxn,
    itxn,
    op,
    urange,
)

from smart_contracts.asa_validation import AsaValidation
from smart_contracts.avm_common import (
    arc90_box_query,
    ceil_div,
    trimmed_itob,
    umin,
)
from smart_contracts.template_vars import TRUSTED_DEPLOYER

from . import abi_types as abi
from . import constants as const
from . import enums as enums
from . import errors as err
from . import flags as flg
from .arc89_interface import Arc89Interface


class AsaMetadataRegistry(Arc89Interface, AsaValidation):
    """
    Singleton Application providing ASA metadata via Algod API and AVM
    """

    def __init__(self) -> None:
        self.asset_metadata = BoxMap(Asset, Bytes, key_prefix="")

    def _metadata_exists(self, asa: Asset) -> bool:
        return asa in self.asset_metadata

    def _is_valid_max_metadata_size(self, metadata_size: UInt64) -> bool:
        return metadata_size <= const.MAX_METADATA_SIZE

    def _is_short_metadata_size(self, metadata_size: UInt64) -> bool:
        return metadata_size <= const.SHORT_METADATA_SIZE

    def _get_metadata_identifiers(self, asa: Asset) -> Bytes:
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_METADATA_IDENTIFIERS,
            length=const.METADATA_IDENTIFIERS_SIZE,
        )

    def _set_metadata_identifiers(self, asa: Asset, identifiers: Bytes) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_METADATA_IDENTIFIERS, value=identifiers
        )

    def _is_short(self, asa: Asset) -> bool:
        return op.getbit(
            self._get_metadata_identifiers(asa),
            const.BIT_RIGHTMOST_IDENTIFIER - flg.ID_SHORT,
        )

    def _get_reversible_flags(self, asa: Asset) -> Bytes:
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_REVERSIBLE_FLAGS, length=const.REVERSIBLE_FLAGS_SIZE
        )

    def _get_reversible_flag_value(self, asa: Asset, flag: UInt64) -> bool:
        return op.getbit(
            self._get_reversible_flags(asa),
            const.BIT_RIGHTMOST_REV_FLAG - flag,
        )

    def _set_reversible_flag_value(
        self, asa: Asset, flag: UInt64, *, value: bool
    ) -> None:
        updated_flags = op.setbit_bytes(
            self._get_reversible_flags(asa), const.BIT_RIGHTMOST_REV_FLAG - flag, value
        )
        self._set_reversible_flags(asa, updated_flags)

    def _set_reversible_flags(self, asa: Asset, flags: Bytes) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_REVERSIBLE_FLAGS, value=flags
        )

    def _get_irreversible_flags(self, asa: Asset) -> Bytes:
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_IRREVERSIBLE_FLAGS,
            length=const.IRREVERSIBLE_FLAGS_SIZE,
        )

    def _set_irreversible_flags(self, asa: Asset, flags: Bytes) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_IRREVERSIBLE_FLAGS, value=flags
        )

    def _get_irreversible_flag_value(self, asa: Asset, flag: UInt64) -> bool:
        return op.getbit(
            self._get_irreversible_flags(asa),
            const.BIT_RIGHTMOST_IRR_FLAG - flag,
        )

    def _set_irreversible_flag_value(self, asa: Asset, flag: UInt64) -> None:
        updated_flags = op.setbit_bytes(
            self._get_irreversible_flags(asa),
            const.BIT_RIGHTMOST_IRR_FLAG - flag,
            True,  # noqa: FBT003
        )
        self._set_irreversible_flags(asa, updated_flags)

    def _get_metadata_hash(self, asa: Asset) -> Bytes:
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_METADATA_HASH, length=const.METADATA_HASH_SIZE
        )

    def _set_metadata_hash(self, asa: Asset, metadata_hash: Bytes) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_METADATA_HASH, value=metadata_hash
        )

    def _get_last_modified_round(self, asa: Asset) -> UInt64:
        return op.btoi(
            self.asset_metadata.box(asa).extract(
                start_index=const.IDX_LAST_MODIFIED_ROUND,
                length=const.LAST_MODIFIED_ROUND_SIZE,
            )
        )

    def _set_last_modified_round(self, asa: Asset, last_modified_round: UInt64) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_LAST_MODIFIED_ROUND,
            value=op.itob(last_modified_round),
        )

    def _get_deprecated_by(self, asa: Asset) -> UInt64:
        return op.btoi(
            self.asset_metadata.box(asa).extract(
                start_index=const.IDX_DEPRECATED_BY,
                length=const.DEPRECATED_BY_SIZE,
            )
        )

    def _set_deprecated_by(self, asa: Asset, deprecated_by: UInt64) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_DEPRECATED_BY,
            value=op.itob(deprecated_by),
        )

    def _get_metadata_size(self, asa: Asset) -> UInt64:
        return self.asset_metadata.box(asa).length - const.HEADER_SIZE

    def _append_payload(self, asa: Asset, payload: Bytes) -> None:
        old_asset_metadata_box_size = self.asset_metadata.box(asa).length
        self.asset_metadata.box(asa).resize(
            new_size=old_asset_metadata_box_size + payload.length
        )
        self.asset_metadata.box(asa).replace(
            start_index=old_asset_metadata_box_size, value=payload
        )

    def _is_arc3(self, asa: Asset) -> bool:
        return self._get_irreversible_flag_value(asa, UInt64(flg.IRR_FLG_ARC3))

    def _is_arc89_native(self, asa: Asset) -> bool:
        return self._get_irreversible_flag_value(asa, UInt64(flg.IRR_FLG_ARC89_NATIVE))

    def _is_immutable(self, asa: Asset) -> bool:
        return self._get_irreversible_flag_value(asa, UInt64(flg.IRR_FLG_IMMUTABLE))

    def _is_registry_call(self, txn: gtxn.Transaction) -> bool:
        return (
            txn.type == TransactionType.ApplicationCall
            and txn.app_id == Global.current_application_id
            and txn.on_completion == OnCompleteAction.NoOp
        )

    def _is_extra_payload_call(self, asa: Asset, txn: gtxn.Transaction) -> bool:
        return (
            self._is_registry_call(txn)
            and txn.app_args(const.ARC4_ARG_METHOD_SELECTOR)
            == arc4.arc4_signature(Arc89Interface.arc89_extra_payload)
            and txn.app_args(const.ARC89_EXTRA_PAYLOAD_ARG_ASSET_ID) == op.itob(asa.id)
        )

    def _read_extra_payload(self, txn: gtxn.Transaction) -> Bytes:
        # This subroutine assumes txn is already validated as an extra payload txn
        return arc4.DynamicBytes.from_bytes(
            txn.app_args(const.ARC89_EXTRA_PAYLOAD_ARG_PAYLOAD)
        ).native

    def _set_metadata_payload(
        self, asa: Asset, metadata_size: UInt64, payload: Bytes
    ) -> None:
        # Erase existing metadata payload
        self.asset_metadata.box(asa).resize(new_size=UInt64(const.HEADER_SIZE))

        # Append provided payload
        self._append_payload(asa, payload)
        assert self._get_metadata_size(asa) <= metadata_size, err.PAYLOAD_OVERFLOW

        # Append staged extra payload (in the same Group, if any)
        group_size = Global.group_size
        group_index = Txn.group_index
        for idx in urange(group_index + 1, group_size):
            txn = gtxn.Transaction(idx)
            if self._is_extra_payload_call(asa, txn):
                extra_payload = self._read_extra_payload(txn)
                assert (
                    self._get_metadata_size(asa) + extra_payload.length <= metadata_size
                ), err.PAYLOAD_OVERFLOW
                self._append_payload(asa, extra_payload)
                assert (
                    self._get_metadata_size(asa) <= metadata_size
                ), err.PAYLOAD_OVERFLOW
        assert self._get_metadata_size(asa) == metadata_size, err.METADATA_SIZE_MISMATCH

    def _get_total_pages(self, asa: Asset) -> UInt64:
        """
        Total page count, allowing 0 pages for empty metadata.
        ceil(metadata_size / PAGE_SIZE)
        """
        n = self._get_metadata_size(asa)
        return ceil_div(num=n, den=UInt64(const.PAGE_SIZE))

    def _get_metadata_page(self, asa: Asset, page_index: UInt64) -> Bytes:
        """
        Return the content of the page identified by 0-based index from the HEAD.
        Page `p` covers `[p*PAGE_SIZE, min((p+1)*PAGE_SIZE, metadata_size))`.
        Final page may be shorter; intermediate pages SHOULD be exactly PAGE_SIZE.
        If page_index is out of range (>= total_pages), returns empty bytes.
        """
        ps = UInt64(const.PAGE_SIZE)
        n = self._get_metadata_size(asa)

        start = page_index * ps
        if start >= n:
            # Out-of-range page (including empty metadata with page_index > 0)
            return Bytes(b"")

        remaining = n - start
        length = umin(ps, remaining)

        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_METADATA + start, length=length
        )

    def _get_slice(self, asa: Asset, offset: UInt64, size: UInt64) -> Bytes:
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_METADATA + offset, length=size
        )

    def _get_short_metadata(self, asa: Asset) -> Bytes:
        assert self._is_short(asa), err.METADATA_NOT_SHORT
        return self._get_slice(asa, UInt64(0), self._get_metadata_size(asa))

    def _identify_metadata(self, asa: Asset) -> None:
        metadata_size = self._get_metadata_size(asa)
        identifiers = op.setbit_bytes(
            self._get_metadata_identifiers(asa),
            const.BIT_RIGHTMOST_IDENTIFIER - flg.ID_SHORT,
            self._is_short_metadata_size(metadata_size),
        )
        self._set_metadata_identifiers(asa, identifiers)

    def _compute_header_hash(self, asa: Asset) -> Bytes:
        # hh = SHA-512/256("arc0089/header" || Asset ID || Metadata Identifiers
        # || Reversible Flags || Irreversible Flags || Metadata Size)
        ensure_budget(required_budget=const.HEADER_HASH_OP_BUDGET)
        domain = Bytes(const.HASH_DOMAIN_HEADER)
        asset_id = op.itob(asa.id)
        metadata_identifiers = self._get_metadata_identifiers(asa)
        reversible_flags = self._get_reversible_flags(asa)
        irreversible_flags = self._get_irreversible_flags(asa)
        metadata_size = trimmed_itob(
            uint=self._get_metadata_size(asa),
            size=UInt64(const.UINT16_SIZE),
        )
        return op.sha512_256(
            domain
            + asset_id
            + metadata_identifiers
            + reversible_flags
            + irreversible_flags
            + metadata_size
        )

    def _compute_page_hash(
        self, asa: Asset, page_index: UInt64, page_content: Bytes
    ) -> Bytes:
        # ph[i] = SHA-512/256("arc0089/page" || Asset ID || Page Index || Page Size || Page Content)
        ensure_budget(required_budget=const.PAGE_HASH_OP_BUDGET)
        domain = Bytes(const.HASH_DOMAIN_PAGE)
        asset_id = op.itob(asa.id)
        page_idx = trimmed_itob(uint=page_index, size=UInt64(const.UINT8_SIZE))
        page_size = trimmed_itob(
            uint=page_content.length, size=UInt64(const.UINT16_SIZE)
        )
        return op.sha512_256(domain + asset_id + page_idx + page_size + page_content)

    def _compute_metadata_hash(self, asa: Asset) -> Bytes:
        # am = SHA-512/256("arc0089/am" || hh || ph[0] || ph[1] || ... || ph[total_pages - 1]) or
        # am = SHA-512/256("arc0089/am" || hh), if no pages
        domain = Bytes(const.HASH_DOMAIN_METADATA)
        hh = self._compute_header_hash(asa)
        total_pages = self._get_total_pages(asa)
        concatenated_ph = Bytes()
        if total_pages > 0:
            for page_index in urange(0, total_pages):
                page_content = self._get_metadata_page(asa, page_index)
                ph = self._compute_page_hash(asa, page_index, page_content)
                concatenated_ph += ph
        return op.sha512_256(domain + hh + concatenated_ph)

    def _check_base_preconditions(self, asa: Asset, metadata_size: UInt64) -> None:
        assert self._asa_exists(asa), err.ASA_NOT_EXIST
        assert self._is_asa_manager(asa), err.UNAUTHORIZED
        assert self._is_valid_max_metadata_size(
            metadata_size
        ), err.EXCEEDS_MAX_METADATA_SIZE

    def _check_update_preconditions(self, asa: Asset, metadata_size: UInt64) -> None:
        self._check_base_preconditions(asa, metadata_size)
        assert self._metadata_exists(asa), err.ASSET_METADATA_NOT_EXIST
        assert not self._is_immutable(asa), err.IMMUTABLE

    def _check_existence_preconditions(self, asa: Asset) -> None:
        assert self._asa_exists(asa), err.ASA_NOT_EXIST
        assert self._metadata_exists(asa), err.ASSET_METADATA_NOT_EXIST

    def _check_set_flag_preconditions(self, asa: Asset) -> None:
        self._check_existence_preconditions(asa)
        assert self._is_asa_manager(asa), err.UNAUTHORIZED
        assert not self._is_immutable(asa), err.IMMUTABLE

    def _emit_updated_event(self, asa: Asset, metadata_hash: Bytes) -> None:
        arc4.emit(
            abi.Arc89MetadataUpdated(
                asset_id=arc4.UInt64(asa.id),
                round=arc4.UInt64(Global.round),
                timestamp=arc4.UInt64(Global.latest_timestamp),
                reversible_flags=arc4.Byte(op.btoi(self._get_reversible_flags(asa))),
                irreversible_flags=arc4.Byte(
                    op.btoi(self._get_irreversible_flags(asa))
                ),
                is_short=arc4.Bool(self._is_short(asa)),
                hash=abi.Hash.from_bytes(metadata_hash),
            )
        )

    def _update_header_excluding_flags_and_emit(self, asa: Asset) -> None:
        # ⚠️ The subroutine assumes that Metadata Flags have already been set
        self._identify_metadata(asa)
        metadata_hash = self._compute_metadata_hash(asa)
        self._set_metadata_hash(asa, metadata_hash)
        self._set_last_modified_round(asa, Global.round)
        self._emit_updated_event(asa, metadata_hash)

    @arc4.baremethod(create="require")
    def deploy(self) -> None:
        """
        Deploy the ASA Metadata Registry Application, restricted to the Trusted Deployer.
        """
        # Preconditions
        assert Txn.sender == TemplateVar[Account](
            TRUSTED_DEPLOYER
        ), err.UNTRUSTED_DEPLOYER

    @arc4.abimethod
    def arc89_create_metadata(
        self,
        *,
        asset_id: Asset,
        reversible_flags: arc4.Byte,
        irreversible_flags: arc4.Byte,
        metadata_size: arc4.UInt16,
        payload: arc4.DynamicBytes,
        mbr_delta_payment: gtxn.PaymentTransaction,
    ) -> abi.MbrDelta:
        """
        Create Asset Metadata for an existing ASA, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to create the Asset Metadata for
            reversible_flags: The Reversible Flags. WARNING: LSB and 1 can by set only at creation time
            irreversible_flags: The Irreversible Flags. WARNING: if the MSB is True the Asset Metadata is IMMUTABLE
            metadata_size: The Metadata byte size to be created
            payload: The Metadata payload (without Header). WARNING: Payload larger than args capacity
                     must be provided with arc89_extra_payload calls in the Group
            mbr_delta_payment: Payment of the MBR Delta amount (microALGO) for the Asset Metadata Box creation

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        # Preconditions
        self._check_base_preconditions(asset_id, metadata_size.as_uint64())
        assert not self._metadata_exists(asset_id), err.ASSET_METADATA_EXIST
        assert (
            mbr_delta_payment.receiver == Global.current_application_address
        ), err.MBR_DELTA_RECEIVER_INVALID

        # Initialize empty Asset Metadata Box
        mbr_i = Global.current_application_address.min_balance
        _exists = self.asset_metadata.box(asset_id).create(size=UInt64(0))

        # Set Metadata Body
        if payload.native.length > 0:
            ensure_budget(required_budget=const.APP_CALL_OP_BUDGET)
        self._set_metadata_payload(asset_id, metadata_size.as_uint64(), payload.native)

        # Update Metadata Header
        self._identify_metadata(asset_id)
        self._set_reversible_flags(
            asset_id,
            trimmed_itob(
                uint=reversible_flags.as_uint64(), size=UInt64(const.BYTE_SIZE)
            ),
        )
        self._set_irreversible_flags(
            asset_id,
            trimmed_itob(
                uint=irreversible_flags.as_uint64(), size=UInt64(const.BYTE_SIZE)
            ),
        )
        if asset_id.metadata_hash != Bytes(
            const.BYTES32_SIZE * b"\x00"
        ):  # Not empty metadata hash
            assert self._is_immutable(asset_id), err.REQUIRES_IMMUTABLE
            metadata_hash = asset_id.metadata_hash
        else:
            metadata_hash = self._compute_metadata_hash(asset_id)
        self._set_metadata_hash(asset_id, metadata_hash)
        self._set_last_modified_round(asset_id, Global.round)
        self._set_deprecated_by(asset_id, UInt64(0))

        # Postconditions
        if self._is_arc3(asset_id):
            assert self._is_arc3_compliant(asset_id), err.ASA_NOT_ARC3_COMPLIANT
        if self._is_arc89_native(asset_id):
            assert self._is_arc89_compliant(asset_id), err.ASA_NOT_ARC89_COMPLIANT

        self._emit_updated_event(asset_id, metadata_hash)

        mbr_delta_amount = Global.current_application_address.min_balance - mbr_i
        assert (
            mbr_delta_payment.amount >= mbr_delta_amount
        ), err.MBR_DELTA_AMOUNT_INVALID

        return abi.MbrDelta(
            sign=arc4.UInt8(enums.MBR_DELTA_POS), amount=arc4.UInt64(mbr_delta_amount)
        )

    @arc4.abimethod
    def arc89_replace_metadata(
        self,
        *,
        asset_id: Asset,
        metadata_size: arc4.UInt16,
        payload: arc4.DynamicBytes,
    ) -> abi.MbrDelta:
        """
        Replace mutable Metadata with a smaller or equal size payload for an existing ASA,
        restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to replace the Asset Metadata for
            metadata_size: The new Metadata byte size, must be less than or equal to the existing
            payload: The Metadata payload (without Header). WARNING: Payload larger than args capacity
                    must be provided with arc89_extra_payload calls in the Group

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        # Preconditions
        self._check_update_preconditions(asset_id, metadata_size.as_uint64())
        assert metadata_size.as_uint64() <= self._get_metadata_size(
            asset_id
        ), err.LARGER_METADATA_SIZE

        # Update Metadata Body
        mbr_i = Global.current_application_address.min_balance
        self._set_metadata_payload(asset_id, metadata_size.as_uint64(), payload.native)

        # Update Metadata Header
        self._update_header_excluding_flags_and_emit(asset_id)

        # Postconditions
        assert (
            self._get_metadata_size(asset_id) == metadata_size.as_uint64()
        ), err.METADATA_SIZE_MISMATCH

        mbr_delta_amount = mbr_i - Global.current_application_address.min_balance
        if mbr_delta_amount == 0:
            sign = UInt64(enums.MBR_DELTA_NULL)
        else:
            sign = UInt64(enums.MBR_DELTA_NEG)
            itxn.Payment(
                receiver=asset_id.manager,
                amount=mbr_delta_amount,
            ).submit()

        return abi.MbrDelta(sign=arc4.UInt8(sign), amount=arc4.UInt64(mbr_delta_amount))

    @arc4.abimethod
    def arc89_replace_metadata_larger(
        self,
        *,
        asset_id: Asset,
        metadata_size: arc4.UInt16,
        payload: arc4.DynamicBytes,
        mbr_delta_payment: gtxn.PaymentTransaction,
    ) -> abi.MbrDelta:
        """
        Replace mutable Metadata with a larger size payload for an existing ASA,
        restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to replace the Asset Metadata for
            metadata_size: The new Metadata byte size, must be larger than the existing
            payload: The Metadata payload (without Header). WARNING: Payload larger than args capacity
                     must be provided with arc89_extra_payload calls in the Group
            mbr_delta_payment: Payment of the MBR Delta amount (microALGO) for the larger Asset Metadata Box replace

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        # Preconditions
        self._check_update_preconditions(asset_id, metadata_size.as_uint64())
        assert metadata_size.as_uint64() > self._get_metadata_size(
            asset_id
        ), err.SMALLER_METADATA_SIZE
        assert (
            mbr_delta_payment.receiver == Global.current_application_address
        ), err.MBR_DELTA_RECEIVER_INVALID

        # Update Metadata Body
        mbr_i = Global.current_application_address.min_balance
        self._set_metadata_payload(asset_id, metadata_size.as_uint64(), payload.native)

        # Update Metadata Header
        self._update_header_excluding_flags_and_emit(asset_id)

        # Postconditions
        assert (
            self._get_metadata_size(asset_id) == metadata_size.as_uint64()
        ), err.METADATA_SIZE_MISMATCH

        mbr_delta_amount = Global.current_application_address.min_balance - mbr_i
        assert (
            mbr_delta_payment.amount >= mbr_delta_amount
        ), err.MBR_DELTA_AMOUNT_INVALID

        return abi.MbrDelta(
            sign=arc4.UInt8(enums.MBR_DELTA_POS), amount=arc4.UInt64(mbr_delta_amount)
        )

    @arc4.abimethod
    def arc89_replace_metadata_slice(
        self,
        *,
        asset_id: Asset,
        offset: arc4.UInt16,
        payload: arc4.DynamicBytes,
    ) -> None:
        """
        Replace a slice of the Asset Metadata for an ASA with a payload of the same size,
        restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to replace the Asset Metadata slice for
            offset: The 0-based byte offset within the Metadata (body) bytes
            payload: The slice payload
        """
        # Preconditions
        self._check_update_preconditions(asset_id, self._get_metadata_size(asset_id))
        assert offset.as_uint64() + payload.native.length <= self._get_metadata_size(
            asset_id
        ), err.EXCEEDS_METADATA_SIZE

        # Handle Not Idempotent
        existing_slice = self._get_slice(
            asset_id, offset.as_uint64(), payload.native.length
        )
        if payload.native != existing_slice:
            # Update Metadata Body
            self.asset_metadata.box(asset_id).replace(
                start_index=const.IDX_METADATA + offset.as_uint64(),
                value=payload.native,
            )

            # Update Metadata Header
            self._update_header_excluding_flags_and_emit(asset_id)

    @arc4.abimethod
    def arc89_migrate_metadata(
        self,
        *,
        asset_id: Asset,
        new_registry_id: arc4.UInt64,
    ) -> None:
        """
        Migrate the Asset Metadata for an ASA to a new ASA Metadata Registry version,
        restricted to the ASA Manager Address

        Args:
            asset_id: The Asset ID to migrate the Asset Metadata for
            new_registry_id: The Application ID of the new ASA Metadata Registry version
        """
        # Preconditions
        self._check_set_flag_preconditions(asset_id)
        assert (
            new_registry_id.as_uint64() != Global.current_application_id.id
        ), err.NEW_REGISTRY_ID_INVALID

        # Update Deprecated By
        self._set_deprecated_by(asset_id, new_registry_id.as_uint64())

        arc4.emit(
            abi.Arc89MetadataMigrated(
                asset_id=arc4.UInt64(asset_id.id),
                round=arc4.UInt64(Global.round),
                timestamp=arc4.UInt64(Global.latest_timestamp),
                new_registry_id=arc4.UInt64(self._get_deprecated_by(asset_id)),
            )
        )

    @arc4.abimethod
    def arc89_delete_metadata(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MbrDelta:
        """
        Delete Asset Metadata for an ASA, restricted to the ASA Manager Address (if the ASA still exists).

        Args:
            asset_id: The Asset ID to delete the Asset Metadata for

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        # Preconditions
        assert self._metadata_exists(asset_id), err.ASSET_METADATA_NOT_EXIST
        if self._asa_exists(asset_id):
            assert not self._is_immutable(asset_id), err.IMMUTABLE
            assert self._is_asa_manager(asset_id), err.UNAUTHORIZED

        # Delete Metadata and refund MBR
        mbr_i = Global.current_application_address.min_balance
        del self.asset_metadata[asset_id]
        mbr_delta_amount = mbr_i - Global.current_application_address.min_balance
        itxn.Payment(
            receiver=asset_id.manager if self._asa_exists(asset_id) else Txn.sender,
            amount=mbr_delta_amount,
        ).submit()

        arc4.emit(
            abi.Arc89MetadataDeleted(
                asset_id=arc4.UInt64(asset_id.id),
                round=arc4.UInt64(Global.round),
                timestamp=arc4.UInt64(Global.latest_timestamp),
            )
        )

        return abi.MbrDelta(
            sign=arc4.UInt8(enums.MBR_DELTA_NEG), amount=arc4.UInt64(mbr_delta_amount)
        )

    @arc4.abimethod
    def arc89_extra_payload(
        self,
        *,
        asset_id: Asset,
        payload: arc4.DynamicBytes,
    ) -> None:
        """
        Concatenate extra payload to Asset Metadata head call methods (creation or replacement).

        Args:
            asset_id: The Asset ID to provide Metadata extra payload for
            payload: The Metadata extra payload to concatenate
        """
        # Preconditions
        assert Global.group_size >= 2, err.NO_PAYLOAD_HEAD_CALL
        assert self._asa_exists(asset_id), err.ASA_NOT_EXIST
        assert self._metadata_exists(asset_id), err.ASSET_METADATA_NOT_EXIST
        assert self._is_asa_manager(asset_id), err.UNAUTHORIZED

    @arc4.abimethod
    def arc89_set_reversible_flag(
        self,
        *,
        asset_id: Asset,
        flag: arc4.UInt8,
        value: arc4.Bool,
    ) -> None:
        """
        Set a reversible Asset Metadata Flag, restricted to the ASA Manager Address

        Args:
            asset_id: The Asset ID to set the Metadata Flag for
            flag: The reversible flag index to set
            value: The flag value to set
        """
        # Preconditions
        self._check_set_flag_preconditions(asset_id)
        assert flag.as_uint64() <= flg.REV_FLG_RESERVED_7, err.FLAG_IDX_INVALID

        # Handle Not Idempotent
        existing_value = self._get_reversible_flag_value(asset_id, flag.as_uint64())
        if value.native != existing_value:
            # Set Reversible Flag
            self._set_reversible_flag_value(
                asset_id, flag.as_uint64(), value=value.native
            )

            # Update Metadata Header
            self._update_header_excluding_flags_and_emit(asset_id)

    @arc4.abimethod
    def arc89_set_irreversible_flag(
        self,
        *,
        asset_id: Asset,
        flag: arc4.UInt8,
    ) -> None:
        """
        Set an irreversible Asset Metadata Flag, restricted to the ASA Manager Address

        Args:
            asset_id: The Asset ID to set the Metadata Flag for
            flag: The irreversible flag index to set. WARNING: must be in 2 ... 6
        """
        # Preconditions
        self._check_set_flag_preconditions(asset_id)
        assert (
            flg.IRR_FLG_RESERVED_2 <= flag.as_uint64() <= flg.IRR_FLG_RESERVED_6
        ), err.FLAG_IDX_INVALID

        # Handle Not Idempotent
        existing_value = self._get_irreversible_flag_value(asset_id, flag.as_uint64())
        if not existing_value:
            # Set Irreversible Flag
            self._set_irreversible_flag_value(asset_id, flag.as_uint64())

            # Update Metadata Header
            self._update_header_excluding_flags_and_emit(asset_id)

    @arc4.abimethod
    def arc89_set_immutable(
        self,
        *,
        asset_id: Asset,
    ) -> None:
        """
        Set Asset Metadata as immutable, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to set immutable Asset Metadata for
        """
        # Preconditions
        self._check_set_flag_preconditions(asset_id)

        # Set Immutable Flag
        self._set_irreversible_flag_value(asset_id, UInt64(flg.IRR_FLG_IMMUTABLE))

        # Update Metadata Header
        self._update_header_excluding_flags_and_emit(asset_id)

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_registry_parameters(self) -> abi.RegistryParameters:
        """
        Return the ASA Metadata Registry parameters.

        Returns:
            Tuple of (HEADER_SIZE, MAX_METADATA_SIZE, SHORT_METADATA_SIZE, PAGE_SIZE,
            FIRST_PAYLOAD_MAX_SIZE, EXTRA_PAYLOAD_MAX_SIZE, REPLACE_PAYLOAD_MAX_SIZE, FLAT_MBR, BYTE_MBR)
        """
        return abi.RegistryParameters(
            header_size=arc4.UInt16(const.HEADER_SIZE),
            max_metadata_size=arc4.UInt16(const.MAX_METADATA_SIZE),
            short_metadata_size=arc4.UInt16(const.SHORT_METADATA_SIZE),
            page_size=arc4.UInt16(const.PAGE_SIZE),
            first_payload_max_size=arc4.UInt16(const.FIRST_PAYLOAD_MAX_SIZE),
            extra_payload_max_size=arc4.UInt16(const.EXTRA_PAYLOAD_MAX_SIZE),
            replace_payload_max_size=arc4.UInt16(const.REPLACE_PAYLOAD_MAX_SIZE),
            flat_mbr=arc4.UInt64(const.FLAT_MBR),
            byte_mbr=arc4.UInt64(const.BYTE_MBR),
        )

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_partial_uri(self) -> String:
        """
        Return the Asset Metadata ARC-90 partial URI, without compliance fragment (optional)

        Returns:
            Asset Metadata ARC-90 partial URI, without compliance fragment
        """
        return String.from_bytes(
            arc90_box_query(Global.current_application_id, Bytes())
        )

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_mbr_delta(
        self,
        *,
        asset_id: Asset,
        new_metadata_size: arc4.UInt16,
    ) -> abi.MbrDelta:
        """
        Return the Asset Metadata Box MBR Delta for an ASA, given a new Asset Metadata byte size.
        If the Asset Metadata Box does not exist, the creation MBR Delta is returned.

        Args:
            asset_id: The Asset ID to calculate the Asset Metadata MBR Delta for
            new_metadata_size: The new Asset Metadata byte size

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        # Preconditions
        assert (
            new_metadata_size.as_uint64() <= const.MAX_METADATA_SIZE
        ), err.EXCEEDS_MAX_METADATA_SIZE

        if self._metadata_exists(asset_id):
            metadata_size = self._get_metadata_size(asset_id)
            flat_mbr = UInt64(0)
            if new_metadata_size.as_uint64() == metadata_size:
                sign = UInt64(enums.MBR_DELTA_NULL)
                delta_size = UInt64(0)
            elif new_metadata_size.as_uint64() > metadata_size:
                sign = UInt64(enums.MBR_DELTA_POS)
                delta_size = new_metadata_size.as_uint64() - metadata_size
            else:
                sign = UInt64(enums.MBR_DELTA_NEG)
                delta_size = metadata_size - new_metadata_size.as_uint64()
        else:
            flat_mbr = UInt64(const.FLAT_MBR)
            sign = UInt64(enums.MBR_DELTA_POS)
            delta_size = (
                const.ASSET_METADATA_BOX_KEY_SIZE
                + const.HEADER_SIZE
                + new_metadata_size.as_uint64()
            )

        delta_amount = flat_mbr + const.BYTE_MBR * delta_size

        return abi.MbrDelta(sign=arc4.UInt8(sign), amount=arc4.UInt64(delta_amount))

    @arc4.abimethod(readonly=True)
    def arc89_check_metadata_exists(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MetadataExistence:
        """
        Checks whether the specified ASA exists and whether its associated Asset Metadata is available.

        Args:
            asset_id: The Asset ID to check the ASA and Asset Metadata existence for

        Returns:
            Tuple of (ASA exists, Asset Metadata exists)
        """
        return abi.MetadataExistence(
            asa_exists=arc4.Bool(self._asa_exists(asset_id)),
            metadata_exists=arc4.Bool(self._metadata_exists(asset_id)),
        )

    @arc4.abimethod(readonly=True)
    def arc89_is_metadata_immutable(
        self,
        *,
        asset_id: Asset,
    ) -> arc4.Bool:
        """
        Return True if the Asset Metadata for an ASA is immutable, False otherwise.

        Args:
            asset_id: The Asset ID to check the Asset Metadata immutability for

        Returns:
            Asset Metadata for the ASA is immutable
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        return arc4.Bool(
            self._is_immutable(asset_id) or asset_id.manager == Global.zero_address
        )

    @arc4.abimethod(readonly=True)
    def arc89_is_metadata_short(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MutableFlag:
        """
        Return True if Asset Metadata for an ASA is short (up to 4096 bytes), False otherwise.

        Args:
            asset_id: The Asset ID to check the Asset Metadata size classification for

        Returns:
            Tuple of (is short metadata, Metadata Last Modified Round)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        return abi.MutableFlag(
            flag=arc4.Bool(self._is_short(asset_id)),
            last_modified_round=arc4.UInt64(self._get_last_modified_round(asset_id)),
        )

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_header(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MetadataHeader:
        """
        Return the Asset Metadata Header for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata Header for

        Returns:
            Asset Metadata Header: (Identifiers, Reversible Flags, Irreversible Flags,
            Hash, Last Modified Round, Deprecated By)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        return abi.MetadataHeader(
            identifiers=arc4.Byte.from_bytes(self._get_metadata_identifiers(asset_id)),
            reversible_flags=arc4.Byte.from_bytes(self._get_reversible_flags(asset_id)),
            irreversible_flags=arc4.Byte.from_bytes(
                self._get_irreversible_flags(asset_id)
            ),
            hash=abi.Hash.from_bytes(self._get_metadata_hash(asset_id)),
            last_modified_round=arc4.UInt64(self._get_last_modified_round(asset_id)),
            deprecated_by=arc4.UInt64(self._get_deprecated_by(asset_id)),
        )

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_pagination(
        self,
        *,
        asset_id: Asset,
    ) -> abi.Pagination:
        """Return the Asset Metadata pagination for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata pagination for

        Returns:
            Tuple of (total metadata byte size, PAGE_SIZE, total number of pages)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        return abi.Pagination(
            metadata_size=arc4.UInt16(self._get_metadata_size(asset_id)),
            page_size=arc4.UInt16(const.PAGE_SIZE),
            total_pages=arc4.UInt8(self._get_total_pages(asset_id)),
        )

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata(
        self,
        *,
        asset_id: Asset,
        page: arc4.UInt8,
    ) -> abi.PaginatedMetadata:
        """
        Return paginated Asset Metadata (without Header) for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata for
            page: The 0-based Metadata page number

        Returns:
            Tuple of (has next page, Metadata Last Modified Round, page content)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)
        total_pages = self._get_total_pages(asset_id)
        if total_pages > 0:
            assert page.as_uint64() < total_pages, err.PAGE_IDX_INVALID
            has_next_page = page.as_uint64() < total_pages - 1
            page_content = self._get_metadata_page(asset_id, page.as_uint64())
        else:
            assert page.as_uint64() == 0, err.PAGE_IDX_INVALID
            has_next_page = False
            page_content = Bytes()

        return abi.PaginatedMetadata(
            has_next_page=arc4.Bool(has_next_page),
            last_modified_round=arc4.UInt64(self._get_last_modified_round(asset_id)),
            page_content=arc4.DynamicBytes(page_content),
        )

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_slice(
        self,
        *,
        asset_id: Asset,
        offset: arc4.UInt16,
        size: arc4.UInt16,
    ) -> Bytes:
        """
        Return a slice of the Asset Metadata for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata slice for
            offset: The 0-based byte offset within the Metadata (body) bytes
            size: The slice bytes size to return

        Returns:
            Asset Metadata slice (size limited to PAGE_SIZE)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)
        assert size.as_uint64() <= const.PAGE_SIZE, err.EXCEEDS_PAGE_SIZE
        assert offset.as_uint64() + size.as_uint64() <= self._get_metadata_size(
            asset_id
        ), err.EXCEEDS_METADATA_SIZE

        metadata_slice = self.asset_metadata.box(asset_id).extract(
            start_index=const.IDX_METADATA + offset.as_uint64(), length=size.as_uint64()
        )
        return metadata_slice

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_header_hash(
        self,
        *,
        asset_id: Asset,
    ) -> abi.Hash:
        """
        Return the Metadata Header Hash for an ASA.

        Args:
            asset_id: The Asset ID to get the Metadata Header Hash for

        Returns:
            Asset Metadata Header Hash
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        return abi.Hash.from_bytes(self._compute_header_hash(asset_id))

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_page_hash(
        self,
        *,
        asset_id: Asset,
        page: arc4.UInt8,
    ) -> abi.Hash:
        """
        Return the SHA512-256 of a Metadata page for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata page hash for
            page: The 0-based Metadata page number

        Returns:
            The SHA512-256 of the Metadata page
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)
        total_pages = self._get_total_pages(asset_id)
        if total_pages > 0:
            assert page.as_uint64() < total_pages, err.PAGE_IDX_INVALID
        else:
            assert False, err.EMPTY_METADATA  # noqa: B011

        page_content = self._get_metadata_page(asset_id, page.as_uint64())
        page_hash = self._compute_page_hash(asset_id, page.as_uint64(), page_content)
        return abi.Hash.from_bytes(page_hash)

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_hash(
        self,
        *,
        asset_id: Asset,
    ) -> abi.Hash:
        """
        Return the Metadata Hash for an ASA.

        Args:
            asset_id: The Asset ID to get the Metadata Hash for

        Returns:
            Asset Metadata Hash
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        return abi.Hash.from_bytes(self._get_metadata_hash(asset_id))

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_string_by_key(
        self,
        *,
        asset_id: Asset,
        key: arc4.String,
    ) -> String:
        """
        Return the UTF-8 string value for a top-level JSON key of type JSON String
        from short Metadata for an ASA; errors if the key does not exist or is not
        a JSON String

        Args:
            asset_id: The Asset ID to get the key value for
            key: The top level JSON key whose string value to fetch

        Returns:
            The string value from valid UTF-8 JSON Metadata (size limited to PAGE_SIZE)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        # Fetch key's value
        # ⚠️ WARNING: The following conditions cause AVM runtime error:
        # - The short Metadata is not a valid UTF-8 encoded JSON object
        # - The top-level key does not exist
        # - The top-level key's value is not a JSON String
        obj = self._get_short_metadata(asset_id)
        value = op.JsonRef.json_string(obj, key.native.bytes)

        # Postconditions
        assert value.length <= const.PAGE_SIZE, err.EXCEEDS_PAGE_SIZE

        return String.from_bytes(value)

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_uint64_by_key(
        self,
        *,
        asset_id: Asset,
        key: arc4.String,
    ) -> arc4.UInt64:
        """
        Return the uint64 value for a top-level JSON key of type JSON Uint64 from
        short Metadata for an ASA; errors if the key does not exist or is not a JSON
        Uint64

        Args:
            asset_id: The Asset ID to get the key value for
            key: The top level JSON key whose uint64 value to fetch

        Returns:
            The uint64 value from valid UTF-8 JSON Metadata
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        # Fetch key's value
        # ⚠️ WARNING: The following conditions cause AVM runtime error:
        # - The short Metadata is not a valid UTF-8 encoded JSON object
        # - The top-level key does not exist
        # - The top-level key's value is not a JSON Uint64
        obj = self._get_short_metadata(asset_id)
        value = op.JsonRef.json_uint64(obj, key.native.bytes)

        return arc4.UInt64(value)

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_object_by_key(
        self,
        *,
        asset_id: Asset,
        key: arc4.String,
    ) -> String:
        """
        Return the UTF-8 object value for a top-level JSON key of type JSON Object
        from short Metadata for an ASA; errors if the key does not exist or is not
        a JSON Object

        Args:
            asset_id: The Asset ID to get the key value for
            key: The top level JSON key whose object value to fetch

        Returns:
            The object value from valid UTF-8 JSON Metadata (size limited to PAGE_SIZE)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)

        # Fetch key's value
        # ⚠️ WARNING: The following conditions cause AVM runtime error:
        # - The short Metadata is not a valid UTF-8 encoded JSON object
        # - The top-level key does not exist
        # - The top-level key's value is not a JSON Object
        obj = self._get_short_metadata(asset_id)
        value = op.JsonRef.json_object(obj, key.native.bytes)

        # Postconditions
        assert value.length <= const.PAGE_SIZE, err.EXCEEDS_PAGE_SIZE

        return String.from_bytes(value)

    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_b64_bytes_by_key(
        self, *, asset_id: Asset, key: arc4.String, b64_encoding: arc4.UInt8
    ) -> Bytes:
        """
        Return the base64-decoded bytes for a top-level JSON key of type JSON String
        from short Metadata for an ASA; errors if the key does not exist, is not
        a JSON String, or is not valid base64 for the chosen encoding

        Args:
            asset_id: The Asset ID to get the key value for
            key: The top-level JSON key whose base64 string value to fetch and decode
            b64_encoding: base64 encoding enum: 0 = URLEncoding, 1 = StdEncoding

        Returns:
            The base64-decoded bytes from valid UTF-8 JSON Metadata (size limited to PAGE_SIZE)
        """
        # Preconditions
        self._check_existence_preconditions(asset_id)
        assert (
            b64_encoding.as_uint64() <= enums.B64_STD_ENCODING
        ), err.B64_ENCODING_INVALID

        # Fetch key's value
        # ⚠️ WARNING: The following conditions cause AVM runtime error:
        # - The short Metadata is not a valid UTF-8 encoded JSON object
        # - The top-level key does not exist
        # - The top-level key's value is not a JSON String
        obj = self._get_short_metadata(asset_id)
        value = op.JsonRef.json_string(obj, key.native.bytes)

        # Decode value
        # ⚠️ WARNING: The following conditions cause AVM runtime error:
        # - The top-level key's value is not a valid base64-encoding string for
        # the chosen encoding.
        if b64_encoding.as_uint64() == enums.B64_URL_ENCODING:
            decoded_value = op.base64_decode(op.Base64.URLEncoding, value)
        else:
            decoded_value = op.base64_decode(op.Base64.StdEncoding, value)

        # Postconditions
        assert decoded_value.length <= const.PAGE_SIZE, err.EXCEEDS_PAGE_SIZE

        return decoded_value

    @arc4.abimethod
    def extra_resources(self) -> None:
        """
        Non-normative placeholder method to acquire AVM extra resources.
        """
        pass

    @arc4.abimethod
    def withdraw_balance_excess(self) -> None:
        """
        Non-normative method to withdraw balance excess due to accidental deposits
        (it should never happen if deposits match exactly the required MBR. Deleted
        metadata MBR is not included in the excess, since it is immediately returned
        on delete).
        """
        excess_balance = (
            Global.current_application_address.balance
            - Global.current_application_address.min_balance
        )
        itxn.Payment(
            receiver=Global.creator_address,
            amount=excess_balance,
        ).submit()
