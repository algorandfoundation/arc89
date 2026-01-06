"""
Unit tests for JSON encoding/decoding and ARC-3 validation in src.models.

Tests cover:
- decode_metadata_json
- encode_metadata_json
- validate_arc3_schema
- _chunk_metadata_payload helper
"""

import pytest

from asa_metadata_registry import (
    MetadataArc3Error,
    MetadataEncodingError,
    decode_metadata_json,
    encode_metadata_json,
    validate_arc3_schema,
)
from asa_metadata_registry.models import _chunk_metadata_payload


class TestChunkMetadataPayload:
    """Tests for _chunk_metadata_payload helper function."""

    def test_empty_data(self) -> None:
        """Test chunking empty data."""
        chunks = _chunk_metadata_payload(b"", head_max_size=10, extra_max_size=5)
        assert chunks == [b""]

    def test_data_fits_in_head(self) -> None:
        """Test data that fits entirely in head chunk."""
        data = b"hello"
        chunks = _chunk_metadata_payload(data, head_max_size=10, extra_max_size=5)
        assert len(chunks) == 1
        assert chunks[0] == b"hello"

    def test_data_exactly_head_size(self) -> None:
        """Test data that exactly fills head chunk."""
        data = b"x" * 10
        chunks = _chunk_metadata_payload(data, head_max_size=10, extra_max_size=5)
        assert len(chunks) == 1
        assert chunks[0] == data

    def test_data_needs_one_extra_chunk(self) -> None:
        """Test data that needs one extra chunk."""
        data = b"x" * 15
        chunks = _chunk_metadata_payload(data, head_max_size=10, extra_max_size=5)
        assert len(chunks) == 2
        assert chunks[0] == b"x" * 10
        assert chunks[1] == b"x" * 5

    def test_data_needs_multiple_extra_chunks(self) -> None:
        """Test data that needs multiple extra chunks."""
        data = b"a" * 25
        chunks = _chunk_metadata_payload(data, head_max_size=10, extra_max_size=5)
        assert len(chunks) == 4
        assert chunks[0] == b"a" * 10
        assert chunks[1] == b"a" * 5
        assert chunks[2] == b"a" * 5
        assert chunks[3] == b"a" * 5

    def test_data_partial_last_chunk(self) -> None:
        """Test data with partial last chunk."""
        data = b"b" * 23
        chunks = _chunk_metadata_payload(data, head_max_size=10, extra_max_size=5)
        assert len(chunks) == 4
        assert chunks[0] == b"b" * 10
        assert chunks[1] == b"b" * 5
        assert chunks[2] == b"b" * 5
        assert chunks[3] == b"b" * 3

    def test_invalid_head_size_zero(self) -> None:
        """Test that head_max_size=0 raises ValueError."""
        with pytest.raises(ValueError, match="Chunk sizes must be > 0"):
            _chunk_metadata_payload(b"data", head_max_size=0, extra_max_size=5)

    def test_invalid_extra_size_zero(self) -> None:
        """Test that extra_max_size=0 raises ValueError."""
        with pytest.raises(ValueError, match="Chunk sizes must be > 0"):
            _chunk_metadata_payload(b"data", head_max_size=10, extra_max_size=0)

    def test_invalid_negative_head_size(self) -> None:
        """Test that negative head_max_size raises ValueError."""
        with pytest.raises(ValueError, match="Chunk sizes must be > 0"):
            _chunk_metadata_payload(b"data", head_max_size=-1, extra_max_size=5)


class TestDecodeMetadataJson:
    """Tests for decode_metadata_json function."""

    def test_empty_bytes(self) -> None:
        """Test that empty bytes decode to empty dict."""
        result = decode_metadata_json(b"")
        assert result == {}

    def test_simple_object(self) -> None:
        """Test decoding simple JSON object."""
        data = b'{"name":"Test","value":123}'
        result = decode_metadata_json(data)
        assert result == {"name": "Test", "value": 123}

    def test_nested_object(self) -> None:
        """Test decoding nested JSON object."""
        data = b'{"outer":{"inner":"value"}}'
        result = decode_metadata_json(data)
        assert result == {"outer": {"inner": "value"}}

    def test_unicode_content(self) -> None:
        """Test decoding JSON with Unicode characters."""
        data = '{"emoji":"🎉","chinese":"你好"}'.encode()
        result = decode_metadata_json(data)
        assert result == {"emoji": "🎉", "chinese": "你好"}

    def test_with_utf8_bom_raises(self) -> None:
        """Test that UTF-8 BOM is rejected."""
        data = b"\xef\xbb\xbf" + b'{"name":"Test"}'
        with pytest.raises(MetadataEncodingError, match="MUST NOT include a UTF-8 BOM"):
            decode_metadata_json(data)

    def test_invalid_utf8_raises(self) -> None:
        """Test that invalid UTF-8 raises MetadataEncodingError."""
        data = b"\xff\xfe invalid utf-8"
        with pytest.raises(MetadataEncodingError, match="not valid UTF-8"):
            decode_metadata_json(data)

    def test_invalid_json_raises(self) -> None:
        """Test that invalid JSON raises MetadataEncodingError."""
        data = b'{"invalid json'
        with pytest.raises(MetadataEncodingError, match="not valid JSON"):
            decode_metadata_json(data)

    def test_json_array_raises(self) -> None:
        """Test that JSON array (not object) raises MetadataEncodingError."""
        data = b"[1,2,3]"
        with pytest.raises(MetadataEncodingError, match="MUST be an object"):
            decode_metadata_json(data)

    def test_json_string_raises(self) -> None:
        """Test that JSON string raises MetadataEncodingError."""
        data = b'"just a string"'
        with pytest.raises(MetadataEncodingError, match="MUST be an object"):
            decode_metadata_json(data)

    def test_json_number_raises(self) -> None:
        """Test that JSON number raises MetadataEncodingError."""
        data = b"42"
        with pytest.raises(MetadataEncodingError, match="MUST be an object"):
            decode_metadata_json(data)

    def test_json_null_raises(self) -> None:
        """Test that JSON null raises MetadataEncodingError."""
        data = b"null"
        with pytest.raises(MetadataEncodingError, match="MUST be an object"):
            decode_metadata_json(data)


