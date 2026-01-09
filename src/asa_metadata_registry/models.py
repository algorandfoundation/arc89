from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from . import bitmasks, enums
from . import constants as const
from .errors import BoxParseError, InvalidPageIndexError, MetadataHashMismatchError
from .hashing import (
    MAX_UINT8,
    compute_header_hash,
    compute_metadata_hash,
    compute_page_hash,
)
from .validation import (
    decode_metadata_json,
    encode_metadata_json,
    is_arc3_metadata,
    validate_arc3_schema,
)

# Type aliases for ABI tuple values
AbiValue = int | bytes | bool | Sequence["AbiValue"]

# Module-level cached default registry parameters (frozen dataclass; safe to share)
_DEFAULT_REGISTRY_PARAMS: RegistryParameters | None = None


def get_default_registry_params() -> RegistryParameters:
    """
    Get cached default registry parameters.

    Returns a singleton instance of the default RegistryParameters to avoid
    repeatedly creating the same object.
    """
    global _DEFAULT_REGISTRY_PARAMS
    if _DEFAULT_REGISTRY_PARAMS is None:
        _DEFAULT_REGISTRY_PARAMS = RegistryParameters.defaults()
    return _DEFAULT_REGISTRY_PARAMS


def _set_bit(*, bits: int, mask: int, value: bool) -> int:
    """Set/clear `mask` within an 8-bit integer and return the 0..255 result."""
    return (bits | mask) if value else (bits & ~mask & 0xFF)


def _coerce_bytes(v: object, *, name: str) -> bytes:
    """
    Coerce Algod/ABI values into `bytes`.

    AVM/Algod commonly returns byte arrays as `bytes` or as `list[int]`.
    We accept any non-bytes sequence of ints for a bit of extra robustness.
    """
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        # Best-effort: if this is not a sequence of ints, `bytes(...)` will raise.
        try:
            return bytes(v)
        except Exception as e:
            raise TypeError(f"{name} must be bytes or a sequence of ints") from e
    raise TypeError(f"{name} must be bytes or a sequence of ints")


def _is_nonzero_32(am: bytes) -> bool:
    """True if am is 32 bytes and not all-zero."""
    return len(am) == 32 and any(b != 0 for b in am)


def _chunk_metadata_payload(
    data: bytes,
    *,
    head_max_size: int,
    extra_max_size: int,
) -> list[bytes]:
    """
    Chunk the metadata payload into a head chunk and zero or more extra chunks.

    This is a pure splitting helper; size validation is handled elsewhere.
    """
    if head_max_size <= 0 or extra_max_size <= 0:
        raise ValueError("Chunk sizes must be > 0")

    if len(data) <= head_max_size:
        return [data]

    chunks = [data[:head_max_size]]
    i = head_max_size
    while i < len(data):
        chunks.append(data[i : i + extra_max_size])
        i += extra_max_size
    return chunks


class MbrDeltaSign(enum.IntEnum):
    NULL = enums.MBR_DELTA_NULL
    POS = enums.MBR_DELTA_POS
    NEG = enums.MBR_DELTA_NEG


@dataclass(frozen=True, slots=True)
class MbrDelta:
    sign: MbrDeltaSign
    amount: int  # microALGO

    @property
    def is_positive(self) -> bool:
        return self.sign == MbrDeltaSign.POS and self.amount > 0

    @property
    def is_negative(self) -> bool:
        return self.sign == MbrDeltaSign.NEG and self.amount > 0

    @property
    def is_zero(self) -> bool:
        return self.sign == MbrDeltaSign.NULL or self.amount == 0

    @property
    def signed_amount(self) -> int:
        if self.is_positive:
            return self.amount
        if self.is_negative:
            return -self.amount
        return 0

    @staticmethod
    def from_tuple(value: Sequence[int]) -> MbrDelta:
        if len(value) != 2:
            raise ValueError("Expected (sign, amount)")
        if value[0] not in (
            enums.MBR_DELTA_NULL,
            enums.MBR_DELTA_POS,
            enums.MBR_DELTA_NEG,
        ):
            raise ValueError(f"Invalid MBR delta sign: {value[0]}")
        if int(value[1]) < 0:
            raise ValueError("MBR delta amount must be non-negative")
        return MbrDelta(sign=MbrDeltaSign(int(value[0])), amount=int(value[1]))


