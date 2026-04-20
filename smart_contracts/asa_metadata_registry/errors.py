from typing import LiteralString

# ── Auth ─────────────────────────────────────────────────────────────────────
# The deployer address is not trusted
UNTRUSTED_DEPLOYER: LiteralString = "untrustedDeployer"

# Unauthorized, it must be the Asset Manager
UNAUTHORIZED: LiteralString = "unauthorized"

# ── ASA ───────────────────────────────────────────────────────────────────────
# The specified ASA does not exist
ASA_NOT_EXIST: LiteralString = "asaNotExist"

# Invalid ARC-3 parameters (name or URL)
ASA_NOT_ARC3_COMPLIANT: LiteralString = "asaNotArc3Compliant"

# The ASA must not have a clawback address
ASA_NOT_ARC54_COMPLIANT: LiteralString = "asaNotArc54Compliant"

# Invalid ARC-89 partial URI
ASA_NOT_ARC89_COMPLIANT: LiteralString = "asaNotArc89Compliant"

# ASA Metadata Hash (am) does not match the computed hash
ASA_METADATA_HASH_MISMATCH: LiteralString = "asaMetadataHashMismatch"

# ── Metadata ──────────────────────────────────────────────────────────────────
# Asset Metadata already exists for the specified ASA
ASSET_METADATA_EXIST: LiteralString = "assetMetadataExist"

# Asset Metadata does not exist for the specified ASA
ASSET_METADATA_NOT_EXIST: LiteralString = "assetMetadataNotExist"

# Metadata is empty
EMPTY_METADATA: LiteralString = "emptyMetadata"

# Metadata size mismatch, it must be exactly equal to declared size
METADATA_SIZE_MISMATCH: LiteralString = "metadataSizeMismatch"

# Metadata is not short
METADATA_NOT_SHORT: LiteralString = "metadataNotShort"

# Must be flagged as immutable
REQUIRES_IMMUTABLE: LiteralString = "requiresImmutable"

# Metadata is immutable
IMMUTABLE: LiteralString = "immutable"

# ── Metadata Size ─────────────────────────────────────────────────────────────
# Invalid Metadata size, exceeds maximum allowed size
EXCEEDS_MAX_METADATA_SIZE: LiteralString = "exceedsMaxMetadataSize"

# Slice exceeds metadata range
EXCEEDS_METADATA_SIZE: LiteralString = "exceedsMetadataSize"

# Payload exceeds page size
EXCEEDS_PAGE_SIZE: LiteralString = "exceedsPageSize"

# Invalid Metadata size, it must be smaller than or equal to the current size
LARGER_METADATA_SIZE: LiteralString = "largerMetadataSize"

# Invalid Metadata size, it must be larger than the current size
SMALLER_METADATA_SIZE: LiteralString = "smallerMetadataSize"

# ── Payload ───────────────────────────────────────────────────────────────────
# No payload head call in Group
NO_PAYLOAD_HEAD_CALL: LiteralString = "noPayloadHeadCall"

# Payload exceeds metadata size
PAYLOAD_OVERFLOW: LiteralString = "payloadOverflow"

# ── MBR ───────────────────────────────────────────────────────────────────────
# Invalid MBR Delta receiver, it must be the ASA Metadata Registry
MBR_DELTA_RECEIVER_INVALID: LiteralString = "mbrDeltaReceiverInvalid"

# Invalid MBR Delta amount
MBR_DELTA_AMOUNT_INVALID: LiteralString = "mbrDeltaAmountInvalid"

# ── Indexes ───────────────────────────────────────────────────────────────────
# Invalid flag index
FLAG_IDX_INVALID: LiteralString = "flagIdxInvalid"

# Invalid page index
PAGE_IDX_INVALID: LiteralString = "pageIdxInvalid"

# ── Encoding ──────────────────────────────────────────────────────────────────
# Invalid base64 encoding, must be 0 (URL safe) or 1 (Std)
B64_ENCODING_INVALID: LiteralString = "b64EncodingInvalid"

# ── Registry ──────────────────────────────────────────────────────────────────
# Invalid new ASA Metadata Registry ID, it must be different from current
NEW_REGISTRY_ID_INVALID: LiteralString = "newRegistryIdInvalid"
