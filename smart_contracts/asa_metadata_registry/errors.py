from typing import LiteralString

# ── Auth ─────────────────────────────────────────────────────────────────────
UNTRUSTED_DEPLOYER: LiteralString = "UntrustedDeployer"
UNTRUSTED_DEPLOYER_DES = "The deployer address is not trusted"

UNAUTHORIZED: LiteralString = "Unauthorized"
UNAUTHORIZED_DES = "Unauthorized, must be the Asset Manager"

# ── ASA ───────────────────────────────────────────────────────────────────────
ASA_NOT_EXIST: LiteralString = "AsaNotExist"
ASA_NOT_EXIST_DES = "The specified ASA does not exist"

ASA_NOT_ARC3_COMPLIANT: LiteralString = "AsaNotArc3Compliant"
ASA_NOT_ARC3_COMPLIANT_DES = "Invalid ARC-3 parameters (name or URL)"

ASA_NOT_ARC54_COMPLIANT: LiteralString = "AsaNotArc54Compliant"
ASA_NOT_ARC54_COMPLIANT_DES = "The ASA must not have a clawback address"

ASA_NOT_ARC89_COMPLIANT: LiteralString = "AsaNotArc89Compliant"
ASA_NOT_ARC89_COMPLIANT_DES = "Invalid ARC-89 partial URI"

ASA_METADATA_HASH_MISMATCH: LiteralString = "AsaMetadataHashMismatch"
ASA_METADATA_HASH_MISMATCH_DES = (
    "ASA Metadata Hash (am) does not match the computed hash"
)

# ── Metadata ──────────────────────────────────────────────────────────────────
ASSET_METADATA_EXIST: LiteralString = "AssetMetadataExist"
ASSET_METADATA_EXIST_DES = "Asset Metadata already exists for the specified ASA"

ASSET_METADATA_NOT_EXIST: LiteralString = "AssetMetadataNotExist"
ASSET_METADATA_NOT_EXIST_DES = "Asset Metadata does not exist for the specified ASA"

EMPTY_METADATA: LiteralString = "EmptyMetadata"
EMPTY_METADATA_DES = "Metadata is empty"

METADATA_SIZE_MISMATCH: LiteralString = "MetadataSizeMismatch"
METADATA_SIZE_MISMATCH_DES = (
    "Metadata size mismatch, must be exactly equal to declared size"
)

METADATA_NOT_SHORT: LiteralString = "MetadataNotShort"
METADATA_NOT_SHORT_DES = "Metadata is not short"

REQUIRES_IMMUTABLE: LiteralString = "RequiresImmutable"
REQUIRES_IMMUTABLE_DES = "Must be flagged as immutable"

IMMUTABLE: LiteralString = "Immutable"
IMMUTABLE_DES = "Metadata is immutable"

# ── Metadata Size ─────────────────────────────────────────────────────────────
EXCEEDS_MAX_METADATA_SIZE: LiteralString = "ExceedsMaxMetadataSize"
EXCEEDS_MAX_METADATA_SIZE_DES = "Invalid Metadata size, exceeds maximum allowed size"

EXCEEDS_METADATA_SIZE: LiteralString = "ExceedsMetadataSize"
EXCEEDS_METADATA_SIZE_DES = "Slice exceeds metadata range"

EXCEEDS_PAGE_SIZE: LiteralString = "ExceedsPageSize"
EXCEEDS_PAGE_SIZE_DES = "Payload exceeds page size"

LARGER_METADATA_SIZE: LiteralString = "LargerMetadataSize"
LARGER_METADATA_SIZE_DES = (
    "Invalid Metadata size, must be smaller than or equal to the current size"
)

SMALLER_METADATA_SIZE: LiteralString = "SmallerMetadataSize"
SMALLER_METADATA_SIZE_DES = (
    "Invalid Metadata size, must be larger than the current size"
)

# ── Payload ───────────────────────────────────────────────────────────────────
NO_PAYLOAD_HEAD_CALL: LiteralString = "NoPayloadHeadCall"
NO_PAYLOAD_HEAD_CALL_DES = "No payload head call in Group"

PAYLOAD_OVERFLOW: LiteralString = "PayloadOverflow"
PAYLOAD_OVERFLOW_DES = "Payload exceeds metadata size"

# ── MBR ───────────────────────────────────────────────────────────────────────
MBR_DELTA_RECEIVER_INVALID: LiteralString = "MbrDeltaReceiverInvalid"
MBR_DELTA_RECEIVER_INVALID_DES = (
    "Invalid MBR Delta receiver, must be the ASA Metadata Registry"
)

MBR_DELTA_AMOUNT_INVALID: LiteralString = "mbrDeltaAmountInvalid"
MBR_DELTA_AMOUNT_INVALID_DES = "Invalid MBR Delta amount"

# ── Indexes ───────────────────────────────────────────────────────────────────
FLAG_IDX_INVALID: LiteralString = "FlagIdxInvalid"
FLAG_IDX_INVALID_DES = "Invalid flag index"

PAGE_IDX_INVALID: LiteralString = "PageIdxInvalid"
PAGE_IDX_INVALID_DES = "Invalid page index"

# ── Encoding ──────────────────────────────────────────────────────────────────
B64_ENCODING_INVALID: LiteralString = "B64EncodingInvalid"
B64_ENCODING_INVALID_DES = "Invalid base64 encoding, must be 0 (URL safe) or 1 (Std)"

# ── Registry ──────────────────────────────────────────────────────────────────
NEW_REGISTRY_ID_INVALID: LiteralString = "NewRegistryIdInvalid"
NEW_REGISTRY_ID_INVALID_DES = (
    "Invalid new ASA Metadata Registry ID, must be different from current"
)
