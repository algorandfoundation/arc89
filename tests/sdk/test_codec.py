"""
Unit tests for src.codec module.

Tests cover:
- asset_id_to_box_name / box_name_to_asset_id
- b64_encode / b64_decode
- b64url_encode / b64url_decode
- Arc90Compliance parsing and serialization
- Arc90Uri parsing and serialization
- complete_partial_asset_url
"""

import pytest

from smart_contracts import constants as const
from src.asa_metadata_registry import (
    Arc90Compliance,
    Arc90Uri,
    InvalidArc90UriError,
)
from src.asa_metadata_registry.codec import (
    asset_id_to_box_name,
    b64_decode,
    b64_encode,
    b64url_decode,
    b64url_encode,
    box_name_to_asset_id,
    complete_partial_asset_url,
)


class TestAssetIdBoxNameConversion:
    """Tests for asset_id_to_box_name and box_name_to_asset_id."""

    def test_asset_id_to_box_name_zero(self) -> None:
        """Test conversion of asset ID 0."""
        result = asset_id_to_box_name(0)
        assert result == b"\x00\x00\x00\x00\x00\x00\x00\x00"
        assert len(result) == const.ASSET_METADATA_BOX_KEY_SIZE

    def test_asset_id_to_box_name_small(self) -> None:
        """Test conversion of small asset ID."""
        result = asset_id_to_box_name(42)
        assert result == b"\x00\x00\x00\x00\x00\x00\x00\x2a"
        assert len(result) == const.ASSET_METADATA_BOX_KEY_SIZE

    def test_asset_id_to_box_name_large(self) -> None:
        """Test conversion of large asset ID."""
        asset_id = 123456789012345
        result = asset_id_to_box_name(asset_id)
        assert len(result) == const.ASSET_METADATA_BOX_KEY_SIZE
        # Verify round-trip
        assert box_name_to_asset_id(result) == asset_id

    def test_asset_id_to_box_name_max_uint64(self) -> None:
        """Test conversion of maximum uint64 value."""
        max_uint64 = 2**64 - 1
        result = asset_id_to_box_name(max_uint64)
        assert result == b"\xff\xff\xff\xff\xff\xff\xff\xff"
        assert len(result) == const.ASSET_METADATA_BOX_KEY_SIZE

    def test_asset_id_to_box_name_negative_raises(self) -> None:
        """Test that negative asset IDs raise ValueError."""
        with pytest.raises(ValueError, match="must fit in uint64"):
            asset_id_to_box_name(-1)

    def test_asset_id_to_box_name_overflow_raises(self) -> None:
        """Test that asset IDs larger than uint64 raise ValueError."""
        with pytest.raises(ValueError, match="must fit in uint64"):
            asset_id_to_box_name(2**64)

    def test_box_name_to_asset_id_zero(self) -> None:
        """Test conversion of zero box name."""
        box_name = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        result = box_name_to_asset_id(box_name)
        assert result == 0

    def test_box_name_to_asset_id_small(self) -> None:
        """Test conversion of small box name."""
        box_name = b"\x00\x00\x00\x00\x00\x00\x00\x2a"
        result = box_name_to_asset_id(box_name)
        assert result == 42

    def test_box_name_to_asset_id_large(self) -> None:
        """Test conversion of large box name."""
        # Use the actual correct byte representation
        asset_id = 123456789012345
        box_name = asset_id_to_box_name(asset_id)
        result = box_name_to_asset_id(box_name)
        assert result == asset_id

    def test_box_name_to_asset_id_max(self) -> None:
        """Test conversion of maximum box name."""
        box_name = b"\xff\xff\xff\xff\xff\xff\xff\xff"
        result = box_name_to_asset_id(box_name)
        assert result == 2**64 - 1

    def test_box_name_to_asset_id_invalid_length_raises(self) -> None:
        """Test that box names with invalid length raise ValueError."""
        with pytest.raises(ValueError, match="must be 8 bytes"):
            box_name_to_asset_id(b"\x00\x00\x00")

        with pytest.raises(ValueError, match="must be 8 bytes"):
            box_name_to_asset_id(b"\x00" * 10)

    def test_roundtrip_conversion(self) -> None:
        """Test round-trip conversion for various asset IDs."""
        test_ids = [0, 1, 42, 1000, 123456, 2**32, 2**48, 2**64 - 1]
        for asset_id in test_ids:
            box_name = asset_id_to_box_name(asset_id)
            result = box_name_to_asset_id(box_name)
            assert result == asset_id


