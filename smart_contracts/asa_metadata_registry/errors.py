from typing import LiteralString

# ── Auth ─────────────────────────────────────────────────────────────────────
# The deployer address is not trusted
UNTRUSTED_DEPLOYER: LiteralString = "UntrustedDeployer"

# Unauthorized, it must be the Asset Manager
UNAUTHORIZED: LiteralString = "Unauthorized"

# ── ASA ───────────────────────────────────────────────────────────────────────
# The specified ASA does not exist
ASA_NOT_EXIST: LiteralString = "AsaNotExist"

# Invalid ARC-3 parameters (name or URL)
ASA_NOT_ARC3_COMPLIANT: LiteralString = "AsaNotArc3Compliant"

# The ASA must not have a clawback address
ASA_NOT_ARC54_COMPLIANT: LiteralString = "AsaNotArc54Compliant"

# Invalid ARC-89 partial URI
ASA_NOT_ARC89_COMPLIANT: LiteralString = "AsaNotArc89Compliant"

# ASA Metadata Hash (am) does not match the computed hash
ASA_METADATA_HASH_MISMATCH: LiteralString = "AsaMetadataHashMismatch"

# ── Metadata ──────────────────────────────────────────────────────────────────
# Asset Metadata already exists for the specified ASA
ASSET_METADATA_EXIST: LiteralString = "AssetMetadataExist"

# Asset Metadata does not exist for the specified ASA
ASSET_METADATA_NOT_EXIST: LiteralString = "AssetMetadataNotExist"

# Metadata is empty
EMPTY_METADATA: LiteralString = "EmptyMetadata"

# Metadata size mismatch, it must be exactly equal to declared size
METADATA_SIZE_MISMATCH: LiteralString = "MetadataSizeMismatch"

# Metadata is not short
METADATA_NOT_SHORT: LiteralString = "MetadataNotShort"

# Must be flagged as immutable
REQUIRES_IMMUTABLE: LiteralString = "RequiresImmutable"

# Metadata is immutable
IMMUTABLE: LiteralString = "Immutable"

# ── Metadata Size ─────────────────────────────────────────────────────────────
# Invalid Metadata size, exceeds maximum allowed size
EXCEEDS_MAX_METADATA_SIZE: LiteralString = "ExceedsMaxMetadataSize"

# Slice exceeds metadata range
EXCEEDS_METADATA_SIZE: LiteralString = "ExceedsMetadataSize"

# Payload exceeds page size
EXCEEDS_PAGE_SIZE: LiteralString = "ExceedsPageSize"

# Invalid Metadata size, it must be smaller than or equal to the current size
LARGER_METADATA_SIZE: LiteralString = "LargerMetadataSize"

# Invalid Metadata size, it must be larger than the current size
SMALLER_METADATA_SIZE: LiteralString = "SmallerMetadataSize"

# ── Payload ───────────────────────────────────────────────────────────────────
# No payload head call in Group
NO_PAYLOAD_HEAD_CALL: LiteralString = "NoPayloadHeadCall"

# Payload exceeds metadata size
PAYLOAD_OVERFLOW: LiteralString = "PayloadOverflow"

# ── MBR ───────────────────────────────────────────────────────────────────────
# Invalid MBR Delta receiver, it must be the ASA Metadata Registry
MBR_DELTA_RECEIVER_INVALID: LiteralString = "MbrDeltaReceiverInvalid"

# Invalid MBR Delta amount
MBR_DELTA_AMOUNT_INVALID: LiteralString = "mbrDeltaAmountInvalid"

# ── Indexes ───────────────────────────────────────────────────────────────────
# Invalid flag index
FLAG_IDX_INVALID: LiteralString = "FlagIdxInvalid"

# Invalid page index
PAGE_IDX_INVALID: LiteralString = "PageIdxInvalid"

# ── Encoding ──────────────────────────────────────────────────────────────────
# Invalid base64 encoding, must be 0 (URL safe) or 1 (Std)
B64_ENCODING_INVALID: LiteralString = "B64EncodingInvalid"

# ── Registry ──────────────────────────────────────────────────────────────────
# Invalid new ASA Metadata Registry ID, it must be different from current
NEW_REGISTRY_ID_INVALID: LiteralString = "NewRegistryIdInvalid"