@dataclass(frozen=True, slots=True)
class RegistryParameters:
    key_size: int
    header_size: int
    max_metadata_size: int
    short_metadata_size: int
    page_size: int
    first_payload_max_size: int
    extra_payload_max_size: int
    replace_payload_max_size: int
    flat_mbr: int
    byte_mbr: int

    @staticmethod
    def defaults() -> RegistryParameters:
        return RegistryParameters(
            key_size=const.ASSET_METADATA_BOX_KEY_SIZE,
            header_size=const.HEADER_SIZE,
            max_metadata_size=const.MAX_METADATA_SIZE,
            short_metadata_size=const.SHORT_METADATA_SIZE,
            page_size=const.PAGE_SIZE,
            first_payload_max_size=const.FIRST_PAYLOAD_MAX_SIZE,
            extra_payload_max_size=const.EXTRA_PAYLOAD_MAX_SIZE,
            replace_payload_max_size=const.REPLACE_PAYLOAD_MAX_SIZE,
            flat_mbr=const.FLAT_MBR,
            byte_mbr=const.BYTE_MBR,
        )

    @staticmethod
    def from_tuple(value: Sequence[int]) -> RegistryParameters:
        if len(value) != 10:
            raise ValueError("Expected 10-tuple of registry parameters")
        return RegistryParameters(
            key_size=int(value[0]),
            header_size=int(value[1]),
            max_metadata_size=int(value[2]),
            short_metadata_size=int(value[3]),
            page_size=int(value[4]),
            first_payload_max_size=int(value[5]),
            extra_payload_max_size=int(value[6]),
            replace_payload_max_size=int(value[7]),
            flat_mbr=int(value[8]),
            byte_mbr=int(value[9]),
        )

    def mbr_for_box(self, metadata_size: int) -> int:
        """
        Compute the minimum balance requirement for a metadata box holding `metadata_size` bytes.
        """
        if metadata_size < 0:
            raise ValueError("metadata_size must be non-negative")
        return self.flat_mbr + self.byte_mbr * (
            self.key_size + self.header_size + metadata_size
        )

    def mbr_delta(
        self,
        *,
        old_metadata_size: int | None,
        new_metadata_size: int,
        delete: bool = False,
    ) -> MbrDelta:
        """
        Compute MBR delta from old->new box size using the registry MBR parameters.

        - If old_metadata_size is None, this is treated as creating a new box.
        - If delete=True, this is treated as deleting the old box (new_metadata_size must be 0).
        """
        if new_metadata_size < 0:
            raise ValueError("new_metadata_size must be non-negative")

        old_mbr = (
            0 if old_metadata_size is None else self.mbr_for_box(old_metadata_size)
        )
        new_mbr = self.mbr_for_box(new_metadata_size)
        delta = new_mbr - old_mbr

        if delete:
            if old_metadata_size is None:
                raise ValueError("old_metadata_size must be provided when delete=True")
            if new_metadata_size != 0:
                raise ValueError("new_metadata_size must be 0 when delete=True")
            delta = -self.mbr_for_box(old_metadata_size)

        if delta == 0:
            return MbrDelta(MbrDeltaSign.NULL, 0)
        if delta > 0:
            return MbrDelta(MbrDeltaSign.POS, delta)
        return MbrDelta(MbrDeltaSign.NEG, abs(delta))


@dataclass(frozen=True, slots=True)
class MetadataExistence:
    asa_exists: bool
    metadata_exists: bool

    @staticmethod
    def from_tuple(value: Sequence[bool]) -> MetadataExistence:
        if len(value) != 2:
            raise ValueError("Expected (asa_exists, metadata_exists)")
        return MetadataExistence(
            asa_exists=bool(value[0]), metadata_exists=bool(value[1])
        )


