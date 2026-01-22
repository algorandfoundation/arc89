from typing import Final

# Bits in big-endian order (0 = LSB, 7 = MSB)

# ⚠️ When operating on byte arrays (instead of uint64), AVM `setbit/getbit` opcodes
# index 0 as the leftmost bit of the leftmost byte.

# Metadata Identifiers byte (set by the ASA Metadata Registry; clients just read)
ID_SHORT: Final[int] = 7  # automatically derived from metadata size

# Reversible Flags byte (set by ASA Manager Address)
REV_FLG_ARC20: Final[int] = 0
REV_FLG_ARC62: Final[int] = 1
REV_FLG_RESERVED_2: Final[int] = 2  # reserved
REV_FLG_RESERVED_3: Final[int] = 3  # reserved
REV_FLG_RESERVED_4: Final[int] = 4  # reserved
REV_FLG_RESERVED_5: Final[int] = 5  # reserved
REV_FLG_RESERVED_6: Final[int] = 6  # reserved
REV_FLG_RESERVED_7: Final[int] = 7  # reserved

# Irreversible Flags byte (set by ASA Manager Address)
IRR_FLG_ARC3: Final[int] = 0  # creation-only
IRR_FLG_ARC89: Final[int] = 1  # creation-only
IRR_FLG_ARC54: Final[int] = 2  # any time
IRR_FLG_RESERVED_3: Final[int] = 3  # reserved; any time; default init False
IRR_FLG_RESERVED_4: Final[int] = 4  # reserved; any time; default init False
IRR_FLG_RESERVED_5: Final[int] = 5  # reserved; any time; default init False
IRR_FLG_RESERVED_6: Final[int] = 6  # reserved; any time; default init False
IRR_FLG_IMMUTABLE: Final[int] = 7  # any time
