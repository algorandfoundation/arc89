"""Copy of ASA Metadata Registry smart contract constants."""


from typing import Final

# ---------------------------------------------------------------------------
# Algorand constants
# ---------------------------------------------------------------------------
MAINNET_GH_B64: Final[str] = "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="
TESTNET_GH_B64: Final[str] = "SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="


# ---------------------------------------------------------------------------
# AVM constants
# ---------------------------------------------------------------------------
MAX_BOX_SIZE: Final[int] = 32768
MAX_STK_SIZE: Final[int] = 4096
MAX_ARG_SIZE: Final[int] = 2048
MAX_LOG_SIZE: Final[int] = 1024

FLAT_MBR: Final[int] = 2500  # microALGO
BYTE_MBR: Final[int] = 400  # microALGO
ACCOUNT_MBR: Final[int] = 100_000  # microALGO

APP_CALL_OP_BUDGET: Final[int] = 700


# ---------------------------------------------------------------------------
# ARC-4 constants
# ---------------------------------------------------------------------------
# ABI Types Byte Sizes
BOOL_SIZE: Final[int] = 1
UINT8_SIZE: Final[int] = 1
UINT16_SIZE: Final[int] = 2
UINT32_SIZE: Final[int] = 4
UINT64_SIZE: Final[int] = 8

BYTE_SIZE: Final[int] = 1
BYTES32_SIZE: Final[int] = 32

# ARC-4 ABI Encoding
ARC4_ARG_METHOD_SELECTOR: Final[int] = 0
ARC4_METHOD_SELECTOR_SIZE: Final[int] = 4
ARC4_RETURN_PREFIX_SIZE: Final[int] = 4
ARC4_DYNAMIC_LENGTH_SIZE: Final[int] = 2


# ---------------------------------------------------------------------------
# ARC-3 constants
# ---------------------------------------------------------------------------
ARC3_NAME: Final[bytes] = b"arc3"
ARC3_NAME_SUFFIX: Final[bytes] = b"@arc3"
ARC3_URL_SUFFIX: Final[bytes] = b"#arc3"
ARC3_HASH_AM_PREFIX: Final[bytes] = b"arc0003/am"
ARC3_HASH_AMJ_PREFIX: Final[bytes] = b"arc0003/amj"


# ---------------------------------------------------------------------------
# ARC-90 constants
# ---------------------------------------------------------------------------
# ARC-90 URI Structure:
#   algorand://<netauth>/app/<app_id>?box=<base64url_box_name>#<fragment>
#
# Examples:
#   - TestNet:  algorand://net:testnet/app/752790676?box=AAAAAAAAAAE%3D#arc89
#   - LocalNet: algorand://net:localnet/app/1002?box=AAAAAAAAA-w%3D#arc3
#   - MainNet:  algorand://app/123456789?box=AAAAAAAAAAE%3D#arc89
#

ARC90_URI_SCHEME_NAME: Final[bytes] = b"algorand"
ARC90_URI_APP_PATH_NAME: Final[bytes] = b"app"
ARC90_URI_BOX_QUERY_NAME: Final[bytes] = b"box"

ARC90_URI_PATH_SEP: Final[bytes] = b"/"

ARC90_URI_SCHEME: Final[bytes] = ARC90_URI_SCHEME_NAME + b"://"
ARC90_URI_APP_PATH: Final[bytes] = ARC90_URI_APP_PATH_NAME + ARC90_URI_PATH_SEP
ARC90_URI_BOX_QUERY: Final[bytes] = b"?" + ARC90_URI_BOX_QUERY_NAME + b"="


# ---------------------------------------------------------------------------
# ARC-89 constants
# ---------------------------------------------------------------------------
# Opcode Budgets
HEADER_HASH_OP_BUDGET: Final[int] = 110
PAGE_HASH_OP_BUDGET: Final[int] = 150

# Method Signatures Overhead
ARC89_CREATE_METADATA_FIXED_SIZE: Final[int] = (
    ARC4_METHOD_SELECTOR_SIZE
    + UINT64_SIZE
    + BYTE_SIZE
    + BYTE_SIZE
    + UINT16_SIZE
    + ARC4_DYNAMIC_LENGTH_SIZE
)

ARC89_EXTRA_PAYLOAD_FIXED_SIZE: Final[int] = (
    ARC4_METHOD_SELECTOR_SIZE + UINT64_SIZE + ARC4_DYNAMIC_LENGTH_SIZE
)

ARC89_REPLACE_METADATA_SLICE_FIXED_SIZE: Final[int] = (
    ARC4_METHOD_SELECTOR_SIZE + UINT64_SIZE + UINT16_SIZE + ARC4_DYNAMIC_LENGTH_SIZE
)