@dataclass(frozen=True, slots=True)
class ReversibleFlags:
    """
    Reversible flags byte for ARC-89 metadata.

    Can be constructed from:
    - A raw byte value: ReversibleFlags.from_byte(0b00000011)
    - Individual flags: ReversibleFlags(arc20=True, arc62=True)
    """

    arc20: bool = False
    arc62: bool = False
    reserved_2: bool = False
    reserved_3: bool = False
    reserved_4: bool = False
    reserved_5: bool = False
    reserved_6: bool = False
    reserved_7: bool = False

    @property
    def byte_value(self) -> int:
        value = 0
        if self.arc20:
            value |= bitmasks.MASK_REV_ARC20
        if self.arc62:
            value |= bitmasks.MASK_REV_ARC62
        if self.reserved_2:
            value |= bitmasks.MASK_REV_RESERVED_2
        if self.reserved_3:
            value |= bitmasks.MASK_REV_RESERVED_3
        if self.reserved_4:
            value |= bitmasks.MASK_REV_RESERVED_4
        if self.reserved_5:
            value |= bitmasks.MASK_REV_RESERVED_5
        if self.reserved_6:
            value |= bitmasks.MASK_REV_RESERVED_6
        if self.reserved_7:
            value |= bitmasks.MASK_REV_RESERVED_7
        return value

    @staticmethod
    def from_byte(value: int) -> ReversibleFlags:
        if not 0 <= value <= MAX_UINT8:
            raise ValueError(f"Byte value must be 0-255, got {value}")
        return ReversibleFlags(
            arc20=bool(value & bitmasks.MASK_REV_ARC20),
            arc62=bool(value & bitmasks.MASK_REV_ARC62),
            reserved_2=bool(value & bitmasks.MASK_REV_RESERVED_2),
            reserved_3=bool(value & bitmasks.MASK_REV_RESERVED_3),
            reserved_4=bool(value & bitmasks.MASK_REV_RESERVED_4),
            reserved_5=bool(value & bitmasks.MASK_REV_RESERVED_5),
            reserved_6=bool(value & bitmasks.MASK_REV_RESERVED_6),
            reserved_7=bool(value & bitmasks.MASK_REV_RESERVED_7),
        )

    @staticmethod
    def empty() -> ReversibleFlags:
        return ReversibleFlags()


@dataclass(frozen=True, slots=True)
class IrreversibleFlags:
    """
    Irreversible flags byte for ARC-89 metadata.

    Can be constructed from:
    - A raw byte value: IrreversibleFlags.from_byte(0b10000001)
    - Individual flags: IrreversibleFlags(arc3=True, immutable=True)
    """

    arc3: bool = False
    arc89_native: bool = False
    reserved_2: bool = False
    reserved_3: bool = False
    reserved_4: bool = False
    reserved_5: bool = False
    reserved_6: bool = False
    immutable: bool = False

    @property
    def byte_value(self) -> int:
        value = 0
        if self.arc3:
            value |= bitmasks.MASK_IRR_ARC3
        if self.arc89_native:
            value |= bitmasks.MASK_IRR_ARC89_NATIVE
        if self.reserved_2:
            value |= bitmasks.MASK_IRR_RESERVED_2
        if self.reserved_3:
            value |= bitmasks.MASK_IRR_RESERVED_3
        if self.reserved_4:
            value |= bitmasks.MASK_IRR_RESERVED_4
        if self.reserved_5:
            value |= bitmasks.MASK_IRR_RESERVED_5
        if self.reserved_6:
            value |= bitmasks.MASK_IRR_RESERVED_6
        if self.immutable:
            value |= bitmasks.MASK_IRR_IMMUTABLE
        return value

    @staticmethod
    def from_byte(value: int) -> IrreversibleFlags:
        if not 0 <= value <= MAX_UINT8:
            raise ValueError(f"Byte value must be 0-255, got {value}")
        return IrreversibleFlags(
            arc3=bool(value & bitmasks.MASK_IRR_ARC3),
            arc89_native=bool(value & bitmasks.MASK_IRR_ARC89_NATIVE),
            reserved_2=bool(value & bitmasks.MASK_IRR_RESERVED_2),
            reserved_3=bool(value & bitmasks.MASK_IRR_RESERVED_3),
            reserved_4=bool(value & bitmasks.MASK_IRR_RESERVED_4),
            reserved_5=bool(value & bitmasks.MASK_IRR_RESERVED_5),
            reserved_6=bool(value & bitmasks.MASK_IRR_RESERVED_6),
            immutable=bool(value & bitmasks.MASK_IRR_IMMUTABLE),
        )

    @staticmethod
    def empty() -> IrreversibleFlags:
        return IrreversibleFlags()


