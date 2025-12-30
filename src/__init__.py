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

from smart_contracts import constants
from smart_contracts.asa_metadata_registry import enums, flags

from . import bitmasks
from .codec import Arc90Compliance, Arc90Uri, build_netauth_from_env
from .deployments import (
    DEFAULT_DEPLOYMENTS,
)
from .errors import (
    AsaMetadataRegistryError,
    AsaNotFoundError,
    BoxNotFoundError,
    BoxParseError,
    InvalidArc90UriError,
    MetadataArc3Error,
    MetadataDriftError,
    MetadataEncodingError,
    MetadataNotFoundError,
    MissingAppClientError,
    RegistryResolutionError,
)

__all__ = [
    # Deployments
    "DEFAULT_DEPLOYMENTS",
    # Codec
    "Arc90Uri",
    "Arc90Compliance",
    "build_netauth_from_env",
    # Errors
    "AsaMetadataRegistryError",
    "AsaNotFoundError",
    "BoxNotFoundError",
    "BoxParseError",
    "InvalidArc90UriError",
    "MetadataArc3Error",
    "MetadataDriftError",
    "MetadataEncodingError",
    "MetadataNotFoundError",
    "MissingAppClientError",
    "RegistryResolutionError",
    # Bitmasks
    "bitmasks",
    # Constants
    "constants",
    # Enums
    "enums",
    # Flags
    "flags",
]