# (bool,uint64,byte[]), ABI tuple are encoded a head(...) || tail(...)
ARC89_GET_METADATA_RETURN_FIXED_SIZE: Final[int] = (
    ARC4_RETURN_PREFIX_SIZE
    + BOOL_SIZE
    + UINT64_SIZE
    + ARC4_DYNAMIC_LENGTH_SIZE  # head
    + ARC4_DYNAMIC_LENGTH_SIZE  # tail
)

# Method Signatures Argument Indexes

# arc89_extra_payload(asset_id, payload)
ARC89_EXTRA_PAYLOAD_ARG_ASSET_ID: Final[int] = 1
ARC89_EXTRA_PAYLOAD_ARG_PAYLOAD: Final[int] = 2

# Pagination
FIRST_PAYLOAD_MAX_SIZE: Final[int] = MAX_ARG_SIZE - ARC89_CREATE_METADATA_FIXED_SIZE
EXTRA_PAYLOAD_MAX_SIZE: Final[int] = MAX_ARG_SIZE - ARC89_EXTRA_PAYLOAD_FIXED_SIZE
REPLACE_PAYLOAD_MAX_SIZE: Final[int] = (
    MAX_ARG_SIZE - ARC89_REPLACE_METADATA_SLICE_FIXED_SIZE
)
PAGE_SIZE: Final[int] = MAX_LOG_SIZE - ARC89_GET_METADATA_RETURN_FIXED_SIZE
MAX_PAGES: Final[int] = 31

# Asset Metadata Box
ASSET_METADATA_BOX_KEY_SIZE: Final[int] = UINT64_SIZE

# Asset Metadata Box Header
METADATA_IDENTIFIERS_SIZE: Final[int] = BYTE_SIZE
REVERSIBLE_FLAGS_SIZE: Final[int] = BYTE_SIZE
IRREVERSIBLE_FLAGS_SIZE: Final[int] = BYTE_SIZE
METADATA_HASH_SIZE: Final[int] = BYTES32_SIZE
LAST_MODIFIED_ROUND_SIZE: Final[int] = UINT64_SIZE
DEPRECATED_BY_SIZE: Final[int] = UINT64_SIZE
HEADER_SIZE: Final[int] = (
    METADATA_IDENTIFIERS_SIZE
    + REVERSIBLE_FLAGS_SIZE
    + IRREVERSIBLE_FLAGS_SIZE
    + METADATA_HASH_SIZE
    + LAST_MODIFIED_ROUND_SIZE
    + DEPRECATED_BY_SIZE
)

IDX_METADATA_IDENTIFIERS: Final[int] = 0
IDX_REVERSIBLE_FLAGS: Final[int] = IDX_METADATA_IDENTIFIERS + METADATA_IDENTIFIERS_SIZE
IDX_IRREVERSIBLE_FLAGS: Final[int] = IDX_REVERSIBLE_FLAGS + REVERSIBLE_FLAGS_SIZE
IDX_METADATA_HASH: Final[int] = IDX_IRREVERSIBLE_FLAGS + IRREVERSIBLE_FLAGS_SIZE
IDX_LAST_MODIFIED_ROUND: Final[int] = IDX_METADATA_HASH + METADATA_HASH_SIZE
IDX_DEPRECATED_BY: Final[int] = IDX_LAST_MODIFIED_ROUND + LAST_MODIFIED_ROUND_SIZE

# AVM setbit/getbit opcodes bit offset (index 0 is the leftmost bit of the leftmost byte)
BIT_RIGHTMOST_IDENTIFIER: Final[int] = 8 * METADATA_IDENTIFIERS_SIZE - 1
BIT_RIGHTMOST_REV_FLAG: Final[int] = 8 * REVERSIBLE_FLAGS_SIZE - 1
BIT_RIGHTMOST_IRR_FLAG: Final[int] = 8 * IRREVERSIBLE_FLAGS_SIZE - 1

# Asset Metadata Box Body
IDX_METADATA: Final[int] = IDX_DEPRECATED_BY + DEPRECATED_BY_SIZE
MAX_METADATA_SIZE: Final[int] = FIRST_PAYLOAD_MAX_SIZE + 14 * EXTRA_PAYLOAD_MAX_SIZE
SHORT_METADATA_SIZE: Final[int] = MAX_STK_SIZE

# Domain Separators
HASH_DOMAIN_HEADER: Final[bytes] = b"arc0089/header"
HASH_DOMAIN_PAGE: Final[bytes] = b"arc0089/page"
HASH_DOMAIN_METADATA: Final[bytes] = b"arc0089/am"
