# ruff: noqa: RUF022
"""
ASA Metadata Registry Python SDK.

Public entrypoints:
- :class:`asa_metadata_registry.registry.AsaMetadataRegistry`
- :class:`asa_metadata_registry.read.reader.AsaMetadataRegistryRead`
- :class:`asa_metadata_registry.write.writer.AsaMetadataRegistryWrite`

This SDK is designed around ARC-89 (ASA Metadata Registry) and integrates with
an AlgoKit-generated ARC-56 AppClient for simulation and write operations.
"""

from __future__ import annotations

from . import bitmasks, constants, enums, flags
from .codec import Arc90Compliance, Arc90Uri, complete_partial_asset_url
from .deployments import DEFAULT_DEPLOYMENTS
from .errors import (
    AsaMetadataRegistryError,
    AsaNotFoundError,
    BoxNotFoundError,
    BoxParseError,
    InvalidArc90UriError,
    InvalidFlagIndexError,
    InvalidPageIndexError,
    MetadataArc3Error,
    MetadataDriftError,
    MetadataEncodingError,
    MetadataHashMismatchError,
    MetadataNotFoundError,
    MissingAppClientError,
    RegistryResolutionError,
)
from .hashing import (
    compute_arc3_metadata_hash,
    compute_header_hash,
    compute_metadata_hash,
    compute_page_hash,
)
from .models import (
    AssetMetadata,
    AssetMetadataBox,
    AssetMetadataRecord,
    IrreversibleFlags,
    MbrDelta,
    MbrDeltaSign,
    MetadataBody,
    MetadataExistence,
    MetadataFlags,
    MetadataHeader,
    PaginatedMetadata,
    Pagination,
    RegistryParameters,
    ReversibleFlags,
    get_default_registry_params,
)
from .read.avm import SimulateOptions
from .read.reader import AsaMetadataRegistryRead, MetadataSource
from .registry import AsaMetadataRegistry, RegistryConfig
from .validation import (
    decode_metadata_json,
    encode_metadata_json,
    is_arc3_metadata,
    validate_arc3_schema,
)
from .write.writer import AsaMetadataRegistryWrite, WriteOptions

__all__ = [
    # Deployments
    "DEFAULT_DEPLOYMENTS",
    # Facade
    "AsaMetadataRegistry",
    "RegistryConfig",
    # Read/Write helpers
    "AsaMetadataRegistryRead",
    "AsaMetadataRegistryWrite",
    "MetadataSource",
    "SimulateOptions",
    "WriteOptions",
    # Codec
    "Arc90Uri",
    "Arc90Compliance",
    "complete_partial_asset_url",
    # Errors
    "AsaMetadataRegistryError",
    "AsaNotFoundError",
    "BoxNotFoundError",
    "BoxParseError",
    "InvalidArc90UriError",
    "InvalidFlagIndexError",
    "InvalidPageIndexError",
    "MetadataArc3Error",
    "MetadataDriftError",
    "MetadataEncodingError",
    "MetadataHashMismatchError",
    "MetadataNotFoundError",
    "MissingAppClientError",
    "RegistryResolutionError",
    # Models
    "AssetMetadata",
    "AssetMetadataBox",
    "AssetMetadataRecord",
    "IrreversibleFlags",
    "MbrDelta",
    "MbrDeltaSign",
    "MetadataBody",
    "MetadataExistence",
    "MetadataFlags",
    "MetadataHeader",
    "PaginatedMetadata",
    "Pagination",
    "RegistryParameters",
    "ReversibleFlags",
    "get_default_registry_params",
    # Bitmasks
    "bitmasks",
    # Constants
    "constants",
    # Enums
    "enums",
    # Flags
    "flags",
    # Hashing
    "compute_arc3_metadata_hash",
    "compute_header_hash",
    "compute_page_hash",
    "compute_metadata_hash",
    # Validation
    "encode_metadata_json",
    "decode_metadata_json",
    "is_arc3_metadata",
    "validate_arc3_schema",
]
