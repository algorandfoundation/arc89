from typing import Final

# Bits in big-endian order (0 = LSB, 7 = MSB)

# ⚠️ When operating on byte arrays (instead of uint64), AVM `setbit/getbit` opcodes
# index 0 as the leftmost bit of the leftmost byte.

# Metadata Identifiers byte (set by the ASA Metadata Registry; clients just read)
ID_SHORT: Final[int] = 7  # Short Metadata (derived from size)

# Metadata Flags byte (set by ASA Manager Address)
FLG_ARC20: Final[int] = 0  # reversible
FLG_ARC62: Final[int] = 1  # reversible
FLG_RESERVED_2: Final[int] = 2  # reversible (reserved; MUST init False)
FLG_RESERVED_3: Final[int] = 3  # reversible (reserved; MUST init False)
FLG_ARC3: Final[int] = 4  # one-way, creation-only
FLG_ARC89_NATIVE: Final[int] = 5  # one-way, creation-only
FLG_RESERVED_6: Final[int] = 6  # one-way, set-anytime (reserved; MUST init False)
FLG_IMMUTABLE: Final[int] = 7  # one-way, set-anytime (MSB)
