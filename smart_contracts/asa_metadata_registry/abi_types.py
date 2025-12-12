from typing import Literal, TypeAlias

from algopy import UInt64, arc4

# Type Aliases
MicroAlgo: TypeAlias = UInt64

# ARC-4 Types
Hash = arc4.StaticArray[arc4.Byte, Literal[32]]
Timestamp = arc4.UIntN[Literal[64]]


class MbrDelta(arc4.Struct, kw_only=True):
    """
    The variation of the ASA Metadata Registry Application Account MBR due to the
    creation, update, or deletion of the Asset Metadata Box.
    """

    sign: arc4.UInt8  # Enum: null (0), positive (1), or negative (255)
    amount: arc4.UInt64  # MBR amount expressed in microALGO


class MutableFlag(arc4.Struct, kw_only=True):
    """Mutable Metadata Identifier or Flag"""

    flag: arc4.Bool
    last_modified_round: arc4.UInt64


class Pagination(arc4.Struct, kw_only=True):
    """Asset Metadata Pagination"""

    metadata_size: arc4.UInt16
    page_size: arc4.UInt16
    total_pages: arc4.UInt8


# ARC-28 Events
class Arc89MetadataUpdated(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata is created or updated"""

    asset_id: arc4.UInt64
    round: arc4.UInt64
    timestamp: Timestamp
    flags: arc4.Byte
    is_short: arc4.Bool
    hash: Hash


class Arc89MetadataDeleted(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata is deleted"""

    asset_id: arc4.UInt64
    round: arc4.UInt64
    timestamp: Timestamp
