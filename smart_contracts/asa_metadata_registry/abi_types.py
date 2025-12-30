from typing import Literal, TypeAlias

from algopy import Bytes, FixedBytes, UInt64, arc4

# Type Aliases
MicroAlgo: TypeAlias = UInt64
Timestamp: TypeAlias = UInt64

# ARC-4 Types
Hash = FixedBytes[Literal[32]]


class MetadataHeader(arc4.Struct, kw_only=True):
    """Asset Metadata Header"""

    identifiers: arc4.Byte
    reversible_flags: arc4.Byte
    irreversible_flags: arc4.Byte
    hash: Hash
    last_modified_round: UInt64
    deprecated_by: UInt64


class MbrDelta(arc4.Struct, kw_only=True):
    """
    The variation of the ASA Metadata Registry Application Account MBR due to the
    creation, update, or deletion of the Asset Metadata Box.
    """

    sign: arc4.UInt8  # Enum: null (0), positive (1), or negative (255)
    amount: MicroAlgo  # MBR amount expressed in microALGO


class MutableFlag(arc4.Struct, kw_only=True):
    """Mutable Metadata Identifier or Flag"""

    flag: bool
    last_modified_round: UInt64


class MetadataExistence(arc4.Struct, kw_only=True):
    """Metadata Existence"""

    asa_exists: bool
    metadata_exists: bool


class Pagination(arc4.Struct, kw_only=True):
    """Asset Metadata Pagination"""

    metadata_size: arc4.UInt16
    page_size: arc4.UInt16
    total_pages: arc4.UInt8


class PaginatedMetadata(arc4.Struct, kw_only=True):
    """Paginated Asset Metadata"""

    has_next_page: bool
    last_modified_round: UInt64
    page_content: Bytes


class RegistryParameters(arc4.Struct, kw_only=True):
    """ASA Metadata Registry Parameters"""

    header_size: arc4.UInt16
    max_metadata_size: arc4.UInt16
    short_metadata_size: arc4.UInt16
    page_size: arc4.UInt16
    first_payload_max_size: arc4.UInt16
    extra_payload_max_size: arc4.UInt16
    replace_payload_max_size: arc4.UInt16
    flat_mbr: UInt64
    byte_mbr: UInt64


# ARC-28 Events
class Arc89MetadataUpdated(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata is created or updated"""

    asset_id: UInt64
    round: UInt64
    timestamp: Timestamp
    reversible_flags: arc4.Byte
    irreversible_flags: arc4.Byte
    is_short: bool
    hash: Hash


class Arc89MetadataMigrated(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata has been migrated to a new ASA Metadata Registry version"""

    asset_id: UInt64
    new_registry_id: UInt64
    round: UInt64
    timestamp: Timestamp


class Arc89MetadataDeleted(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata is deleted"""

    asset_id: UInt64
    round: UInt64
    timestamp: Timestamp
