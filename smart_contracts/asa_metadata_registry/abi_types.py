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


# ARC-28 Events
class Arc89MetadataCreated(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata is created"""
    asset_id: arc4.UInt64
    round: arc4.UInt64
    timestamp: Timestamp
    hash: Hash
    flags: arc4.Byte
    is_short: arc4.Bool
    is_arc3: arc4.Bool
    is_native: arc4.Bool


class Arc89MetadataUpdated(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata is replaced or updated"""
    asset_id: arc4.UInt64
    round: arc4.UInt64
    timestamp: Timestamp
    hash: Hash
    is_short: arc4.Bool


class Arc89MetadataDeleted(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata is deleted"""
    asset_id: arc4.UInt64
    round: arc4.UInt64
    timestamp: Timestamp


class Arc89MetadataUpdatedFlags(arc4.Struct, kw_only=True):
    """Event emitted when Asset Metadata Flags are updated"""
    asset_id: arc4.UInt64
    round: arc4.UInt64
    timestamp: Timestamp
    old_flags: arc4.Byte
    new_flags: arc4.Byte
    hash: Hash
