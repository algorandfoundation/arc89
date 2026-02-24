import pytest

from asa_metadata_registry.errors import (
    InvalidArc3PropertiesError,
    MetadataArc3Error,
    MetadataEncodingError,
)
from asa_metadata_registry.validation import (
    decode_metadata_json,
    encode_metadata_json,
    is_arc3_metadata,
    is_positive_uint64,
    validate_arc3_properties,
    validate_arc3_schema,
    validate_arc3_values,
    validate_arc20_arc62_require_arc3,
)


class TestIsPositiveUint64:
    def test_valid_min(self) -> None:
        assert is_positive_uint64(1) is True

    def test_valid_max(self) -> None:
        assert is_positive_uint64(2**64 - 1) is True

    def test_zero_invalid(self) -> None:
        assert is_positive_uint64(0) is False

    def test_negative_invalid(self) -> None:
        assert is_positive_uint64(-1) is False

    def test_too_large_invalid(self) -> None:
        assert is_positive_uint64(2**64) is False

    def test_non_int_invalid(self) -> None:
        assert is_positive_uint64("1") is False


class TestDecodeMetadataJson:
    def test_empty_bytes_decodes_to_empty_object(self) -> None:
        assert decode_metadata_json(b"") == {}

    def test_rejects_utf8_bom(self) -> None:
        with pytest.raises(MetadataEncodingError, match="BOM"):
            decode_metadata_json(b"\xef\xbb\xbf{}")

    def test_rejects_non_utf8(self) -> None:
        with pytest.raises(MetadataEncodingError, match="UTF-8"):
            decode_metadata_json(b"\xff")

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(MetadataEncodingError, match="valid JSON"):
            decode_metadata_json(b"{")

    def test_rejects_non_object_json(self) -> None:
        with pytest.raises(MetadataEncodingError, match="MUST be an object"):
            decode_metadata_json(b"[]")

    def test_valid_object(self) -> None:
        assert decode_metadata_json(b'{"name":"Test"}') == {"name": "Test"}


class TestEncodeMetadataJson:
    def test_roundtrip_unicode(self) -> None:
        obj = {"name": "caffè", "n": 1}
        data = encode_metadata_json(obj)
        assert isinstance(data, (bytes, bytearray))
        assert data.decode("utf-8")  # decodes
        assert decode_metadata_json(data) == obj

    def test_rejects_non_serializable(self) -> None:
        with pytest.raises(MetadataEncodingError, match="JSON-serializable"):
            encode_metadata_json({"x": object()})


class TestValidateArc3Schema:
    def test_allows_unknown_fields(self) -> None:
        validate_arc3_schema({"name": "x", "unknown": {"nested": True}})

    def test_decimals_must_be_int_not_bool(self) -> None:
        with pytest.raises(MetadataArc3Error, match="decimals.*integer"):
            validate_arc3_schema({"decimals": True})

    def test_decimals_must_be_non_negative(self) -> None:
        with pytest.raises(MetadataArc3Error, match="non-negative"):
            validate_arc3_schema({"decimals": -1})

    def test_string_fields_must_be_string(self) -> None:
        with pytest.raises(MetadataArc3Error, match="name.*string"):
            validate_arc3_schema({"name": 123})

    def test_properties_must_be_object(self) -> None:
        with pytest.raises(MetadataArc3Error, match="properties.*object"):
            validate_arc3_schema({"properties": []})

    def test_localization_requires_fields(self) -> None:
        with pytest.raises(MetadataArc3Error, match="must have 'uri'"):
            validate_arc3_schema({"localization": {"default": "en", "locales": []}})

        with pytest.raises(MetadataArc3Error, match="must have 'default'"):
            validate_arc3_schema({"localization": {"uri": "u", "locales": []}})

        with pytest.raises(MetadataArc3Error, match="must have 'locales'"):
            validate_arc3_schema({"localization": {"uri": "u", "default": "en"}})

    def test_localization_type_checks(self) -> None:
        with pytest.raises(MetadataArc3Error, match="locales.*array"):
            validate_arc3_schema(
                {"localization": {"uri": "u", "default": "en", "locales": "en"}}
            )

        with pytest.raises(MetadataArc3Error, match="entries must be strings"):
            validate_arc3_schema(
                {"localization": {"uri": "u", "default": "en", "locales": [123]}}
            )


class TestValidateArc3Values:
    def test_decimals_optional(self) -> None:
        validate_arc3_values({}, asa_decimals=6)

    def test_decimals_must_match_asset_decimals(self) -> None:
        with pytest.raises(MetadataArc3Error, match="must match ASA decimals"):
            validate_arc3_values({"decimals": 0}, asa_decimals=6)

    def test_decimals_wrong_type(self) -> None:
        with pytest.raises(MetadataArc3Error, match="must be an integer"):
            validate_arc3_values({"decimals": "6"}, asa_decimals=6)

    def test_decimals_matches(self) -> None:
        validate_arc3_values({"decimals": 6}, asa_decimals=6)


class TestIsArc3Metadata:
    def test_true_when_has_indicator_fields(self) -> None:
        assert is_arc3_metadata({"decimals": 0}) is True
        assert is_arc3_metadata({"properties": {}}) is True
        assert is_arc3_metadata({"localization": {}}) is True

    def test_false_for_generic_only(self) -> None:
        assert is_arc3_metadata({"name": "x", "description": "y"}) is False


class TestValidateArc20Arc62RequireArc3:
    def test_allows_when_no_arc20_no_arc62(self) -> None:
        validate_arc20_arc62_require_arc3(
            rev_arc20=False, rev_arc62=False, irr_arc3=False
        )

    def test_allows_when_arc3_true(self) -> None:
        validate_arc20_arc62_require_arc3(
            rev_arc20=True, rev_arc62=False, irr_arc3=True
        )
        validate_arc20_arc62_require_arc3(
            rev_arc20=False, rev_arc62=True, irr_arc3=True
        )

    def test_rejects_when_arc20_or_arc62_without_arc3(self) -> None:
        with pytest.raises(MetadataArc3Error, match="require ARC-3"):
            validate_arc20_arc62_require_arc3(
                rev_arc20=True, rev_arc62=False, irr_arc3=False
            )
        with pytest.raises(MetadataArc3Error, match="require ARC-3"):
            validate_arc20_arc62_require_arc3(
                rev_arc20=False, rev_arc62=True, irr_arc3=False
            )


class TestValidateArc3Properties:
    def test_requires_properties_object(self) -> None:
        with pytest.raises(InvalidArc3PropertiesError, match="properties"):
            validate_arc3_properties({}, "arc-20")

        with pytest.raises(InvalidArc3PropertiesError, match="properties"):
            validate_arc3_properties({"properties": []}, "arc-20")

    def test_requires_arc_key_object(self) -> None:
        with pytest.raises(InvalidArc3PropertiesError, match="must be an object"):
            validate_arc3_properties({"properties": {"arc-20": 1}}, "arc-20")

    @pytest.mark.parametrize(
        "app_id",
        [None, 0, -1, 2**64, "1"],
    )
    def test_requires_application_id_positive_uint64(self, app_id: object) -> None:
        with pytest.raises(InvalidArc3PropertiesError, match="application-id"):
            validate_arc3_properties(
                {"properties": {"arc-20": {"application-id": app_id}}},
                "arc-20",
            )

    def test_happy_path(self) -> None:
        validate_arc3_properties(
            {"properties": {"arc-20": {"application-id": 123}}},
            "arc-20",
        )
        validate_arc3_properties(
            {"properties": {"arc-62": {"application-id": 123}}},
            "arc-62",
        )