@dataclass(frozen=True, slots=True)
class MetadataFlags:
    """Combined reversible and irreversible flags."""

    reversible: ReversibleFlags
    irreversible: IrreversibleFlags

    @property
    def reversible_byte(self) -> int:
        return self.reversible.byte_value

    @property
    def irreversible_byte(self) -> int:
        return self.irreversible.byte_value

    @staticmethod
    def from_bytes(reversible: int, irreversible: int) -> MetadataFlags:
        return MetadataFlags(
            reversible=ReversibleFlags.from_byte(reversible),
            irreversible=IrreversibleFlags.from_byte(irreversible),
        )

    @staticmethod
    def empty() -> MetadataFlags:
        return MetadataFlags(
            reversible=ReversibleFlags.empty(), irreversible=IrreversibleFlags.empty()
        )


@dataclass(frozen=True, slots=True)
class MetadataHeader:
    identifiers: int
    flags: MetadataFlags
    metadata_hash: bytes  # 32 bytes
    last_modified_round: int
    deprecated_by: int

    @property
    def is_short(self) -> bool:
        return bool(self.identifiers & bitmasks.MASK_ID_SHORT)

    @property
    def is_immutable(self) -> bool:
        return self.flags.irreversible.immutable

    @property
    def is_arc3_compliant(self) -> bool:
        return self.flags.irreversible.arc3

    @property
    def is_arc89_native(self) -> bool:
        return self.flags.irreversible.arc89_native

    @property
    def is_arc20_smart_asa(self) -> bool:
        return self.flags.reversible.arc20

    @property
    def is_arc62_circulating_supply(self) -> bool:
        return self.flags.reversible.arc62

    @property
    def is_deprecated(self) -> bool:
        return self.deprecated_by != 0

    @property
    def serialized(self) -> bytes:
        result = bytearray()
        result.append(self.identifiers & 0xFF)
        result.append(self.flags.reversible_byte & 0xFF)
        result.append(self.flags.irreversible_byte & 0xFF)
        result.extend(self.metadata_hash)
        result.extend(
            self.last_modified_round.to_bytes(const.UINT64_SIZE, "big", signed=False)
        )
        result.extend(
            self.deprecated_by.to_bytes(const.UINT64_SIZE, "big", signed=False)
        )
        return bytes(result)

    def expected_identifiers(
        self, *, body: MetadataBody, params: RegistryParameters | None = None
    ) -> int:
        """
        Return an identifiers byte whose shortness bit is consistent with `body`.

        Reserved bits are preserved from the observed header.
        """
        p = params or get_default_registry_params()
        is_short = body.size <= p.short_metadata_size
        return _set_bit(
            bits=self.identifiers & 0xFF, mask=bitmasks.MASK_ID_SHORT, value=is_short
        )

    @staticmethod
    def from_tuple(value: Sequence[AbiValue]) -> MetadataHeader:
        """
        Parse from ABI tuple (identifiers, rev_flags, irr_flags, hash, last_modified_round, deprecated_by).
        """
        if len(value) != 6:
            raise ValueError("Expected 6-tuple for metadata header")
        v0, v1, v2, v3, v4, v5 = (
            value[0],
            value[1],
            value[2],
            value[3],
            value[4],
            value[5],
        )

        if not isinstance(v0, int):
            raise TypeError("identifiers must be int")
        if not 0 <= v0 <= MAX_UINT8:
            raise ValueError("identifiers must fit in uint8")

        if not isinstance(v1, int) or not 0 <= v1 <= MAX_UINT8:
            raise TypeError("reversible_flags must be int 0..255")
        if not isinstance(v2, int) or not 0 <= v2 <= MAX_UINT8:
            raise TypeError("irreversible_flags must be int 0..255")

        metadata_hash = _coerce_bytes(v3, name="metadata_hash")
        if len(metadata_hash) != 32:
            raise ValueError("metadata_hash must be 32 bytes")

        if not isinstance(v4, int):
            raise TypeError("last_modified_round must be int")
        if not isinstance(v5, int):
            raise TypeError("deprecated_by must be int")

        return MetadataHeader(
            identifiers=v0,
            flags=MetadataFlags.from_bytes(v1, v2),
            metadata_hash=metadata_hash,
            last_modified_round=v4,
            deprecated_by=v5,
        )


