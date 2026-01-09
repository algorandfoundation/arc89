from __future__ import annotations


class AsaMetadataRegistryError(Exception):
    """Base class for all SDK errors."""


class MissingAppClientError(AsaMetadataRegistryError):
    """Raised when an operation requires the generated AppClient but none is configured."""


class InvalidArc90UriError(AsaMetadataRegistryError, ValueError):
    """Raised when an ARC-90 URI cannot be parsed or is not compatible with ARC-89."""


class AsaNotFoundError(AsaMetadataRegistryError, LookupError):
    """Raised when an ASA is not found on-chain."""


class MetadataNotFoundError(AsaMetadataRegistryError, LookupError):
    """Raised when the ASA exists but metadata is not present in the registry."""


class BoxNotFoundError(AsaMetadataRegistryError, LookupError):
    """Raised when the expected metadata box does not exist."""


class BoxParseError(AsaMetadataRegistryError, ValueError):
    """Raised when a metadata box value cannot be parsed according to ARC-89."""


class InvalidFlagIndexError(AsaMetadataRegistryError, ValueError):
    """Raised when a flag index (reversible/irreversible) is out of bounds."""


class InvalidPageIndexError(AsaMetadataRegistryError, ValueError):
    """Raised when a page index is out of bounds."""


class MetadataEncodingError(AsaMetadataRegistryError, ValueError):
    """Raised when metadata bytes are not valid UTF-8 JSON object encoding (RFC 8259)."""


class MetadataArc3Error(AsaMetadataRegistryError, ValueError):
    """
    Raised when metadata bytes decode to valid UTF-8 JSON but the resulting object
    does not conform to the ARC-3 JSON schema.
    """


class MetadataDriftError(AsaMetadataRegistryError, RuntimeError):
    """
    Raised when paginated metadata reads detect that metadata changed between pages
    (last_modified_round mismatch).
    """


class RegistryResolutionError(AsaMetadataRegistryError, RuntimeError):
    """Raised when the registry app id cannot be resolved from inputs."""


class MetadataHashMismatchError(AsaMetadataRegistryError, ValueError):
    """
    Raised when the ASA metadata hash (am) does not match the computed hash.

    Per ARC-89: if an ASA has a non-zero metadata hash and is flagged as ARC89 native
    but not ARC3 compliant, the ASA's metadata hash must match the computed hash.
    """