class TestBase64Encoding:
    """Tests for base64 encoding/decoding functions."""

    def test_b64_encode_empty(self) -> None:
        """Test encoding empty bytes."""
        result = b64_encode(b"")
        assert result == ""

    def test_b64_encode_simple(self) -> None:
        """Test encoding simple bytes."""
        result = b64_encode(b"hello")
        assert result == "aGVsbG8="

    def test_b64_encode_binary(self) -> None:
        """Test encoding binary data."""
        result = b64_encode(b"\x00\x01\x02\x03\xff")
        assert result == "AAECA/8="

    def test_b64_decode_empty(self) -> None:
        """Test decoding empty string."""
        result = b64_decode("")
        assert result == b""

    def test_b64_decode_simple(self) -> None:
        """Test decoding simple base64."""
        result = b64_decode("aGVsbG8=")
        assert result == b"hello"

    def test_b64_decode_binary(self) -> None:
        """Test decoding binary base64."""
        result = b64_decode("AAECA/8=")
        assert result == b"\x00\x01\x02\x03\xff"

    def test_b64_roundtrip(self) -> None:
        """Test round-trip base64 encoding."""
        original = b"The quick brown fox jumps over the lazy dog"
        encoded = b64_encode(original)
        decoded = b64_decode(encoded)
        assert decoded == original

    def test_b64url_encode_empty(self) -> None:
        """Test URL-safe encoding of empty bytes."""
        result = b64url_encode(b"")
        assert result == ""

    def test_b64url_encode_simple(self) -> None:
        """Test URL-safe encoding."""
        result = b64url_encode(b"hello")
        assert result == "aGVsbG8="

    def test_b64url_encode_with_special_chars(self) -> None:
        """Test URL-safe encoding with characters that differ from standard base64."""
        # Standard base64 uses + and /, URL-safe uses - and _
        result = b64url_encode(b"\xfb\xff\xfe")
        assert result == "-__-"
        # Standard base64 would be: +//+

    def test_b64url_decode_empty(self) -> None:
        """Test URL-safe decoding of empty string."""
        result = b64url_decode("")
        assert result == b""

    def test_b64url_decode_simple(self) -> None:
        """Test URL-safe decoding."""
        result = b64url_decode("aGVsbG8=")
        assert result == b"hello"

    def test_b64url_decode_with_special_chars(self) -> None:
        """Test URL-safe decoding with - and _."""
        result = b64url_decode("-__-")
        assert result == b"\xfb\xff\xfe"

    def test_b64url_roundtrip(self) -> None:
        """Test round-trip URL-safe base64 encoding."""
        original = b"\x00\x01\x02\xfb\xff\xfe\xff"
        encoded = b64url_encode(original)
        decoded = b64url_decode(encoded)
        assert decoded == original