@dataclass(frozen=True, slots=True)
class MetadataBody:
    raw_bytes: bytes

    @property
    def size(self) -> int:
        return len(self.raw_bytes)

    @property
    def is_short(self) -> bool:
        p = get_default_registry_params()
        return self.size <= p.short_metadata_size

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    @property
    def json(self) -> dict[str, object]:
        """Decode metadata bytes to JSON object."""
        return decode_metadata_json(self.raw_bytes)

    def total_pages(self, params: RegistryParameters | None = None) -> int:
        if self.size == 0:
            return 0
        p = params or get_default_registry_params()
        return (self.size + p.page_size - 1) // p.page_size

    def get_page(
        self, page_index: int, params: RegistryParameters | None = None
    ) -> bytes:
        if page_index < 0:
            raise InvalidPageIndexError("page_index must be non-negative")
        total = self.total_pages(params)
        if page_index >= total:
            raise InvalidPageIndexError(
                f"Page index {page_index} out of range (total pages: {total})"
            )
        p = params or get_default_registry_params()
        start = page_index * p.page_size
        end = min(start + p.page_size, self.size)
        return self.raw_bytes[start:end]

    def chunked_payload(
        self,
        *,
        params: RegistryParameters | None = None,
    ) -> list[bytes]:
        """
        Split the metadata bytes into head + extra payload chunks.
        """
        p = params or get_default_registry_params()
        return _chunk_metadata_payload(
            self.raw_bytes,
            head_max_size=p.first_payload_max_size,
            extra_max_size=p.extra_payload_max_size,
        )

    def validate_size(self, params: RegistryParameters | None = None) -> None:
        """Raise ValueError if metadata exceeds max size."""
        p = params or get_default_registry_params()
        if self.size > p.max_metadata_size:
            raise ValueError(
                f"Metadata size {self.size} exceeds max {p.max_metadata_size}"
            )

    @staticmethod
    def from_json(
        obj: Mapping[str, object], *, arc3_compliant: bool = False
    ) -> MetadataBody:
        if arc3_compliant:
            validate_arc3_schema(obj)
        return MetadataBody(encode_metadata_json(obj))

    @staticmethod
    def empty() -> MetadataBody:
        """Create an empty metadata body (represents {})."""
        return MetadataBody(b"")


@dataclass(frozen=True, slots=True)
class Pagination:
    metadata_size: int
    page_size: int
    total_pages: int

    @staticmethod
    def from_tuple(value: Sequence[int]) -> Pagination:
        if len(value) != 3:
            raise ValueError("Expected (metadata_size, page_size, total_pages)")
        return Pagination(
            metadata_size=int(value[0]),
            page_size=int(value[1]),
            total_pages=int(value[2]),
        )


@dataclass(frozen=True, slots=True)
class PaginatedMetadata:
    has_next_page: bool
    last_modified_round: int
    page_content: bytes

    @staticmethod
    def from_tuple(value: Sequence[AbiValue]) -> PaginatedMetadata:
        if len(value) != 3:
            raise ValueError(
                "Expected (has_next_page, last_modified_round, page_content)"
            )
        v0, v1, v2 = value[0], value[1], value[2]
        if not isinstance(v0, bool):
            raise TypeError("has_next_page must be bool")
        if not isinstance(v1, int):
            raise TypeError("last_modified_round must be int")
        page_content = _coerce_bytes(v2, name="page_content")
        return PaginatedMetadata(
            has_next_page=v0,
            last_modified_round=v1,
            page_content=page_content,
        )


