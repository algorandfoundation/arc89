from __future__ import annotations

import enum
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property

from src import bitmasks, enums
from src import constants as const

from .errors import BoxParseError, MetadataArc3Error, MetadataEncodingError
from .hashing import MAX_UINT8, compute_metadata_hash

# Type aliases for ABI tuple values
AbiValue = int | bytes | bool | Sequence["AbiValue"]


def _chunk_metadata_payload(
    data: bytes,
    *,
    head_max_size: int,
    extra_max_size: int,
) -> list[bytes]:
    """
    Split metadata bytes into head + extra payload chunks.

    Args:
        data: The metadata bytes to chunk
        head_max_size: Max size for the first chunk
        extra_max_size: Max size for subsequent chunks

    Returns:
        List of byte chunks

    Raises:
        ValueError: If chunk sizes are invalid
    """
    if head_max_size <= 0 or extra_max_size <= 0:
        raise ValueError("Chunk sizes must be > 0")
    if len(data) == 0:
        return [b""]

    chunks: list[bytes] = [data[:head_max_size]]
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
        elif self.is_negative:
            return -self.amount
        else:
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
        if value[1] < 0:
            raise ValueError("MBR delta amount must be non-negative")
        return MbrDelta(sign=MbrDeltaSign(int(value[0])), amount=int(value[1]))