class TestArc90Compliance:
    """Tests for Arc90Compliance parsing and serialization."""

    def test_parse_empty_fragment(self) -> None:
        """Test parsing empty or None fragment."""
        assert Arc90Compliance.parse(None) == Arc90Compliance(())
        assert Arc90Compliance.parse("") == Arc90Compliance(())
        assert Arc90Compliance.parse("#") == Arc90Compliance(())

    def test_parse_single_arc(self) -> None:
        """Test parsing single ARC number."""
        result = Arc90Compliance.parse("#arc89")
        assert result == Arc90Compliance((89,))

    def test_parse_multiple_arcs(self) -> None:
        """Test parsing multiple ARC numbers."""
        result = Arc90Compliance.parse("#arc89+90+91")
        assert result == Arc90Compliance((89, 90, 91))

    def test_parse_arc3_alone(self) -> None:
        """Test parsing ARC-3 alone (valid)."""
        result = Arc90Compliance.parse("#arc3")
        assert result == Arc90Compliance((3,))

    def test_parse_arc3_with_others_invalid(self) -> None:
        """Test parsing ARC-3 with others (invalid per spec)."""
        result = Arc90Compliance.parse("#arc3+89")
        assert result == Arc90Compliance(())  # Invalid, returns empty

        result = Arc90Compliance.parse("#arc89+3")
        assert result == Arc90Compliance(())  # Invalid, returns empty

    def test_parse_leading_zeros_invalid(self) -> None:
        """Test parsing with leading zeros (invalid)."""
        result = Arc90Compliance.parse("#arc089")
        assert result == Arc90Compliance(())  # Invalid

        result = Arc90Compliance.parse("#arc89+090")
        assert result == Arc90Compliance(())  # Invalid

    def test_parse_single_digit_zero_valid(self) -> None:
        """Test parsing single digit 0 (valid)."""
        result = Arc90Compliance.parse("#arc0")
        assert result == Arc90Compliance((0,))

    def test_parse_without_arc_prefix_invalid(self) -> None:
        """Test parsing without 'arc' prefix (invalid)."""
        result = Arc90Compliance.parse("#89")
        assert result == Arc90Compliance(())

    def test_parse_arc_without_number_invalid(self) -> None:
        """Test parsing 'arc' without a number (invalid)."""
        result = Arc90Compliance.parse("#arc")
        assert result == Arc90Compliance(())

    def test_parse_non_numeric_invalid(self) -> None:
        """Test parsing with non-numeric values (invalid)."""
        result = Arc90Compliance.parse("#arcabc")
        assert result == Arc90Compliance(())

        result = Arc90Compliance.parse("#arc89+xyz")
        assert result == Arc90Compliance(())

    def test_to_fragment_empty(self) -> None:
        """Test serializing empty compliance."""
        compliance = Arc90Compliance(())
        assert compliance.to_fragment() is None

    def test_to_fragment_single(self) -> None:
        """Test serializing single ARC."""
        compliance = Arc90Compliance((89,))
        assert compliance.to_fragment() == "#arc89"

    def test_to_fragment_multiple(self) -> None:
        """Test serializing multiple ARCs."""
        compliance = Arc90Compliance((89, 90, 91))
        assert compliance.to_fragment() == "#arc89+90+91"

    def test_to_fragment_arc3_alone(self) -> None:
        """Test serializing ARC-3 alone."""
        compliance = Arc90Compliance((3,))
        assert compliance.to_fragment() == "#arc3"

    def test_to_fragment_arc3_with_others_raises(self) -> None:
        """Test serializing ARC-3 with others raises error."""
        compliance = Arc90Compliance((3, 89))
        with pytest.raises(ValueError, match="ARC-3 must be the sole entry"):
            compliance.to_fragment()

    def test_roundtrip_single(self) -> None:
        """Test round-trip for single ARC."""
        original = "#arc89"
        parsed = Arc90Compliance.parse(original)
        serialized = parsed.to_fragment()
        assert serialized == original

    def test_roundtrip_multiple(self) -> None:
        """Test round-trip for multiple ARCs."""
        original = "#arc89+90+200"
        parsed = Arc90Compliance.parse(original)
        serialized = parsed.to_fragment()
        assert serialized == original


