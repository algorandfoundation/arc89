"""Copy of ASA Metadata Registry smart contract enums."""

from typing import Final

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
MBR_DELTA_NULL: Final[int] = 0
MBR_DELTA_POS: Final[int] = 1
MBR_DELTA_NEG: Final[int] = 255

JSON_KEY_TYPE_STRING: Final[int] = 0
JSON_KEY_TYPE_UINT64: Final[int] = 1
JSON_KEY_TYPE_OBJECT: Final[int] = 2

B64_URL_ENCODING: Final[int] = 0
B64_STD_ENCODING: Final[int] = 1