@dataclass(frozen=True, slots=True)
class RegistryParameters:
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
        # ARC-89 specs constants; callers should prefer params from registry if possible.
        return RegistryParameters(
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
        if len(value) != 9:
            raise ValueError("Expected 9-tuple of registry parameters")
        return RegistryParameters(
            header_size=int(value[0]),
            max_metadata_size=int(value[1]),
            short_metadata_size=int(value[2]),
            page_size=int(value[3]),
            first_payload_max_size=int(value[4]),
            extra_payload_max_size=int(value[5]),
            replace_payload_max_size=int(value[6]),
            flat_mbr=int(value[7]),
            byte_mbr=int(value[8]),
        )

    def mbr_for_box(self, metadata_size: int) -> int:
        """
        Compute the minimum balance requirement for a metadata box holding `metadata_size` bytes.

        This uses the flat/byte MBR parameters returned by the registry.
        """
        return self.flat_mbr + self.byte_mbr * (
            const.ASSET_METADATA_BOX_KEY_SIZE + self.header_size + metadata_size
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

        If old_metadata_size is None, the box is assumed not to exist (creation).
        """
        new_mbr = self.mbr_for_box(new_metadata_size)
        old_mbr = (
            0 if old_metadata_size is None else self.mbr_for_box(old_metadata_size)
        )
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
        return MbrDelta(MbrDeltaSign.NEG, -delta)


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
        """Get the byte representation of these flags."""
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
        """Create ReversibleFlags from a byte value."""
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
        """Create an empty flags instance (all flags False)."""
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
        """Get the byte representation of these flags."""
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
        """Create IrreversibleFlags from a byte value."""
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
        """Create an empty flags instance (all flags False)."""
        return IrreversibleFlags()


@dataclass(frozen=True, slots=True)
class MetadataFlags:
    """Combined reversible and irreversible flags."""

    reversible: ReversibleFlags
    irreversible: IrreversibleFlags

    @property
    def reversible_byte(self) -> int:
        """Get the reversible flags as a byte value."""
        return self.reversible.byte_value

    @property
    def irreversible_byte(self) -> int:
        """Get the irreversible flags as a byte value."""
        return self.irreversible.byte_value

    @staticmethod
    def from_bytes(reversible: int, irreversible: int) -> MetadataFlags:
        """Create MetadataFlags from byte values."""
        return MetadataFlags(
            reversible=ReversibleFlags.from_byte(reversible),
            irreversible=IrreversibleFlags.from_byte(irreversible),
        )

    @staticmethod
    def empty() -> MetadataFlags:
        """Create empty flags (all False)."""
        return MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags.empty(),
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
        if not isinstance(v1, int):
            raise TypeError("reversible_flags must be int")
        if not isinstance(v2, int):
            raise TypeError("irreversible_flags must be int")
        if not isinstance(v3, bytes):
            raise TypeError("metadata_hash must be bytes")
        if not isinstance(v4, int):
            raise TypeError("last_modified_round must be int")
        if not isinstance(v5, int):
            raise TypeError("deprecated_by must be int")
        return MetadataHeader(
            identifiers=v0,
            flags=MetadataFlags.from_bytes(v1, v2),
            metadata_hash=v3,
            last_modified_round=v4,
            deprecated_by=v5,
        )


def validate_arc3_schema(obj: Mapping[str, object]) -> None:
    """
    Validate that a JSON object conforms to the ARC-3 JSON metadata schema according
    to ARC-3 (https://dev.algorand.co/arc-standards/arc-0003/#json-metadata-file-schema).

    Raises MetadataArc3Error if validation fails.
    """
    # Define ARC-3 schema field types
    string_fields = {
        "name",
        "decimals",
        "description",
        "image",
        "image_integrity",
        "image_mimetype",
        "background_color",
        "external_url",
        "external_url_integrity",
        "external_url_mimetype",
        "animation_url",
        "animation_url_integrity",
        "animation_url_mimetype",
        "unitName",
        "extra_metadata",
    }

    # decimals can be either string or integer in ARC-3
    # unitName can be either string

    for key, value in obj.items():
        if key == "decimals":
            # decimals must be an integer (non-negative)
            if not isinstance(value, int) or isinstance(value, bool):
                raise MetadataArc3Error(
                    f"ARC-3 field 'decimals' must be an integer, got {type(value).__name__}"
                )
            if value < 0:
                raise MetadataArc3Error(
                    f"ARC-3 field 'decimals' must be non-negative, got {value}"
                )
        elif key == "properties":
            if not isinstance(value, dict):
                raise MetadataArc3Error(
                    f"ARC-3 field 'properties' must be an object, got {type(value).__name__}"
                )
        elif key == "localization":
            if not isinstance(value, dict):
                raise MetadataArc3Error(
                    f"ARC-3 field 'localization' must be an object, got {type(value).__name__}"
                )
            # Validate localization structure (must have 'uri' and 'default' and 'locales')
            if "uri" not in value:
                raise MetadataArc3Error(
                    "ARC-3 'localization' object must have 'uri' field"
                )
            if "default" not in value:
                raise MetadataArc3Error(
                    "ARC-3 'localization' object must have 'default' field"
                )
            if "locales" not in value:
                raise MetadataArc3Error(
                    "ARC-3 'localization' object must have 'locales' field"
                )
            if not isinstance(value["uri"], str):
                raise MetadataArc3Error("ARC-3 'localization.uri' must be a string")
            if not isinstance(value["default"], str):
                raise MetadataArc3Error("ARC-3 'localization.default' must be a string")
            if not isinstance(value["locales"], list):
                raise MetadataArc3Error("ARC-3 'localization.locales' must be an array")
            for locale in value["locales"]:
                if not isinstance(locale, str):
                    raise MetadataArc3Error(
                        "ARC-3 'localization.locales' entries must be strings"
                    )
        elif key in string_fields:
            if not isinstance(value, str):
                raise MetadataArc3Error(
                    f"ARC-3 field '{key}' must be a string, got {type(value).__name__}"
                )
        # Other fields are allowed (for extensibility) but we don't validate them


@dataclass(frozen=True, slots=True)
class MetadataBody:
    raw_bytes: bytes

    @property
    def size(self) -> int:
        return len(self.raw_bytes)

    @property
    def is_short(self) -> bool:
        return self.size <= const.SHORT_METADATA_SIZE

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    @cached_property
    def json(self) -> dict[str, object]:
        """Decode metadata bytes to JSON object."""
        return decode_metadata_json(self.raw_bytes)

    def total_pages(self, params: RegistryParameters) -> int:
        if self.size == 0:
            return 0
        return (self.size + params.page_size - 1) // params.page_size

    def chunked_payload(
        self,
        *,
        head_max_size: int = const.FIRST_PAYLOAD_MAX_SIZE,
        extra_max_size: int = const.EXTRA_PAYLOAD_MAX_SIZE,
    ) -> list[bytes]:
        """
        Split the metadata bytes into head + extra payload chunks.
        """
        return _chunk_metadata_payload(
            self.raw_bytes,
            head_max_size=head_max_size,
            extra_max_size=extra_max_size,
        )

    def validate_size(self, params: RegistryParameters) -> None:
        """Raise ValueError if metadata exceeds max size."""
        if self.size > params.max_metadata_size:
            raise ValueError(
                f"Metadata size {self.size} exceeds max {params.max_metadata_size}"
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
        if not isinstance(v2, bytes):
            raise TypeError("page_content must be bytes")
        return PaginatedMetadata(
            has_next_page=v0,
            last_modified_round=v1,
            page_content=v2,
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
        header_size: int = const.HEADER_SIZE,
        max_metadata_size: int = const.MAX_METADATA_SIZE,
    ) -> AssetMetadataBox:
        if len(value) < header_size:
            raise BoxParseError(f"Box value too small: {len(value)} < {header_size}")

        try:
            identifiers = value[const.IDX_METADATA_IDENTIFIERS]
            rev_flags = value[const.IDX_REVERSIBLE_FLAGS]
            irr_flags = value[const.IDX_IRREVERSIBLE_FLAGS]
            metadata_hash = value[
                const.IDX_METADATA_HASH : const.IDX_LAST_MODIFIED_ROUND
            ]
            last_modified_round = int.from_bytes(
                value[const.IDX_LAST_MODIFIED_ROUND : const.IDX_DEPRECATED_BY],
                "big",
                signed=False,
            )
            deprecated_by = int.from_bytes(
                value[const.IDX_DEPRECATED_BY:header_size], "big", signed=False
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
            metadata_hash=metadata_hash,
            last_modified_round=last_modified_round,
            deprecated_by=deprecated_by,
        )
        body = MetadataBody(raw_bytes=body_bytes)
        return cls(asset_id=asset_id, header=header, body=body)


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

    @cached_property
    def json(self) -> dict[str, object]:
        return decode_metadata_json(self.body.raw_bytes)

    def as_asset_metadata(self) -> AssetMetadata:
        return AssetMetadata(
            asset_id=self.asset_id,
            body=self.body,
            flags=self.header.flags,
            deprecated_by=self.header.deprecated_by,
        )


def decode_metadata_json(metadata: bytes) -> dict[str, object]:
    """
    Decode ARC-89 metadata bytes into a Python dict.

    ARC-89 requires a UTF-8 JSON *object*. Empty metadata bytes MUST be treated as `{}`.
    """
    if metadata == b"":
        return {}

    # Reject UTF-8 BOM
    if metadata.startswith(b"\xef\xbb\xbf"):
        raise MetadataEncodingError("Metadata MUST NOT include a UTF-8 BOM")

    try:
        txt = metadata.decode("utf-8")
    except UnicodeDecodeError as e:
        raise MetadataEncodingError("Metadata is not valid UTF-8") from e

    try:
        obj: object = json.loads(txt)
    except json.JSONDecodeError as e:
        raise MetadataEncodingError("Metadata is not valid JSON") from e

    if not isinstance(obj, dict):
        raise MetadataEncodingError("Metadata JSON MUST be an object")
    return obj


def encode_metadata_json(obj: Mapping[str, object]) -> bytes:
    """
    Encode a JSON object to UTF-8 bytes without BOM.

    The encoding is not canonicalized beyond `json.dumps` defaults; ARC-89 hashing uses raw bytes.
    """
    try:
        txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as e:
        raise MetadataEncodingError("Object is not JSON-serializable") from e
    data = txt.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        raise MetadataEncodingError("Produced UTF-8 BOM; this should not happen")
    return data


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    """
    Metadata payload and flags, suitable for ARC-89 write operations.

    This class represents only the *metadata body* (JSON bytes), plus flags to be stored in the header.
    The registry sets metadata identifiers (shortness) automatically.
    """

    asset_id: int
    body: MetadataBody
    flags: MetadataFlags
    deprecated_by: int

    def compute_metadata_hash(self, *, params: RegistryParameters) -> bytes:
        """
        Compute the expected on-chain metadata hash per ARC-89.

        Note: this does NOT incorporate the ASA `am` override behavior; it follows the ARC-89 hash
        computation over header+pages (domain-separated SHA-512/256).
        """
        return compute_metadata_hash(
            asset_id=self.asset_id,
            metadata_identifiers=self.body.is_short,
            reversible_flags=self.flags.reversible.byte_value,
            irreversible_flags=self.flags.irreversible.byte_value,
            metadata=self.body.raw_bytes,
            page_size=params.page_size,
        )

    def get_mbr_delta(
        self, *, params: RegistryParameters, old_size: int | None
    ) -> MbrDelta:
        return params.mbr_delta(
            old_metadata_size=old_size, new_metadata_size=self.body.size
        )

    def get_delete_mbr_delta(self, *, params: RegistryParameters) -> MbrDelta:
        return params.mbr_delta(
            old_metadata_size=self.body.size, new_metadata_size=0, delete=True
        )

    @classmethod
    def from_json(
        cls,
        *,
        asset_id: int,
        json_obj: Mapping[str, object],
        reversible_flags: int = 0,
        irreversible_flags: int = 0,
        deprecated_by: int = 0,
        arc3_compliant: bool = False,
    ) -> AssetMetadata:
        if arc3_compliant:
            validate_arc3_schema(json_obj)
        body_raw_bytes = encode_metadata_json(json_obj)
        # Validate round-trip and schema constraints (object)
        decode_metadata_json(body_raw_bytes)
        return cls(
            asset_id=asset_id,
            body=MetadataBody(body_raw_bytes),
            flags=MetadataFlags.from_bytes(reversible_flags, irreversible_flags),
            deprecated_by=deprecated_by,
        )
