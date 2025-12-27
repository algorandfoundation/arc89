UNTRUSTED_DEPLOYER = "The deployer address is not trusted"
UNAUTHORIZED = "Unauthorized, must be the Asset Manager"

ASA_NOT_EXIST = "The specified ASA does not exist"
ASA_NOT_ARC89_COMPLIANT = "Invalid ARC-89 URI"
ASA_NOT_ARC3_COMPLIANT = "Invalid ARC-3 parameters (name or URL)"

ASSET_METADATA_EXIST = "Asset Metadata already exists for the specified ASA"
ASSET_METADATA_NOT_EXIST = "Asset Metadata does not exist for the specified ASA"

EMPTY_METADATA = "Metadata is empty"
EXCEEDS_MAX_METADATA_SIZE = "Invalid Metadata size, exceeds maximum allowed size"
EXCEEDS_METADATA_SIZE = "Slice exceeds metadata range"
EXCEEDS_PAGE_SIZE = "Payload exceeds page size"
LARGER_METADATA_SIZE = (
    "Invalid Metadata size, must be smaller than or equal to the current size"
)
SMALLER_METADATA_SIZE = "Invalid Metadata size, must be larger than the current size"

NO_PAYLOAD_HEAD_CALL = "No payload head call in Group"
PAYLOAD_OVERFLOW = "Payload overflow, exceeds metadata size"

METADATA_SIZE_MISMATCH = (
    "Metadata size mismatch, must be exactly equal to declared size"
)
METADATA_NOT_SHORT = "Metadata is not short"

MBR_DELTA_RECEIVER_INVALID = (
    "Invalid MBR Delta receiver, must be the ASA Metadata Registry"
)
MBR_DELTA_AMOUNT_INVALID = "Invalid MBR Delta amount"

REQUIRES_IMMUTABLE = "Must be flagged as immutable"
IMMUTABLE = "Metadata is immutable"

FLAG_IDX_INVALID = "Invalid flag index"
PAGE_IDX_INVALID = "Invalid page index"

NEW_REGISTRY_ID_INVALID = (
    "Invalid new ASA Metadata Registry ID, must be different from current"
)