class TestEncodeMetadataJson:
    """Tests for encode_metadata_json function."""

    def test_empty_dict(self) -> None:
        """Test encoding empty dict."""
        result = encode_metadata_json({})
        assert result == b"{}"

    def test_simple_object(self) -> None:
        """Test encoding simple object."""
        obj = {"name": "Test", "value": 123}
        result = encode_metadata_json(obj)
        # Note: json.dumps with separators=(',',':') produces compact JSON
        assert result == b'{"name":"Test","value":123}'

    def test_nested_object(self) -> None:
        """Test encoding nested object."""
        obj = {"outer": {"inner": "value"}}
        result = encode_metadata_json(obj)
        assert result == b'{"outer":{"inner":"value"}}'

    def test_unicode_content(self) -> None:
        """Test encoding Unicode content."""
        obj = {"emoji": "🎉", "chinese": "你好"}
        result = encode_metadata_json(obj)
        # ensure_ascii=False means Unicode chars are preserved
        decoded = result.decode("utf-8")
        assert "🎉" in decoded
        assert "你好" in decoded

    def test_no_utf8_bom(self) -> None:
        """Test that encoding doesn't produce UTF-8 BOM."""
        obj = {"name": "Test"}
        result = encode_metadata_json(obj)
        assert not result.startswith(b"\xef\xbb\xbf")

    def test_non_serializable_raises(self) -> None:
        """Test that non-JSON-serializable object raises MetadataEncodingError."""
        obj = {"func": lambda x: x}  # Functions aren't JSON-serializable
        with pytest.raises(MetadataEncodingError, match="not JSON-serializable"):
            encode_metadata_json(obj)

    def test_round_trip(self) -> None:
        """Test encode -> decode round trip."""
        original = {"name": "Test", "value": 123, "nested": {"key": "val"}}
        encoded = encode_metadata_json(original)
        decoded = decode_metadata_json(encoded)
        assert decoded == original