class TestArc90Uri:
    """Tests for Arc90Uri parsing and serialization."""

    def test_parse_testnet_uri(self) -> None:
        """Test parsing testnet URI."""
        uri = "algorand://net:testnet/app/752790676?box=AAAAAAAAAAE%3D#arc89"
        parsed = Arc90Uri.parse(uri)

        assert parsed.netauth == "net:testnet"
        assert parsed.app_id == 752790676
        assert parsed.box_name == b"\x00\x00\x00\x00\x00\x00\x00\x01"
        assert parsed.compliance == Arc90Compliance((89,))
        assert parsed.asset_id == 1
        assert not parsed.is_partial

    def test_parse_mainnet_uri(self) -> None:
        """Test parsing mainnet URI."""
        uri = "algorand://app/123456789?box=AAAAAAAAAAE%3D#arc89"
        parsed = Arc90Uri.parse(uri)

        assert parsed.netauth is None
        assert parsed.app_id == 123456789
        assert parsed.box_name == b"\x00\x00\x00\x00\x00\x00\x00\x01"
        assert parsed.compliance == Arc90Compliance((89,))
        assert parsed.asset_id == 1
        assert not parsed.is_partial

    def test_parse_localnet_uri(self) -> None:
        """Test parsing localnet URI."""
        uri = "algorand://net:localnet/app/1001?box=AAAAAAAAAAE%3D#arc3"
        parsed = Arc90Uri.parse(uri)

        assert parsed.netauth == "net:localnet"
        assert parsed.app_id == 1001
        assert parsed.box_name == b"\x00\x00\x00\x00\x00\x00\x00\x01"
        assert parsed.compliance == Arc90Compliance((3,))
        assert parsed.asset_id == 1
        assert not parsed.is_partial

    def test_parse_partial_uri(self) -> None:
        """Test parsing partial URI (empty box value)."""
        uri = "algorand://net:testnet/app/752790676?box=#arc89"
        parsed = Arc90Uri.parse(uri)

        assert parsed.netauth == "net:testnet"
        assert parsed.app_id == 752790676
        assert parsed.box_name is None
        assert parsed.compliance == Arc90Compliance((89,))
        assert parsed.asset_id is None
        assert parsed.is_partial

    def test_parse_uri_without_fragment(self) -> None:
        """Test parsing URI without compliance fragment."""
        uri = "algorand://net:testnet/app/752790676?box=AAAAAAAAAAE%3D"
        parsed = Arc90Uri.parse(uri)

        assert parsed.netauth == "net:testnet"
        assert parsed.app_id == 752790676
        assert parsed.box_name == b"\x00\x00\x00\x00\x00\x00\x00\x01"
        assert parsed.compliance == Arc90Compliance(())

    def test_parse_uri_multiple_compliance(self) -> None:
        """Test parsing URI with multiple compliance ARCs."""
        uri = "algorand://net:testnet/app/752790676?box=AAAAAAAAAAE%3D#arc89+90"
        parsed = Arc90Uri.parse(uri)

        assert parsed.compliance == Arc90Compliance((89, 90))

    def test_parse_invalid_scheme_raises(self) -> None:
        """Test parsing non-algorand scheme raises error."""
        with pytest.raises(InvalidArc90UriError, match="Not an algorand:// URI"):
            Arc90Uri.parse("https://example.com/app/123?box=")

    def test_parse_missing_box_param_raises(self) -> None:
        """Test parsing without box parameter raises error."""
        with pytest.raises(InvalidArc90UriError, match="Missing 'box' query parameter"):
            Arc90Uri.parse("algorand://net:testnet/app/123")

    def test_parse_invalid_app_path_raises(self) -> None:
        """Test parsing with invalid app path raises error."""
        with pytest.raises(InvalidArc90UriError, match="Expected path '/app/<app_id>'"):
            Arc90Uri.parse("algorand://net:testnet/asset/123?box=")

    def test_parse_invalid_app_id_raises(self) -> None:
        """Test parsing with non-numeric app ID raises error."""
        with pytest.raises(InvalidArc90UriError, match="Invalid app id"):
            Arc90Uri.parse("algorand://net:testnet/app/abc?box=")

    def test_parse_invalid_app_id_mainnet_raises(self) -> None:
        """Test parsing mainnet URI with non-numeric app ID raises error."""
        with pytest.raises(InvalidArc90UriError, match="Invalid app id"):
            Arc90Uri.parse("algorand://app/notanumber?box=")

    def test_parse_invalid_box_name_base64_raises(self) -> None:
        """Test parsing with invalid base64 box name raises error."""
        with pytest.raises(InvalidArc90UriError, match="Invalid base64url box name"):
            Arc90Uri.parse("algorand://net:testnet/app/123?box=!!!invalid!!!")

    def test_parse_invalid_box_name_length_raises(self) -> None:
        """Test parsing with wrong box name length raises error."""
        # 4 bytes instead of 8
        box_b64 = b64url_encode(b"\x00\x00\x00\x01")
        uri = f"algorand://net:testnet/app/123?box={box_b64}"
        with pytest.raises(InvalidArc90UriError, match="8-byte box name"):
            Arc90Uri.parse(uri)

    def test_parse_unrecognized_shape_raises(self) -> None:
        """Test parsing with unrecognized URI shape raises error."""
        with pytest.raises(
            InvalidArc90UriError, match="Unrecognized ARC-90 app URI shape"
        ):
            Arc90Uri.parse("algorand://unknown/something/123?box=")

    def test_to_uri_testnet(self) -> None:
        """Test serializing testnet URI."""
        uri_obj = Arc90Uri(
            netauth="net:testnet",
            app_id=752790676,
            box_name=b"\x00\x00\x00\x00\x00\x00\x00\x01",
            compliance=Arc90Compliance((89,)),
        )
        result = uri_obj.to_uri()

        assert "algorand://net:testnet/app/752790676" in result
        assert "box=" in result
        assert "arc89" in result

    def test_to_uri_mainnet(self) -> None:
        """Test serializing mainnet URI."""
        uri_obj = Arc90Uri(
            netauth=None,
            app_id=123456789,
            box_name=b"\x00\x00\x00\x00\x00\x00\x00\x01",
            compliance=Arc90Compliance((89,)),
        )
        result = uri_obj.to_uri()

        assert "algorand://app/123456789" in result
        assert "box=" in result
        assert "arc89" in result

    def test_to_uri_partial(self) -> None:
        """Test serializing partial URI."""
        uri_obj = Arc90Uri(
            netauth="net:testnet",
            app_id=752790676,
            box_name=None,
            compliance=Arc90Compliance((89,)),
        )
        result = uri_obj.to_uri()

        assert "algorand://net:testnet/app/752790676" in result
        assert "box=" in result
        assert "arc89" in result
        # Box should be empty
        assert "box=&" in result or "box=#" in result or result.endswith("box=")

    def test_to_uri_without_compliance(self) -> None:
        """Test serializing URI without compliance fragment."""
        uri_obj = Arc90Uri(
            netauth="net:testnet",
            app_id=752790676,
            box_name=b"\x00\x00\x00\x00\x00\x00\x00\x01",
            compliance=Arc90Compliance(()),
        )
        result = uri_obj.to_uri()

        assert "algorand://net:testnet/app/752790676" in result
        assert "box=" in result
        assert "#" not in result

    def test_with_asset_id(self) -> None:
        """Test completing partial URI with asset ID."""
        partial = Arc90Uri(
            netauth="net:testnet",
            app_id=752790676,
            box_name=None,
            compliance=Arc90Compliance((89,)),
        )
        completed = partial.with_asset_id(42)

        assert completed.netauth == partial.netauth
        assert completed.app_id == partial.app_id
        assert completed.box_name == asset_id_to_box_name(42)
        assert completed.compliance == partial.compliance
        assert completed.asset_id == 42
        assert not completed.is_partial

    def test_to_algod_box_name_b64(self) -> None:
        """Test converting to Algod box name format (standard base64)."""
        uri_obj = Arc90Uri(
            netauth="net:testnet",
            app_id=752790676,
            box_name=b"\x00\x00\x00\x00\x00\x00\x00\x01",
            compliance=Arc90Compliance((89,)),
        )
        result = uri_obj.to_algod_box_name_b64()

        # Should be standard base64 with padding
        assert result == b64_encode(b"\x00\x00\x00\x00\x00\x00\x00\x01")
        # Verify it's different from URL-safe encoding if special chars present
        assert b64_decode(result) == b"\x00\x00\x00\x00\x00\x00\x00\x01"

    def test_to_algod_box_name_b64_partial_raises(self) -> None:
        """Test that partial URI cannot produce algod box name."""
        partial = Arc90Uri(
            netauth="net:testnet",
            app_id=752790676,
            box_name=None,
            compliance=Arc90Compliance((89,)),
        )
        with pytest.raises(
            ValueError, match="Cannot produce algod box name for a partial URI"
        ):
            partial.to_algod_box_name_b64()

    def test_roundtrip_testnet(self) -> None:
        """Test round-trip for testnet URI."""
        original_uri = "algorand://net:testnet/app/752790676?box=AAAAAAAAAAE%3D#arc89"
        parsed = Arc90Uri.parse(original_uri)
        serialized = parsed.to_uri()
        reparsed = Arc90Uri.parse(serialized)

        assert reparsed.netauth == parsed.netauth
        assert reparsed.app_id == parsed.app_id
        assert reparsed.box_name == parsed.box_name
        assert reparsed.compliance == parsed.compliance

    def test_roundtrip_mainnet(self) -> None:
        """Test round-trip for mainnet URI."""
        original_uri = "algorand://app/123456789?box=AAAAAAAAAAE%3D#arc89"
        parsed = Arc90Uri.parse(original_uri)
        serialized = parsed.to_uri()
        reparsed = Arc90Uri.parse(serialized)

        assert reparsed.netauth == parsed.netauth
        assert reparsed.app_id == parsed.app_id
        assert reparsed.box_name == parsed.box_name
        assert reparsed.compliance == parsed.compliance


