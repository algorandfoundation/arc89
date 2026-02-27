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
    validate_arc3_values,
    validate_arc20_arc62_require_arc3,
)


class TestIsPositiveUint64:
    """Test is_positive_uint64 and validate_arc3_properties helpers."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (1, True),
            (2**64 - 1, True),
            (0, False),
            (-1, False),
            (2**64, False),
            (1.0, False),
            ("1", False),
            (None, False),
        ],
    )
    def test_is_positive_uint64(
        self, value: object, expected: bool  # noqa: FBT001
    ) -> None:
        """Test is_positive_uint64 helper."""
        assert is_positive_uint64(value) is expected


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


class TestValidateArc3Values:
    def test_decimals_optional(self) -> None:
        validate_arc3_values({}, asa_decimals=6)

    def test_decimals_must_match_asset_decimals(self) -> None:
        with pytest.raises(MetadataArc3Error, match="must match ASA decimals"):
            validate_arc3_values({"decimals": 0}, asa_decimals=6)

    def test_decimals_wrong_type(self) -> None:
        with pytest.raises(MetadataArc3Error, match="must be an integer"):
            validate_arc3_values({"decimals": "6"}, asa_decimals=6)

    def test_decimals_must_be_int_not_bool(self) -> None:
        with pytest.raises(MetadataArc3Error, match="must be an integer"):
            validate_arc3_values({"decimals": True}, asa_decimals=6)
        with pytest.raises(MetadataArc3Error, match="must be an integer"):
            validate_arc3_values({"decimals": False}, asa_decimals=6)

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

    @pytest.mark.parametrize("arc_key", ["arc-20", "arc-62"])
    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({}, id="no_properties"),
            pytest.param({"properties": "not-a-dict"}, id="properties_not_dict"),
            pytest.param({"properties": {"other-key": 1}}, id="missing_arc_key"),
            pytest.param(
                {"properties": {"arc-20": "not-a-dict", "arc-62": "not-a-dict"}},
                id="arc_key_not_dict",
            ),
            pytest.param(
                {"properties": {"arc-20": {}, "arc-62": {}}},
                id="missing_application_id",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": 0},
                        "arc-62": {"application-id": 0},
                    }
                },
                id="app_id_zero",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": -1},
                        "arc-62": {"application-id": -1},
                    }
                },
                id="app_id_negative",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": "123"},
                        "arc-62": {"application-id": "123"},
                    }
                },
                id="app_id_string",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": 2**64},
                        "arc-62": {"application-id": 2**64},
                    }
                },
                id="app_id_overflow",
            ),
        ],
    )
    def test_invalid_raises(self, body: dict[str, object], arc_key: str) -> None:
        """Test invalid properties raises."""
        with pytest.raises(InvalidArc3PropertiesError):
            validate_arc3_properties(body, arc_key)

    @pytest.mark.parametrize("arc_key", ["arc-20", "arc-62"])
    def test_valid_passes(self, arc_key: str) -> None:
        """Test valid properties passes."""
        body = {"properties": {arc_key: {"application-id": 123456}}}
        validate_arc3_properties(body, arc_key)