class TestValidateArc3Schema:
    """Tests for validate_arc3_schema function."""

    def test_empty_object(self) -> None:
        """Test that empty object is valid."""
        validate_arc3_schema({})  # Should not raise

    def test_valid_name(self) -> None:
        """Test valid name field."""
        validate_arc3_schema({"name": "My Token"})

    def test_valid_decimals(self) -> None:
        """Test valid decimals field as integer."""
        validate_arc3_schema({"decimals": 6})

    def test_decimals_zero(self) -> None:
        """Test decimals=0 is valid."""
        validate_arc3_schema({"decimals": 0})

    def test_decimals_string_raises(self) -> None:
        """Test that decimals as string raises."""
        with pytest.raises(MetadataArc3Error, match="'decimals' must be an integer"):
            validate_arc3_schema({"decimals": "6"})

    def test_decimals_negative_raises(self) -> None:
        """Test that negative decimals raises."""
        with pytest.raises(MetadataArc3Error, match="must be non-negative"):
            validate_arc3_schema({"decimals": -1})

    def test_decimals_boolean_raises(self) -> None:
        """Test that boolean for decimals raises (even though True==1 in Python)."""
        with pytest.raises(MetadataArc3Error, match="'decimals' must be an integer"):
            validate_arc3_schema({"decimals": True})

    def test_valid_description(self) -> None:
        """Test valid description field."""
        validate_arc3_schema({"description": "A test token"})

    def test_description_non_string_raises(self) -> None:
        """Test that non-string description raises."""
        with pytest.raises(MetadataArc3Error, match="'description' must be a string"):
            validate_arc3_schema({"description": 123})

    def test_valid_image(self) -> None:
        """Test valid image field."""
        validate_arc3_schema({"image": "https://example.com/image.png"})

    def test_image_non_string_raises(self) -> None:
        """Test that non-string image raises."""
        with pytest.raises(MetadataArc3Error, match="'image' must be a string"):
            validate_arc3_schema({"image": 123})

    def test_valid_properties(self) -> None:
        """Test valid properties field."""
        validate_arc3_schema({"properties": {"custom": "value"}})

    def test_properties_non_object_raises(self) -> None:
        """Test that non-object properties raises."""
        with pytest.raises(MetadataArc3Error, match="'properties' must be an object"):
            validate_arc3_schema({"properties": "not an object"})

    def test_valid_localization(self) -> None:
        """Test valid localization field."""
        validate_arc3_schema(
            {
                "localization": {
                    "uri": "https://example.com/{locale}.json",
                    "default": "en",
                    "locales": ["en", "es", "fr"],
                }
            }
        )

    def test_localization_missing_uri_raises(self) -> None:
        """Test that localization without uri raises."""
        with pytest.raises(MetadataArc3Error, match="must have 'uri' field"):
            validate_arc3_schema({"localization": {"default": "en", "locales": ["en"]}})

    def test_localization_missing_default_raises(self) -> None:
        """Test that localization without default raises."""
        with pytest.raises(MetadataArc3Error, match="must have 'default' field"):
            validate_arc3_schema(
                {"localization": {"uri": "https://example.com", "locales": ["en"]}}
            )

    def test_localization_missing_locales_raises(self) -> None:
        """Test that localization without locales raises."""
        with pytest.raises(MetadataArc3Error, match="must have 'locales' field"):
            validate_arc3_schema(
                {"localization": {"uri": "https://example.com", "default": "en"}}
            )

    def test_localization_uri_non_string_raises(self) -> None:
        """Test that non-string localization.uri raises."""
        with pytest.raises(
            MetadataArc3Error, match=r"'localization.uri' must be a string"
        ):
            validate_arc3_schema(
                {
                    "localization": {
                        "uri": 123,
                        "default": "en",
                        "locales": ["en"],
                    }
                }
            )

    def test_localization_default_non_string_raises(self) -> None:
        """Test that non-string localization.default raises."""
        with pytest.raises(
            MetadataArc3Error, match=r"'localization.default' must be a string"
        ):
            validate_arc3_schema(
                {
                    "localization": {
                        "uri": "https://example.com",
                        "default": 123,
                        "locales": ["en"],
                    }
                }
            )

    def test_localization_locales_non_array_raises(self) -> None:
        """Test that non-array localization.locales raises."""
        with pytest.raises(
            MetadataArc3Error, match=r"'localization.locales' must be an array"
        ):
            validate_arc3_schema(
                {
                    "localization": {
                        "uri": "https://example.com",
                        "default": "en",
                        "locales": "en",
                    }
                }
            )

    def test_localization_locales_non_string_entry_raises(self) -> None:
        """Test that non-string entry in localization.locales raises."""
        with pytest.raises(MetadataArc3Error, match="entries must be strings"):
            validate_arc3_schema(
                {
                    "localization": {
                        "uri": "https://example.com",
                        "default": "en",
                        "locales": ["en", 123],
                    }
                }
            )

    def test_valid_unit_name(self) -> None:
        """Test valid unitName field."""
        validate_arc3_schema({"unitName": "TKN"})

    def test_unit_name_non_string_raises(self) -> None:
        """Test that non-string unitName raises."""
        with pytest.raises(MetadataArc3Error, match="'unitName' must be a string"):
            validate_arc3_schema({"unitName": 123})

    def test_valid_all_string_fields(self) -> None:
        """Test all valid string fields."""
        validate_arc3_schema(
            {
                "name": "Token",
                "description": "Description",
                "image": "https://example.com/img.png",
                "image_integrity": "sha256-abc123",
                "image_mimetype": "image/png",
                "background_color": "#FFFFFF",
                "external_url": "https://example.com",
                "external_url_integrity": "sha256-def456",
                "external_url_mimetype": "text/html",
                "animation_url": "https://example.com/anim.mp4",
                "animation_url_integrity": "sha256-ghi789",
                "animation_url_mimetype": "video/mp4",
                "unitName": "TKN",
                "extra_metadata": "extra",
            }
        )

    def test_extensible_custom_fields(self) -> None:
        """Test that custom fields are allowed (extensibility)."""
        validate_arc3_schema(
            {
                "name": "Token",
                "custom_field": "custom_value",
                "another_field": 123,
            }
        )  # Should not raise

    def test_complete_arc3_example(self) -> None:
        """Test complete ARC-3 compliant metadata."""
        validate_arc3_schema(
            {
                "name": "My Asset",
                "decimals": 0,
                "description": "A test NFT",
                "image": "https://example.com/image.png",
                "image_integrity": "sha256-abcdef",
                "properties": {
                    "trait1": "value1",
                    "trait2": "value2",
                },
            }
        )
