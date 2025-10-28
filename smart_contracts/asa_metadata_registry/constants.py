import math
from typing import Final

# AVM
MAX_BOX_SIZE: Final[int] = 32768
MAX_LOG_SIZE: Final[int] = 1024
ARC4_RETURN_PREFIX_SIZE: Final[int] = 4
FLAT_MBR: Final[int] = 2500  # microALGO
BYTE_MBR: Final[int] = 400  # microALGO

# Asset Metadata Box Header
METADATA_IDENTIFIERS_SIZE: Final[int] = 1
METADATA_FLAGS_SIZE: Final[int] = 1
METADATA_HASH_SIZE: Final[int] = 32
LAST_MODIFIED_ROUND_SIZE: Final[int] = 8
HEADER_SIZE: Final[int] = (
    METADATA_IDENTIFIERS_SIZE
    + METADATA_FLAGS_SIZE
    + METADATA_HASH_SIZE
    + LAST_MODIFIED_ROUND_SIZE
)
assert HEADER_SIZE <= MAX_LOG_SIZE - ARC4_RETURN_PREFIX_SIZE

IDX_METADATA_IDENTIFIERS: Final[int] = 0
IDX_METADATA_FLAGS: Final[int] = IDX_METADATA_IDENTIFIERS + METADATA_IDENTIFIERS_SIZE
IDX_METADATA_HASH: Final[int] = IDX_METADATA_FLAGS + METADATA_FLAGS_SIZE
IDX_LAST_MODIFIED_ROUND: Final[int] = IDX_METADATA_HASH + METADATA_HASH_SIZE

# Asset Metadata Box Body
IDX_METADATA: Final[int] = IDX_LAST_MODIFIED_ROUND + LAST_MODIFIED_ROUND_SIZE
MAX_METADATA_SIZE: Final[int] = MAX_BOX_SIZE - HEADER_SIZE
SHORT_METADATA_SIZE: Final[int] = 4096

# Metadata Identifiers Bitmask
BITMASK_SHORT_METADATA: Final[int] = 0x01  # Hex for Bitmask 00 00 00 01
BITMASK_ARC3: Final[int] = 0x10  # Hex for Bitmask 00 01 00 00
BITMASK_ARC89: Final[int] = 0x80  # Hex for Bitmask 10 00 00 00

# Metadata Flags Bitmask
# Two-ways bits
BITMASK_ARC20: Final[int] = 0x01  # Hex for Bitmask 00 00 00 01
BITMASK_ARC62: Final[int] = 0x02  # Hex for Bitmask 00 00 00 10
BITMASK_RESERVED_BIT_2: Final[int] = 0x04  # Hex for Bitmask 00 00 01 00
BITMASK_RESERVED_BIT_3: Final[int] = 0x08  # Hex for Bitmask 00 00 10 00
# One-way bits
BITMASK_RESERVED_BIT_4: Final[int] = 0x10  # Hex for Bitmask 00 01 00 00
BITMASK_RESERVED_BIT_5: Final[int] = 0x20  # Hex for Bitmask 00 10 00 00
BITMASK_RESERVED_BIT_6: Final[int] = 0x40  # Hex for Bitmask 01 00 00 00
BITMASK_IMMUTABLE: Final[int] = 0x80  # Hex for Bitmask 10 00 00 00

# Pagination
# TODO: The hardcoded value 13 represents the size (in bytes) of the ABI type `(bool,uint64,byte[])`. Replace with ABI type size_of() when the type is defined.
PAGE_SIZE: Final[int] = MAX_LOG_SIZE - ARC4_RETURN_PREFIX_SIZE - 13
MAX_PAGES: Final[int] = 33
assert MAX_PAGES == math.ceil(MAX_METADATA_SIZE / PAGE_SIZE) <= 256

# Domain Separators
METADATA_HEADER_HASH: Final[str] = "arc0089/header"
METADATA_PAGE_HASH: Final[str] = "arc0089/page"
METADATA_HASH: Final[str] = "arc0089/am"

# Asset Metadata URI
URI_ARC_SEGMENT: Final[bytes] = b"#arc"
URI_ARC_89_PREFIX: Final[bytes] = b"algorand://app/"
URI_ARC_89_SUFFIX: Final[bytes] = b"?box="
