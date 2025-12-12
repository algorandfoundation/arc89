from algopy import Account, Asset, BoxMap, Bytes, Global, OnCompleteAction, TemplateVar, TransactionType, Txn, UInt64, arc4, itxn, gtxn, op, urange, subroutine, ensure_budget

from . import abi_types as abi
from . import bitmasks as masks
from . import constants as const
from . import enums as enums
from . import errors as err
from .interface import AsaMetadataRegistryInterface
from .template_vars import TRUSTED_DEPLOYER


class AsaMetadataRegistry(AsaMetadataRegistryInterface):
    """
    Singleton Application providing ASA metadata via Algod API and AVM
    """
    def __init__(self) -> None:
        self.asset_metadata = BoxMap(Asset, Bytes, key_prefix="")

    @subroutine
    def _asa_exists(self, asa: Asset) -> bool:
        return asa.creator != Global.zero_address

    @subroutine
    def _metadata_exists(self, asa: Asset) -> bool:
        return asa in self.asset_metadata

    @subroutine
    def _is_asa_manager(self, asa: Asset) -> bool:
        return Txn.sender == asa.manager

    @subroutine
    def _is_valid_max_metadata_size(self, metadata_size: UInt64) -> bool:
        return metadata_size <= const.MAX_METADATA_SIZE

    @subroutine
    def _is_short_metadata_size(self, metadata_size: UInt64) -> bool:
        return metadata_size <= const.SHORT_METADATA_SIZE

    @subroutine
    def _has_bits(self, bits: UInt64, mask: UInt64) -> bool:
        # AVM bitwise operations on UInt64 are more efficient than on Bytes
        return (bits & mask) != 0

    @subroutine
    def _set_bits(self, bits: UInt64, mask: UInt64, value: bool) -> UInt64:
        # AVM bitwise operations on UInt64 are more efficient than on Bytes
        return (bits | mask) if value else (bits & ~mask)

    @subroutine
    def _trimmed_itob(self, a: UInt64, size: UInt64) -> Bytes:
        """
        Return exactly `size` rightmost bytes of the 8-byte big-endian itob(a).
        Size is assumed to be 1 (UInt8), 2 (UInt16), or 4 (UInt32) bytes.
        """
        start = UInt64(const.UINT64_SIZE) - size  # left-trim offset
        return op.extract(op.itob(a), start, size)

    @subroutine
    def _umin(self, a: UInt64, b: UInt64) -> UInt64:
        return a if a < b else b

    @subroutine
    def _ceil_div(self, n: UInt64, d: UInt64) -> UInt64:
        # Assumes d >= 1
        return (n + (d - 1)) // d

    @subroutine
    def itoa(self, n: UInt64) -> Bytes:
        # ASCII digits (valid UTF-8)
        digits = Bytes(b"0123456789")
        acc = Bytes(b"")

        while n > 0:
            d = n % UInt64(10)
            acc = digits[d:d + UInt64(1)] + acc
            n //= UInt64(10)

        return acc or Bytes(b"0")

    @subroutine
    def _get_metadata_identifiers(self, asa: Asset) -> Bytes:
        """Return the 1-byte Metadata Identifiers for an ASA."""
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_METADATA_IDENTIFIERS,
            length=const.METADATA_IDENTIFIERS_SIZE
        )

    @subroutine
    def _set_metadata_identifiers(self, asa: Asset, identifiers: Bytes) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_METADATA_IDENTIFIERS,
            value=identifiers
        )

    @subroutine
    def _get_metadata_flags(self, asa: Asset) -> Bytes:
        """Return the 1-byte Metadata Identifiers for an ASA."""
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_METADATA_FLAGS,
            length=const.METADATA_FLAGS_SIZE
        )

    @subroutine
    def _set_metadata_flags(self, asa: Asset, flags: Bytes) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_METADATA_FLAGS,
            value=flags
        )

    @subroutine
    def _is_short(self, asa: Asset) -> bool:
        return self._has_bits(
            op.btoi(self._get_metadata_identifiers(asa)),
            UInt64(masks.ID_SHORT)
        )

    @subroutine
    def _is_arc3(self, asa: Asset) -> bool:
        return self._has_bits(
            op.btoi(self._get_metadata_flags(asa)),
            UInt64(masks.FLG_ARC3)
        )

    @subroutine
    def _is_arc20(self, asa: Asset) -> bool:
        return self._has_bits(
            op.btoi(self._get_metadata_flags(asa)),
            UInt64(masks.FLG_ARC20)
        )

    @subroutine
    def _is_arc62(self, asa: Asset) -> bool:
        return self._has_bits(
            op.btoi(self._get_metadata_flags(asa)),
            UInt64(masks.FLG_ARC62)
        )

    @subroutine
    def _is_arc89(self, asa: Asset) -> bool:
        return self._has_bits(
            op.btoi(self._get_metadata_flags(asa)),
            UInt64(masks.FLG_ARC89_NATIVE)
        )

    @subroutine
    def _is_immutable(self, asa: Asset) -> bool:
        return self._has_bits(
            op.btoi(self._get_metadata_flags(asa)),
            UInt64(masks.FLG_IMMUTABLE)
        )

    @subroutine
    def _get_metadata_hash(self, asa: Asset) -> Bytes:
        return self.asset_metadata.box(asa).extract(
            start_index=const.IDX_METADATA_HASH,
            length=const.METADATA_HASH_SIZE
        )

    @subroutine
    def _set_metadata_hash(self, asa: Asset, metadata_hash: Bytes) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_METADATA_HASH,
            value=metadata_hash
        )

    @subroutine
    def _get_last_modified_round(self, asa: Asset) -> UInt64:
        return op.btoi(
            self.asset_metadata.box(asa).extract(
                start_index=const.IDX_LAST_MODIFIED_ROUND,
                length=const.LAST_MODIFIED_ROUND_SIZE
            )
        )

    @subroutine
    def _set_last_modified_round(self, asa: Asset, last_modified_round: UInt64) -> None:
        self.asset_metadata.box(asa).replace(
            start_index=const.IDX_LAST_MODIFIED_ROUND,
            value=op.itob(last_modified_round)
        )

    @subroutine
    def _get_metadata_size(self, asa: Asset) -> UInt64:
        return self.asset_metadata.box(asa).length - const.METADATA_HEADER_SIZE

    @subroutine
    def _append_payload(self, asa: Asset, payload: Bytes) -> None:
        old_asset_metadata_box_size = self.asset_metadata.box(asa).length
        self.asset_metadata.box(asa).resize(
            new_size=old_asset_metadata_box_size + payload.length
        )
        self.asset_metadata.box(asa).replace(
            start_index=old_asset_metadata_box_size - 1,
            value=payload
        )

    @subroutine
    def _is_extra_payload_txn(self, txn: gtxn.Transaction) -> bool:
        return (
            txn.type == TransactionType.ApplicationCall
            and txn.app_id == Global.current_application_id
            and txn.on_completion == OnCompleteAction.NoOp
            and txn.app_args(0) == arc4.arc4_signature(AsaMetadataRegistryInterface.arc89_extra_payload)
        )

    @subroutine
    def _read_extra_payload(self, txn: gtxn.Transaction) -> Bytes:
        # This subroutine assumes txn is already validated as an extra payload txn
        return arc4.DynamicBytes.from_bytes(
            txn.app_args(const.ARC89_EXTRA_PAYLOAD_ARG_PAYLOAD)
        ).native

    @subroutine
    def _set_metadata_payload(self, asa: Asset, metadata_size: UInt64, payload: Bytes) -> None:
        # Append provided payload
        self._append_payload(asa, payload)

        # Append staged extra payload (in the same Group, if any)
        group_size = Global.group_size
        group_index = Txn.group_index
        for idx in urange(group_index + 1, group_size):
            txn = gtxn.Transaction(idx)
            if self._is_extra_payload_txn(txn):
                extra_payload = self._read_extra_payload(txn)
                assert self._get_metadata_size(asa) + extra_payload.length <= metadata_size, err.PAYLOAD_OVERFLOW
                self._append_payload(asa, extra_payload)
        assert self._get_metadata_size(asa) == metadata_size, err.METADATA_SIZE_MISMATCH

    @subroutine
    def _get_total_pages(self, asa: Asset) -> UInt64:
        """
        Total page count, allowing 0 pages for empty metadata.
        ceil(metadata_size / PAGE_SIZE)
        """
        n = self._get_metadata_size(asa)
        return self._ceil_div(n, UInt64(const.PAGE_SIZE))

    @subroutine
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
        length = self._umin(ps, remaining)

        return self.asset_metadata.box(asa).extract(
            start_index=start,
            length=length
        )

    @subroutine
    def _identify_metadata(self, asset_id: Asset, metadata_size: UInt64) -> None:
        identifiers = self._trimmed_itob(
            self._set_bits(
                op.btoi(self._get_metadata_identifiers(asset_id)),
                UInt64(masks.ID_SHORT),
                self._is_short_metadata_size(metadata_size)
            ),
            size=UInt64(const.UINT8_SIZE),
        )
        self._set_metadata_identifiers(asset_id, identifiers)

    @subroutine
    def _compute_header_hash(self, asa: Asset) -> Bytes:
        # hh = SHA - 512 / 256("arc0089/header" || Asset ID || Metadata Identifiers || Metadata Flags || Metadata Size)
        domain = Bytes(const.HASH_DOMAIN_HEADER)
        asset_id = op.itob(asa.id)
        metadata_identifiers = self._get_metadata_identifiers(asa)
        metadata_flags = self._get_metadata_flags(asa)
        metadata_size = self._trimmed_itob(
            self._get_metadata_size(asa),
            size=UInt64(const.UINT16_SIZE),
        )
        return op.sha512_256(
            domain
            +asset_id
            +metadata_identifiers
            +metadata_flags
            +metadata_size
        )

    @subroutine
    def _compute_page_hash(self, asa: Asset, page_index: UInt64, page_content: Bytes) -> Bytes:
        # ph[i] = SHA-512/256("arc0089/page" || Asset ID || Page Index || Page Size || Page Content)
        domain = Bytes(const.HASH_DOMAIN_PAGE)
        asset_id = op.itob(asa.id)
        page_idx = self._trimmed_itob(page_index, UInt64(const.UINT8_SIZE))
        page_size = self._trimmed_itob(page_content.length, UInt64(const.UINT16_SIZE))
        return op.sha512_256(
            domain
            + asset_id
            + page_idx
            + page_size
            + page_content
        )

    @subroutine
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

    @subroutine
    def _check_base_preconditions(self, asa: Asset, metadata_size: UInt64) -> None:
        assert self._asa_exists(asa), err.ASA_NOT_EXIST
        assert self._is_asa_manager(asa), err.UNAUTHORIZED
        assert self._is_valid_max_metadata_size(metadata_size), err.EXCEEDS_MAX_METADATA_SIZE

    @subroutine
    def _check_update_preconditions(self, asa: Asset, metadata_size: UInt64) -> None:
        self._check_base_preconditions(asa, metadata_size)
        assert self._metadata_exists(asa), err.ASSET_METADATA_NOT_EXIST
        assert not self._is_immutable(asa), err.IMMUTABLE

    @arc4.baremethod(create="require")
    def arc89_deploy(self) -> None:
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
        flags: arc4.Byte,
        metadata_size: arc4.UInt16,
        payload: arc4.DynamicBytes,
        mbr_delta_payment: gtxn.PaymentTransaction,
    ) -> abi.MbrDelta:
        """
        Create Asset Metadata for an existing ASA, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to create the Asset Metadata for
            flags: The Metadata Flags. WARNING: if the MSB is True the Asset Metadata is IMMUTABLE
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

        # MBR Payment pre-validation
        assert mbr_delta_payment.receiver == Global.current_application_address, err.MBR_DELTA_RECEIVER_INVALID

        # Initialize Asset Metadata Box Header
        mbr_i = Global.current_application_address.min_balance
        _exists = self.asset_metadata.box(asset_id).create(size=UInt64(const.METADATA_HEADER_SIZE))

        # Set Metadata Header (without Metadata Hash, computed after payload upload)
        self._identify_metadata(asset_id, metadata_size.as_uint64())
        self._set_metadata_flags(asset_id, self._trimmed_itob(flags.as_uint64(), size=UInt64(const.BYTE_SIZE)))
        self._set_last_modified_round(asset_id, Global.round)

        # Set Metadata Body
        if payload.native.length > 0:
            ensure_budget(required_budget=const.APP_CALL_OP_CODE_BUDGET)
        self._set_metadata_payload(asset_id, metadata_size.as_uint64(), payload.native)

        # Postconditions
        if self._is_arc89(asset_id):
            arc_89_uri = (
                const.URI_ARC_89_PREFIX
                + self.itoa(Global.current_application_id.id)
                + const.URI_ARC_89_SUFFIX
            )
            asa_url = asset_id.url
            assert asa_url[:arc_89_uri.length] == arc_89_uri, err.ASA_URL_INVALID_ARC89_URI

        if asset_id.metadata_hash != Bytes(const.BYTES32_SIZE * b'\x00'):  # Not empty metadata hash
            assert self._is_immutable(asset_id), err.REQUIRES_IMMUTABLE
            metadata_hash = asset_id.metadata_hash
        else:
            metadata_hash = self._compute_metadata_hash(asset_id)
        self._set_metadata_hash(asset_id, metadata_hash)

        mbr_delta_amount = Global.current_application_address.min_balance - mbr_i
        assert mbr_delta_payment.amount >= mbr_delta_amount, err.MBR_DELTA_AMOUNT_INVALID

        arc4.emit(
            abi.Arc89MetadataUpdated(
                asset_id=arc4.UInt64(asset_id.id),
                round=arc4.UInt64(Global.round),
                timestamp=arc4.UInt64(Global.latest_timestamp),
                flags=flags,
                is_short=arc4.Bool(self._is_short(asset_id)),
                hash=abi.Hash.from_bytes(metadata_hash),
            )
        )

        return abi.MbrDelta(sign=arc4.UInt8(enums.MBR_DELTA_POS), amount=arc4.UInt64(mbr_delta_amount))

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
        assert metadata_size.as_uint64() <= self._get_metadata_size(asset_id), err.LARGER_METADATA_SIZE

        # Update Metadata Header (without Metadata Hash, computed after payload upload)
        self._identify_metadata(asset_id, metadata_size.as_uint64())
        self._set_last_modified_round(asset_id, Global.round)

        # Update Metadata Body
        mbr_i = Global.current_application_address.min_balance
        self.asset_metadata.box(asset_id).resize(new_size=UInt64(const.METADATA_HEADER_SIZE))
        self._set_metadata_payload(asset_id, metadata_size.as_uint64(), payload.native)

        # Postconditions
        assert self._get_metadata_size(asset_id) == metadata_size.as_uint64(), err.METADATA_SIZE_MISMATCH
        metadata_hash = self._compute_metadata_hash(asset_id)
        self._set_metadata_hash(asset_id, metadata_hash)

        mbr_delta_amount = mbr_i - Global.current_application_address.min_balance
        if mbr_delta_amount == 0:
            sign = UInt64(enums.MBR_DELTA_NULL)
        else:
            sign = UInt64(enums.MBR_DELTA_NEG)
            itxn.Payment(
                receiver=asset_id.manager,
                amount=mbr_delta_amount,
            ).submit()

        arc4.emit(
            abi.Arc89MetadataUpdated(
                asset_id=arc4.UInt64(asset_id.id),
                round=arc4.UInt64(Global.round),
                timestamp=arc4.UInt64(Global.latest_timestamp),
                flags=arc4.Byte(op.btoi(self._get_metadata_flags(asset_id))),
                is_short=arc4.Bool(self._is_short(asset_id)),
                hash=abi.Hash.from_bytes(metadata_hash),
            )
        )

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
        assert metadata_size.as_uint64() > self._get_metadata_size(asset_id), err.SMALLER_METADATA_SIZE

        # Update Metadata Header (without Metadata Hash, computed after payload upload)
        self._identify_metadata(asset_id, metadata_size.as_uint64())
        self._set_last_modified_round(asset_id, Global.round)

        # Update Metadata Body
        mbr_i = Global.current_application_address.min_balance
        self.asset_metadata.box(asset_id).resize(new_size=UInt64(const.METADATA_HEADER_SIZE))
        self._set_metadata_payload(asset_id, metadata_size.as_uint64(),payload.native)

        # Postconditions
        assert self._get_metadata_size(asset_id) == metadata_size.as_uint64(), err.METADATA_SIZE_MISMATCH
        metadata_hash = self._compute_metadata_hash(asset_id)
        self._set_metadata_hash(asset_id, metadata_hash)

        mbr_delta_amount = Global.current_application_address.min_balance - mbr_i
        assert mbr_delta_payment.amount >= mbr_delta_amount, err.MBR_DELTA_AMOUNT_INVALID

        arc4.emit(
            abi.Arc89MetadataUpdated(
                asset_id=arc4.UInt64(asset_id.id),
                round=arc4.UInt64(Global.round),
                timestamp=arc4.UInt64(Global.latest_timestamp),
                flags=arc4.Byte(op.btoi(self._get_metadata_flags(asset_id))),
                is_short=arc4.Bool(self._is_short(asset_id)),
                hash=abi.Hash.from_bytes(metadata_hash),
            )
        )

        return abi.MbrDelta(sign=arc4.UInt8(enums.MBR_DELTA_POS), amount=arc4.UInt64(mbr_delta_amount))

    @arc4.abimethod
    def arc89_extra_payload(
        self,
        *,
        asset_id: Asset,
        payload: arc4.DynamicBytes,
    ) -> None:
        """Concatenate extra payload to Asset Metadata head call methods (creation or replacement).

        Args:
            asset_id: The Asset ID to provide Metadata extra payload for
            payload: The Metadata extra payload to concatenate
        """
        # Preconditions
        assert self._asa_exists(asset_id), err.ASA_NOT_EXIST
        assert self._metadata_exists(asset_id), err.ASSET_METADATA_NOT_EXIST
        assert self._is_asa_manager(asset_id), err.UNAUTHORIZED