@dataclass(frozen=True, slots=True)
class AssetMetadataBox:
    """
    Parsed ARC-89 Asset Metadata Box.

    Box value format (HEADER_SIZE bytes header + body bytes):
    - identifiers: byte
    - reversible_flags: byte
    - irreversible_flags: byte
    - metadata_hash: byte[32]
    - last_modified_round: uint64
    - deprecated_by: uint64
    - metadata: byte[]
    """

    asset_id: int
    header: MetadataHeader
    body: MetadataBody

    @classmethod
    def parse(
        cls,
        *,
        asset_id: int,
        value: bytes,
        header_size: int | None = None,
        max_metadata_size: int | None = None,
        params: RegistryParameters | None = None,
    ) -> AssetMetadataBox:
        """
        Parse a box value into (header, body).

        If `params` is provided, `header_size` and `max_metadata_size` default to the chain values.
        """
        p = params or get_default_registry_params()
        header_size = header_size or p.header_size
        max_metadata_size = max_metadata_size or p.max_metadata_size

        if len(value) < header_size:
            raise BoxParseError(f"Box value too small: {len(value)} < {header_size}")

        # Parse the known ARC-89 header fields at fixed offsets.
        try:
            identifiers = int(value[const.IDX_METADATA_IDENTIFIERS])
            rev_flags = int(value[const.IDX_REVERSIBLE_FLAGS])
            irr_flags = int(value[const.IDX_IRREVERSIBLE_FLAGS])
            metadata_hash = value[
                const.IDX_METADATA_HASH : const.IDX_LAST_MODIFIED_ROUND
            ]
            last_modified_round = int.from_bytes(
                value[const.IDX_LAST_MODIFIED_ROUND : const.IDX_DEPRECATED_BY],
                "big",
                signed=False,
            )
            deprecated_by = int.from_bytes(
                value[
                    const.IDX_DEPRECATED_BY : const.IDX_DEPRECATED_BY
                    + const.UINT64_SIZE
                ],
                "big",
                signed=False,
            )
        except Exception as e:
            raise BoxParseError("Failed to parse ARC-89 metadata header") from e

        if len(metadata_hash) != 32:
            raise BoxParseError("Invalid metadata_hash length")

        body_bytes = value[header_size:]
        if len(body_bytes) > max_metadata_size:
            raise BoxParseError("Metadata exceeds max_metadata_size")

        header = MetadataHeader(
            identifiers=identifiers,
            flags=MetadataFlags.from_bytes(rev_flags, irr_flags),
            metadata_hash=bytes(metadata_hash),
            last_modified_round=last_modified_round,
            deprecated_by=deprecated_by,
        )
        body = MetadataBody(raw_bytes=body_bytes)
        return cls(asset_id=asset_id, header=header, body=body)

    def expected_metadata_hash(
        self,
        *,
        params: RegistryParameters | None = None,
        asa_am: bytes | None = None,
        enforce_immutable_on_override: bool = True,
        enforce_arc89_native_hash_match: bool = True,
    ) -> bytes:
        """
        Compute the *effective* metadata hash for this record.

        If `asa_am` is provided and non-zero, returns it (ASA `am` override case).
        If `enforce_arc89_native_hash_match` is True (default), when ARC89 native is set
        but ARC3 is not, the ASA's `am` must match the computed metadata hash.
        """
        p = params or get_default_registry_params()

        identifiers = self.header.expected_identifiers(body=self.body, params=p)
        computed_hash = compute_metadata_hash(
            asset_id=self.asset_id,
            metadata_identifiers=identifiers,
            reversible_flags=self.header.flags.reversible_byte,
            irreversible_flags=self.header.flags.irreversible_byte,
            metadata=self.body.raw_bytes,
            page_size=p.page_size,
        )

        if asa_am is not None and _is_nonzero_32(asa_am):
            if (
                enforce_immutable_on_override
                and not self.header.flags.irreversible.immutable
            ):
                raise ValueError("ASA `am` override requires immutable metadata")
            # ARC89 native without ARC3: am must match computed hash
            if (
                enforce_arc89_native_hash_match
                and self.header.is_arc89_native
                and not self.header.is_arc3_compliant
                and asa_am != computed_hash
            ):
                raise MetadataHashMismatchError(
                    "ASA Metadata Hash (am) does not match the computed hash; "
                    "ARC89 native metadata without ARC3 requires matching hashes"
                )
            return asa_am

        return computed_hash

    def hash_matches(
        self,
        *,
        params: RegistryParameters | None = None,
        asa_am: bytes | None = None,
        skip_validation_on_override: bool = True,
    ) -> bool:
        """
        Compare observed on-chain hash to the locally computed effective hash.

        If `asa_am` is set and non-zero and skip_validation_on_override=True, this returns True
        unconditionally (because spec says not to validate `am` overrides).
        """
        if (
            asa_am is not None
            and _is_nonzero_32(asa_am)
            and skip_validation_on_override
        ):
            return True
        expected = self.expected_metadata_hash(params=params, asa_am=asa_am)
        return expected == self.header.metadata_hash

    @property
    def json(self) -> dict[str, object]:
        return decode_metadata_json(self.body.raw_bytes)

    def as_asset_metadata(self) -> AssetMetadata:
        return AssetMetadata(
            asset_id=self.asset_id,
            body=self.body,
            flags=self.header.flags,
            deprecated_by=self.header.deprecated_by,
        )


