import json
from collections.abc import Mapping

from .errors import MetadataArc3Error, MetadataEncodingError


def decode_metadata_json(metadata: bytes) -> dict[str, object]:
    """
    Decode ARC-89 metadata bytes into a Python dict.

    ARC-89 requires a UTF-8 JSON *object*. Empty metadata bytes MUST be treated as `{}`.
    """
    if metadata == b"":
        return {}

    # Reject UTF-8 BOM
    if metadata.startswith(b"\xef\xbb\xbf"):
        raise MetadataEncodingError("Metadata MUST NOT include a UTF-8 BOM")

    try:
        txt = metadata.decode("utf-8")
    except UnicodeDecodeError as e:
        raise MetadataEncodingError("Metadata is not valid UTF-8") from e

    try:
        obj: object = json.loads(txt)
    except json.JSONDecodeError as e:
        raise MetadataEncodingError("Metadata is not valid JSON") from e

    if not isinstance(obj, dict):
        raise MetadataEncodingError("Metadata JSON MUST be an object")
    return obj


def encode_metadata_json(obj: Mapping[str, object]) -> bytes:
    """
    Encode a JSON object to UTF-8 bytes without BOM.

    The encoding is not canonicalized beyond `json.dumps` defaults; ARC-89 hashing uses raw bytes.
    """
    try:
        txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as e:
        raise MetadataEncodingError("Object is not JSON-serializable") from e
    data = txt.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        raise MetadataEncodingError("Produced UTF-8 BOM; this should not happen")
    return data


def validate_arc3_schema(obj: Mapping[str, object]) -> None:
    """
    Validate that a JSON object conforms to the ARC-3 JSON metadata schema according
    to ARC-3 (https://dev.algorand.co/arc-standards/arc-0003/#json-metadata-file-schema).

    Raises MetadataArc3Error if validation fails.
    """
    # Define ARC-3 schema field types
    string_fields = {
        "name",
        "description",
        "image",
        "image_integrity",
        "image_mimetype",
        "background_color",
        "external_url",
        "external_url_integrity",
        "external_url_mimetype",
        "animation_url",
        "animation_url_integrity",
        "animation_url_mimetype",
        "unitName",
        "extra_metadata",
    }

    # Note: this implementation requires 'decimals' to be a non-negative integer
    # and 'unitName' to be a string (see string_fields above).

    for key, value in obj.items():
        if key == "decimals":
            # decimals must be an integer (non-negative)
            if not isinstance(value, int) or isinstance(value, bool):
                raise MetadataArc3Error(
                    f"ARC-3 field 'decimals' must be an integer, got {type(value).__name__}"
                )
            if value < 0:
                raise MetadataArc3Error(
                    f"ARC-3 field 'decimals' must be non-negative, got {value}"
                )
        elif key == "properties":
            if not isinstance(value, dict):
                raise MetadataArc3Error(
                    f"ARC-3 field 'properties' must be an object, got {type(value).__name__}"
                )
        elif key == "localization":
            if not isinstance(value, dict):
                raise MetadataArc3Error(
                    f"ARC-3 field 'localization' must be an object, got {type(value).__name__}"
                )
            # Validate localization structure (must have 'uri' and 'default' and 'locales')
            if "uri" not in value:
                raise MetadataArc3Error(
                    "ARC-3 'localization' object must have 'uri' field"
                )
            if "default" not in value:
                raise MetadataArc3Error(
                    "ARC-3 'localization' object must have 'default' field"
                )
            if "locales" not in value:
                raise MetadataArc3Error(
                    "ARC-3 'localization' object must have 'locales' field"
                )
            if not isinstance(value["uri"], str):
                raise MetadataArc3Error("ARC-3 'localization.uri' must be a string")
            if not isinstance(value["default"], str):
                raise MetadataArc3Error("ARC-3 'localization.default' must be a string")
            if not isinstance(value["locales"], list):
                raise MetadataArc3Error("ARC-3 'localization.locales' must be an array")
            for locale in value["locales"]:
                if not isinstance(locale, str):
                    raise MetadataArc3Error(
                        "ARC-3 'localization.locales' entries must be strings"
                    )
        elif key in string_fields:
            if not isinstance(value, str):
                raise MetadataArc3Error(
                    f"ARC-3 field '{key}' must be a string, got {type(value).__name__}"
                )
        # Other fields are allowed (for extensibility) but we don't validate them