class TestCompletePartialAssetUrl:
    """Tests for complete_partial_asset_url function."""

    def test_complete_partial_url(self) -> None:
        """Test completing a partial asset URL."""
        partial_url = "algorand://net:testnet/app/752790676?box=#arc89"
        asset_id = 42

        result = complete_partial_asset_url(partial_url, asset_id)

        # Parse to verify
        parsed = Arc90Uri.parse(result)
        assert parsed.asset_id == asset_id
        assert not parsed.is_partial
        assert parsed.app_id == 752790676
        assert parsed.netauth == "net:testnet"

    def test_complete_already_complete_url(self) -> None:
        """Test that completing an already complete URL returns equivalent URI."""
        complete_url = "algorand://net:testnet/app/752790676?box=AAAAAAAAAAE%3D#arc89"
        asset_id = 1  # Matches the box content

        result = complete_partial_asset_url(complete_url, asset_id)

        # Parse both to compare
        parsed_original = Arc90Uri.parse(complete_url)
        parsed_result = Arc90Uri.parse(result)

        assert parsed_result.asset_id == parsed_original.asset_id
        assert parsed_result.app_id == parsed_original.app_id
        assert parsed_result.netauth == parsed_original.netauth

    def test_complete_different_asset_id(self) -> None:
        """Test completing URL with different asset ID preserves the original if already complete."""
        complete_url = "algorand://net:testnet/app/752790676?box=AAAAAAAAAAE%3D#arc89"
        new_asset_id = 999

        result = complete_partial_asset_url(complete_url, new_asset_id)

        parsed = Arc90Uri.parse(result)
        # Should preserve the original asset ID since URI was already complete
        assert parsed.asset_id == 1  # Original asset ID

    def test_complete_mainnet_url(self) -> None:
        """Test completing mainnet partial URL."""
        partial_url = "algorand://app/123456789?box=#arc89"
        asset_id = 1000

        result = complete_partial_asset_url(partial_url, asset_id)

        parsed = Arc90Uri.parse(result)
        assert parsed.asset_id == asset_id
        assert parsed.app_id == 123456789
        assert parsed.netauth is None

    def test_complete_preserves_compliance(self) -> None:
        """Test that completing preserves compliance fragment."""
        partial_url = "algorand://net:testnet/app/752790676?box=#arc89+90"
        asset_id = 42

        result = complete_partial_asset_url(partial_url, asset_id)

        parsed = Arc90Uri.parse(result)
        assert parsed.compliance == Arc90Compliance((89, 90))

    def test_complete_without_compliance(self) -> None:
        """Test completing URL without compliance fragment."""
        partial_url = "algorand://net:testnet/app/752790676?box="
        asset_id = 42

        result = complete_partial_asset_url(partial_url, asset_id)

        parsed = Arc90Uri.parse(result)
        assert parsed.asset_id == asset_id
        assert parsed.compliance == Arc90Compliance(())

    def test_complete_large_asset_id(self) -> None:
        """Test completing with large asset ID."""
        partial_url = "algorand://net:testnet/app/752790676?box=#arc89"
        asset_id = 2**48 - 1

        result = complete_partial_asset_url(partial_url, asset_id)

        parsed = Arc90Uri.parse(result)
        assert parsed.asset_id == asset_id

    def test_complete_zero_asset_id(self) -> None:
        """Test completing with zero asset ID."""
        partial_url = "algorand://net:testnet/app/752790676?box=#arc89"
        asset_id = 0

        result = complete_partial_asset_url(partial_url, asset_id)

        parsed = Arc90Uri.parse(result)
        assert parsed.asset_id == asset_id
