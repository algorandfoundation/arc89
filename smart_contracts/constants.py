from typing import Final

# Algorand Genesis Hash
MAINNET_GH_B64: Final[str] = "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="

# AVM
MAX_BOX_SIZE: Final[int] = 32768
MAX_LOG_SIZE: Final[int] = 1024
MAX_ARG_SIZE: Final[int] = 2048
FLAT_MBR: Final[int] = 2500  # microALGO
BYTE_MBR: Final[int] = 400  # microALGO
ACCOUNT_MBR: Final[int] = 100_000  # microALGO

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

# ARCs
ARC90_URI_SCHEME: Final[bytes] = b"algorand://"
ARC90_URI_APP_PATH: Final[bytes] = b"app/"
ARC90_URI_BOX_QUERY: Final[bytes] = b"?box="

ARC3_NAME: Final[bytes] = b"arc3"
ARC3_NAME_SUFFIX: Final[bytes] = b"@arc3"
ARC3_URL_SUFFIX: Final[bytes] = b"#arc3"
ARC3_HASH_AM_PREFIX: Final[bytes] = b"arc0003/am"
ARC3_HASH_AMJ_PREFIX: Final[bytes] = b"arc0003/amj"