@dataclass(frozen=True, slots=True)
class AssetMetadataRecord:
    """
    High-level representation of an on-chain ARC-89 metadata record (header + metadata bytes).

    This is what you typically want for reading.
    """

    app_id: int
    asset_id: int
    header: MetadataHeader
    body: MetadataBody

    @property
    def json(self) -> dict[str, object]:
        return decode_metadata_json(self.body.raw_bytes)

    def as_asset_metadata(self) -> AssetMetadata:
        return AssetMetadata(
            asset_id=self.asset_id,
            body=self.body,
            flags=self.header.flags,
            deprecated_by=self.header.deprecated_by,
        )

    def expected_metadata_hash(
        self,
        *,
        params: RegistryParameters | None = None,
        asa_am: bytes | None = None,
        enforce_immutable_on_override: bool = True,
        enforce_arc89_native_hash_match: bool = True,
    ) -> bytes:
        return AssetMetadataBox(
            asset_id=self.asset_id, header=self.header, body=self.body
        ).expected_metadata_hash(
            params=params,
            asa_am=asa_am,
            enforce_immutable_on_override=enforce_immutable_on_override,
            enforce_arc89_native_hash_match=enforce_arc89_native_hash_match,
        )

    def hash_matches(
        self,
        *,
        params: RegistryParameters | None = None,
        asa_am: bytes | None = None,
    ) -> bool:
        return AssetMetadataBox(
            asset_id=self.asset_id, header=self.header, body=self.body
        ).hash_matches(
            params=params,
            asa_am=asa_am,
        )


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    """
    Metadata payload and flags, suitable for ARC-89 write operations.

    This class represents only the *metadata body* (JSON bytes), plus flags to be stored in the header.
    Header identifiers and hash are derived and can be recomputed after changes.
    Registry parameters are always set as default (cached singleton).
    """

    asset_id: int
    body: MetadataBody
    flags: MetadataFlags
    deprecated_by: int

    @property
    def is_empty(self) -> bool:
        return self.body.is_empty

    @property
    def is_short(self) -> bool:
        return self.body.is_short

    @property
    def size(self) -> int:
        return self.body.size

    @property
    def is_immutable(self) -> bool:
        return self.flags.irreversible.immutable

    @property
    def is_arc3_compliant(self) -> bool:
        return self.flags.irreversible.arc3

    @property
    def is_arc89_native(self) -> bool:
        return self.flags.irreversible.arc89_native

    @property
    def is_arc20_smart_asa(self) -> bool:
        return self.flags.reversible.arc20

    @property
    def is_arc62_circulating_supply(self) -> bool:
        return self.flags.reversible.arc62

    @property
    def is_deprecated(self) -> bool:
        return self.deprecated_by != 0

    @property
    def identifiers_byte(self) -> int:
        """
        Compute the metadata identifiers byte for hashing/writes.

        The registry sets the shortness bit based on metadata size; we mirror that logic here.
        Reserved bits default to 0 for write-intent objects.
        """
        value = 0
        if self.is_short:
            value |= bitmasks.MASK_ID_SHORT
        return value

    def compute_header_hash(self) -> bytes:
        return compute_header_hash(
            asset_id=self.asset_id,
            metadata_identifiers=self.identifiers_byte,
            reversible_flags=self.flags.reversible_byte,
            irreversible_flags=self.flags.irreversible_byte,
            metadata_size=self.body.size,
        )

    def compute_page_hash(self, *, page_index: int) -> bytes:
        return compute_page_hash(
            asset_id=self.asset_id,
            page_index=page_index,
            page_content=self.body.get_page(page_index),
        )

    def compute_arc89_metadata_hash(self) -> bytes:
        """
        Compute the ARC-89 hash from (identifiers, flags, pages).

        This ignores the ASA `am` override mechanism.
        """
        p = get_default_registry_params()
        return compute_metadata_hash(
            asset_id=self.asset_id,
            metadata_identifiers=self.identifiers_byte,
            reversible_flags=self.flags.reversible.byte_value,
            irreversible_flags=self.flags.irreversible.byte_value,
            metadata=self.body.raw_bytes,
            page_size=p.page_size,
        )

    def compute_metadata_hash(
        self,
        *,
        asa_am: bytes | None = None,
        enforce_immutable_on_override: bool = True,
        enforce_arc89_native_hash_match: bool = True,
    ) -> bytes:
        """
        Compute the effective on-chain metadata hash.

        If `asa_am` is provided and non-zero, it takes precedence and is returned
        (ASA Asset Metadata Hash (`am`) override behavior per ARC-89). In that case,
        the registry does not validate the `am` content, but ARC-89 requires the
        metadata to be immutable at creation.

        If `enforce_arc89_native_hash_match` is True (default), when ARC89 native is set
        but ARC3 is not, the ASA's `am` must match the computed metadata hash.
        """

        computed_hash = self.compute_arc89_metadata_hash()

        if asa_am is not None:
            if len(asa_am) != 32:
                raise ValueError("ASA `am` override must be exactly 32 bytes")
            if _is_nonzero_32(asa_am):
                if (
                    enforce_immutable_on_override
                    and not self.flags.irreversible.immutable
                ):
                    raise ValueError("ASA `am` override requires immutable metadata")
                # ARC89 native without ARC3: am must match computed hash
                if (
                    enforce_arc89_native_hash_match
                    and self.is_arc89_native
                    and not self.is_arc3_compliant
                    and asa_am != computed_hash
                ):
                    raise MetadataHashMismatchError(
                        "ASA Metadata Hash (am) does not match the computed hash; "
                        "ARC89 native metadata without ARC3 requires matching hashes"
                    )
                return asa_am

        return computed_hash

    def get_mbr_delta(self, *, old_size: int | None = None) -> MbrDelta:
        p = get_default_registry_params()
        return p.mbr_delta(old_metadata_size=old_size, new_metadata_size=self.body.size)

    def get_delete_mbr_delta(self) -> MbrDelta:
        p = get_default_registry_params()
        return p.mbr_delta(
            old_metadata_size=self.body.size, new_metadata_size=0, delete=True
        )

    @classmethod
    def from_json(
        cls,
        *,
        asset_id: int,
        json_obj: Mapping[str, object],
        flags: MetadataFlags | None = None,
        deprecated_by: int = 0,
        arc3_compliant: bool = False,
    ) -> AssetMetadata:
        # Auto-detect ARC-3 metadata if not explicitly specified
        is_arc3 = arc3_compliant or is_arc3_metadata(json_obj)

        # Validate ARC-3 schema if metadata contains ARC-3 fields
        if is_arc3:
            validate_arc3_schema(json_obj)

        body_raw_bytes = encode_metadata_json(json_obj)
        # Validate round-trip and schema constraints (object)
        decode_metadata_json(body_raw_bytes)

        # Set arc3 flag if detected and not overridden by explicit flags
        final_flags = flags
        if final_flags is None and is_arc3:
            final_flags = MetadataFlags(
                reversible=ReversibleFlags.empty(),
                irreversible=IrreversibleFlags(arc3=True),
            )
        elif final_flags is None:
            final_flags = MetadataFlags.empty()

        return cls(
            asset_id=asset_id,
            body=MetadataBody(body_raw_bytes),
            flags=final_flags,
            deprecated_by=deprecated_by,
        )

    @classmethod
    def from_bytes(
        cls,
        *,
        asset_id: int,
        metadata_bytes: bytes,
        flags: MetadataFlags | None = None,
        deprecated_by: int = 0,
        validate_json_object: bool = True,
        arc3_compliant: bool = False,
    ) -> AssetMetadata:
        """
        Create from raw metadata bytes.

        If validate_json_object=True (default), bytes must decode to a JSON object per ARC-89
        (empty bytes are allowed and treated as `{}`). ARC-3 compliance validation (arc3_compliant=True)
        requires JSON object validation.
        """
        assert (
            not arc3_compliant or validate_json_object
        ), "arc3_compliant=True requires validate_json_object=True"
        if validate_json_object:
            json_obj = decode_metadata_json(metadata_bytes)
            if arc3_compliant:
                validate_arc3_schema(json_obj)

        return cls(
            asset_id=asset_id,
            body=MetadataBody(metadata_bytes),
            flags=flags or MetadataFlags.empty(),
            deprecated_by=deprecated_by,
        )
