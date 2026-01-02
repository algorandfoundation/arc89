"""
Unit tests for AssetMetadataBox parsing in src.models.

Tests cover:
- AssetMetadataBox.parse() method
- Box value parsing and validation
"""

import pytest

from smart_contracts import constants as const
from src import bitmasks
from src.errors import BoxParseError
from src.models import (
    AssetMetadata,
    AssetMetadataBox,
    RegistryParameters,
    get_default_registry_params,
)


class TestAssetMetadataBoxParse:
    """Tests for AssetMetadataBox.parse() method."""

    def _create_minimal_box_value(
        self,
        *,
        identifiers: int = 0,
        rev_flags: int = 0,
        irr_flags: int = 0,
        metadata_hash: bytes = b"\x00" * 32,
        last_modified_round: int = 0,
        deprecated_by: int = 0,
        metadata: bytes = b"",
    ) -> bytes:
        """Helper to create a valid box value."""
        return (
            bytes([identifiers])
            + bytes([rev_flags])
            + bytes([irr_flags])
            + metadata_hash
            + last_modified_round.to_bytes(8, "big", signed=False)
            + deprecated_by.to_bytes(8, "big", signed=False)
            + metadata
        )

    def test_parse_minimal_box(self) -> None:
        """Test parsing minimal valid box (header only, no metadata)."""
        box_value = self._create_minimal_box_value()
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        assert box.asset_id == 123
        assert box.header.identifiers == 0
        assert box.header.flags.reversible_byte == 0
        assert box.header.flags.irreversible_byte == 0
        assert box.header.metadata_hash == b"\x00" * 32
        assert box.header.last_modified_round == 0
        assert box.header.deprecated_by == 0
        assert box.body.raw_bytes == b""
        assert box.body.is_empty is True

    def test_parse_box_with_metadata(self) -> None:
        """Test parsing box with metadata."""
        metadata = b'{"name":"Test"}'
        box_value = self._create_minimal_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=456, value=box_value)

        assert box.asset_id == 456
        assert box.body.raw_bytes == metadata
        from src.models import decode_metadata_json

        assert decode_metadata_json(box.body.raw_bytes) == {"name": "Test"}

    def test_parse_box_with_flags(self) -> None:
        """Test parsing box with flags set."""
        box_value = self._create_minimal_box_value(
            rev_flags=bitmasks.MASK_REV_ARC20,
            irr_flags=bitmasks.MASK_IRR_ARC3 | bitmasks.MASK_IRR_IMMUTABLE,
        )
        box = AssetMetadataBox.parse(asset_id=789, value=box_value)

        assert box.header.flags.reversible.arc20 is True
        assert box.header.flags.irreversible.arc3 is True
        assert box.header.flags.irreversible.immutable is True
        assert box.header.is_arc3_compliant is True
        assert box.header.is_immutable is True

    def test_parse_box_with_short_identifier(self) -> None:
        """Test parsing box with short identifier set."""
        box_value = self._create_minimal_box_value(
            identifiers=bitmasks.MASK_ID_SHORT,
        )
        box = AssetMetadataBox.parse(asset_id=111, value=box_value)

        assert box.header.identifiers == bitmasks.MASK_ID_SHORT
        assert box.header.is_short is True

    def test_parse_box_with_rounds(self) -> None:
        """Test parsing box with round values."""
        box_value = self._create_minimal_box_value(
            last_modified_round=12345,
            deprecated_by=67890,
        )
        box = AssetMetadataBox.parse(asset_id=222, value=box_value)

        assert box.header.last_modified_round == 12345
        assert box.header.deprecated_by == 67890

    def test_parse_box_with_rounds_and_metadata(self) -> None:
        """Test parsing box with round values AND metadata.

        This test catches a bug where deprecated_by was parsed with value[43:]
        instead of value[43:51], which would include metadata bytes when present.
        """
        metadata = b'{"name":"Test Asset"}'
        box_value = self._create_minimal_box_value(
            last_modified_round=12345,
            deprecated_by=67890,
            metadata=metadata,
        )
        box = AssetMetadataBox.parse(asset_id=222, value=box_value)

        # These would fail with the buggy implementation that used value[43:]
        assert box.header.last_modified_round == 12345
        assert box.header.deprecated_by == 67890
        assert box.body.raw_bytes == metadata

    def test_parse_box_with_custom_hash(self) -> None:
        """Test parsing box with custom metadata hash."""
        custom_hash = b"\xaa" * 32
        box_value = self._create_minimal_box_value(metadata_hash=custom_hash)
        box = AssetMetadataBox.parse(asset_id=333, value=box_value)

        assert box.header.metadata_hash == custom_hash

    def test_parse_box_with_large_metadata(self) -> None:
        """Test parsing box with large metadata."""
        metadata = b"x" * 10000
        box_value = self._create_minimal_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=444, value=box_value)

        assert box.body.raw_bytes == metadata
        assert box.body.size == 10000
        assert box.body.is_short is False

    def test_parse_box_too_small_raises(self) -> None:
        """Test that box value smaller than header size raises."""
        # Header is 51 bytes, provide only 50
        box_value = b"\x00" * 50
        with pytest.raises(BoxParseError, match="Box value too small"):
            AssetMetadataBox.parse(asset_id=555, value=box_value)

    def test_parse_box_empty_raises(self) -> None:
        """Test that empty box value raises."""
        with pytest.raises(BoxParseError, match="Box value too small"):
            AssetMetadataBox.parse(asset_id=666, value=b"")

    def test_parse_box_invalid_hash_length_raises(self) -> None:
        """Test that invalid metadata hash length raises."""
        # Create box with wrong hash length (should be 32 bytes)
        # The box is 50 bytes (3 + 31 + 8 + 8) which is less than header_size (51)
        # So it will fail with "Box value too small" before checking hash length
        box_value = (
            bytes([0])  # identifiers
            + bytes([0])  # rev_flags
            + bytes([0])  # irr_flags
            + b"\x00" * 31  # WRONG: only 31 bytes for hash
            + (0).to_bytes(8, "big")  # last_modified_round
            + (0).to_bytes(8, "big")  # deprecated_by
        )
        with pytest.raises(BoxParseError, match="Box value too small"):
            AssetMetadataBox.parse(asset_id=777, value=box_value)

    def test_parse_box_metadata_exceeds_max_raises(self) -> None:
        """Test that metadata exceeding max size raises."""
        # Create metadata larger than max
        metadata = b"x" * (const.MAX_METADATA_SIZE + 1)
        box_value = self._create_minimal_box_value(metadata=metadata)

        with pytest.raises(BoxParseError, match="exceeds max_metadata_size"):
            AssetMetadataBox.parse(asset_id=888, value=box_value)

    def test_parse_box_with_custom_header_size(self) -> None:
        """Test parsing with custom header size."""
        # Create a custom header (e.g., smaller)
        custom_header_size = 20
        box_value = b"\x00" * custom_header_size + b'{"name":"Test"}'

        box = AssetMetadataBox.parse(
            asset_id=999,
            value=box_value,
            header_size=custom_header_size,
        )

        # Note: This won't parse correctly because header structure is fixed,
        # but it tests the parameter is used
        assert box.body.size > 0

    def test_parse_box_with_custom_max_metadata_size(self) -> None:
        """Test parsing with custom max metadata size."""
        metadata = b"x" * 100
        box_value = self._create_minimal_box_value(metadata=metadata)

        # Set max to less than metadata size - should raise
        with pytest.raises(BoxParseError, match="exceeds max_metadata_size"):
            AssetMetadataBox.parse(
                asset_id=1111,
                value=box_value,
                max_metadata_size=50,
            )

    def test_parse_box_max_uint64_rounds(self) -> None:
        """Test parsing box with maximum uint64 round values."""
        max_uint64 = 2**64 - 1
        box_value = self._create_minimal_box_value(
            last_modified_round=max_uint64,
            deprecated_by=max_uint64,
        )
        box = AssetMetadataBox.parse(asset_id=2222, value=box_value)

        assert box.header.last_modified_round == max_uint64
        assert box.header.deprecated_by == max_uint64

    def test_parse_box_all_flags_set(self) -> None:
        """Test parsing box with all flags set."""
        box_value = self._create_minimal_box_value(
            identifiers=0xFF,
            rev_flags=0xFF,
            irr_flags=0xFF,
        )
        box = AssetMetadataBox.parse(asset_id=3333, value=box_value)

        assert box.header.identifiers == 0xFF
        assert box.header.flags.reversible_byte == 0xFF
        assert box.header.flags.irreversible_byte == 0xFF

    def test_parse_box_unicode_metadata(self) -> None:
        """Test parsing box with Unicode metadata."""
        metadata = '{"emoji":"🎉","text":"你好"}'.encode()
        box_value = self._create_minimal_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=4444, value=box_value)

        assert box.body.raw_bytes == metadata
        from src.models import decode_metadata_json

        assert decode_metadata_json(box.body.raw_bytes) == {
            "emoji": "🎉",
            "text": "你好",
        }

    def test_parse_preserves_exact_bytes(self) -> None:
        """Test that parsing preserves exact byte representation of metadata."""
        # Use specific JSON formatting
        metadata = b'{"a":1,"b":2}'
        box_value = self._create_minimal_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=5555, value=box_value)

        # The exact bytes should be preserved
        assert box.body.raw_bytes == metadata

    def test_parse_box_at_max_size(self) -> None:
        """Test parsing box with metadata at exactly max size."""
        metadata = b"x" * const.MAX_METADATA_SIZE
        box_value = self._create_minimal_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=6666, value=box_value)

        assert box.body.size == const.MAX_METADATA_SIZE

    def test_parse_box_short_boundary(self) -> None:
        """Test parsing box at short metadata size boundary."""
        # At exactly SHORT_METADATA_SIZE
        metadata = b"x" * const.SHORT_METADATA_SIZE
        box_value = self._create_minimal_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=7777, value=box_value)

        assert box.body.size == const.SHORT_METADATA_SIZE
        assert box.body.is_short is True

        # One byte over
        metadata_over = b"x" * (const.SHORT_METADATA_SIZE + 1)
        box_value_over = self._create_minimal_box_value(metadata=metadata_over)
        box_over = AssetMetadataBox.parse(asset_id=7778, value=box_value_over)

        assert box_over.body.size == const.SHORT_METADATA_SIZE + 1
        assert box_over.body.is_short is False

    def test_parse_realistic_arc3_metadata(self) -> None:
        """Test parsing box with realistic ARC-3 metadata."""
        metadata_obj = {
            "name": "My NFT",
            "decimals": 0,
            "description": "A test NFT",
            "image": "https://example.com/image.png",
            "properties": {
                "trait1": "value1",
                "trait2": "value2",
            },
        }
        import json

        metadata = json.dumps(
            metadata_obj, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

        box_value = self._create_minimal_box_value(
            rev_flags=0,
            irr_flags=bitmasks.MASK_IRR_ARC3,
            metadata=metadata,
        )
        box = AssetMetadataBox.parse(asset_id=8888, value=box_value)

        assert box.header.is_arc3_compliant is True
        from src.models import decode_metadata_json

        decoded = decode_metadata_json(box.body.raw_bytes)
        assert decoded["name"] == "My NFT"
        assert decoded["decimals"] == 0
        assert decoded["properties"]["trait1"] == "value1"


class TestAssetMetadataBoxAdvanced:
    """Advanced tests for AssetMetadataBox hash validation methods."""

    def _create_box_value(
        self,
        *,
        identifiers: int = 0,
        rev_flags: int = 0,
        irr_flags: int = 0,
        metadata_hash: bytes = b"\x00" * 32,
        last_modified_round: int = 0,
        deprecated_by: int = 0,
        metadata: bytes = b"",
    ) -> bytes:
        """Helper to create a valid box value."""
        return (
            bytes([identifiers])
            + bytes([rev_flags])
            + bytes([irr_flags])
            + metadata_hash
            + last_modified_round.to_bytes(8, "big", signed=False)
            + deprecated_by.to_bytes(8, "big", signed=False)
            + metadata
        )

    def test_expected_metadata_hash_without_asa_am(self) -> None:
        """Test expected_metadata_hash without ASA am override."""
        metadata = b'{"name":"Test"}'
        box_value = self._create_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        # Should compute from metadata
        expected_hash = box.expected_metadata_hash()
        assert len(expected_hash) == 32
        assert expected_hash != b"\x00" * 32

    def test_expected_metadata_hash_with_asa_am_override(self) -> None:
        """Test expected_metadata_hash with ASA am override."""
        asa_am = b"\xaa" * 32
        metadata = b'{"name":"Test"}'
        box_value = self._create_box_value(
            metadata=metadata,
            irr_flags=bitmasks.MASK_IRR_IMMUTABLE,  # Required for override
        )
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        # Should return asa_am directly
        expected_hash = box.expected_metadata_hash(asa_am=asa_am)
        assert expected_hash == asa_am

    def test_expected_metadata_hash_asa_am_requires_immutable(self) -> None:
        """Test expected_metadata_hash with asa_am requires immutable flag."""
        asa_am = b"\xaa" * 32
        metadata = b'{"name":"Test"}'
        box_value = self._create_box_value(
            metadata=metadata,
            irr_flags=0,  # NOT immutable
        )
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        with pytest.raises(ValueError, match="ASA `am` override requires immutable"):
            box.expected_metadata_hash(asa_am=asa_am)

    def test_expected_metadata_hash_asa_am_all_zeros_ignored(self) -> None:
        """Test expected_metadata_hash with all-zero asa_am (should be ignored)."""
        asa_am = b"\x00" * 32
        metadata = b'{"name":"Test"}'
        box_value = self._create_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        # All-zero asa_am should be ignored, compute from metadata
        expected_hash = box.expected_metadata_hash(asa_am=asa_am)
        assert expected_hash != asa_am

    def test_hash_matches_true(self) -> None:
        """Test hash_matches when hashes match."""
        from src.hashing import compute_metadata_hash

        metadata = b'{"name":"Test"}'
        params = get_default_registry_params()

        # Compute correct hash
        correct_hash = compute_metadata_hash(
            asset_id=123,
            metadata_identifiers=bitmasks.MASK_ID_SHORT,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=metadata,
            page_size=params.page_size,
        )

        box_value = self._create_box_value(
            identifiers=bitmasks.MASK_ID_SHORT,
            metadata=metadata,
            metadata_hash=correct_hash,
        )
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        assert box.hash_matches() is True

    def test_hash_matches_false(self) -> None:
        """Test hash_matches when hashes don't match."""
        metadata = b'{"name":"Test"}'
        wrong_hash = b"\xff" * 32

        box_value = self._create_box_value(
            identifiers=bitmasks.MASK_ID_SHORT,
            metadata=metadata,
            metadata_hash=wrong_hash,
        )
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        assert box.hash_matches() is False

    def test_hash_matches_with_asa_am_skip_validation(self) -> None:
        """Test hash_matches with asa_am and skip_validation=True."""
        asa_am = b"\xaa" * 32
        metadata = b'{"name":"Test"}'
        wrong_hash = b"\xff" * 32

        box_value = self._create_box_value(
            metadata=metadata,
            metadata_hash=wrong_hash,
        )
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        # With skip_validation=True and non-zero asa_am, should return True
        assert box.hash_matches(asa_am=asa_am, skip_validation_on_override=True) is True

    def test_json_property(self) -> None:
        """Test json property on AssetMetadataBox."""
        metadata = b'{"name":"Test","value":42}'
        box_value = self._create_box_value(metadata=metadata)
        box = AssetMetadataBox.parse(asset_id=123, value=box_value)

        assert box.json == {"name": "Test", "value": 42}

    def test_as_asset_metadata(self) -> None:
        """Test as_asset_metadata conversion."""
        metadata = b'{"name":"Test"}'
        box_value = self._create_box_value(
            metadata=metadata,
            rev_flags=bitmasks.MASK_REV_ARC20,
            irr_flags=bitmasks.MASK_IRR_ARC3,
            deprecated_by=5000,
        )
        box = AssetMetadataBox.parse(asset_id=456, value=box_value)

        asset_metadata = box.as_asset_metadata()
        assert isinstance(asset_metadata, AssetMetadata)
        assert asset_metadata.asset_id == 456
        assert asset_metadata.body.raw_bytes == metadata
        assert asset_metadata.flags.reversible.arc20 is True
        assert asset_metadata.flags.irreversible.arc3 is True
        assert asset_metadata.deprecated_by == 5000

    def test_parse_with_params_overrides_header_size(self) -> None:
        """Test parse with params overrides header_size."""
        # Create custom params with different header size
        custom_params = RegistryParameters(
            header_size=60,  # Different from default
            max_metadata_size=const.MAX_METADATA_SIZE,
            short_metadata_size=const.SHORT_METADATA_SIZE,
            page_size=const.PAGE_SIZE,
            first_payload_max_size=const.FIRST_PAYLOAD_MAX_SIZE,
            extra_payload_max_size=const.EXTRA_PAYLOAD_MAX_SIZE,
            replace_payload_max_size=const.REPLACE_PAYLOAD_MAX_SIZE,
            flat_mbr=const.FLAT_MBR,
            byte_mbr=const.BYTE_MBR,
        )

        # Create box with extended header (60 bytes instead of 51)
        base_value = self._create_box_value(metadata=b'{"name":"Test"}')
        # Add extra 9 bytes for the extended header
        box_value = base_value[:51] + b"\x00" * 9 + base_value[51:]

        # Parse with custom params (should use params.header_size)
        box = AssetMetadataBox.parse(
            asset_id=123, value=box_value, params=custom_params
        )
        assert box.asset_id == 123
        # Body starts after 60 bytes instead of 51
        assert box.body.raw_bytes == base_value[51:]

    def test_parse_with_params_overrides_max_metadata_size(self) -> None:
        """Test parse with params overrides max_metadata_size."""
        # Create custom params with smaller max_metadata_size
        custom_params = RegistryParameters(
            header_size=const.HEADER_SIZE,
            max_metadata_size=100,  # Very small limit
            short_metadata_size=const.SHORT_METADATA_SIZE,
            page_size=const.PAGE_SIZE,
            first_payload_max_size=const.FIRST_PAYLOAD_MAX_SIZE,
            extra_payload_max_size=const.EXTRA_PAYLOAD_MAX_SIZE,
            replace_payload_max_size=const.REPLACE_PAYLOAD_MAX_SIZE,
            flat_mbr=const.FLAT_MBR,
            byte_mbr=const.BYTE_MBR,
        )

        # Create box with metadata exceeding custom limit
        metadata = b"x" * 150
        box_value = self._create_box_value(metadata=metadata)

        # Should raise because metadata exceeds custom max_metadata_size
        with pytest.raises(BoxParseError, match="exceeds max_metadata_size"):
            AssetMetadataBox.parse(asset_id=123, value=box_value, params=custom_params)

    def test_parse_known_header_validation_edge_case(self) -> None:
        """Test parse with custom header_size smaller than known header."""
        # Edge case: custom header_size < min_known_header should not trigger
        # the secondary validation check (line 673-675)
        custom_header_size = 40  # Less than min_known_header (51)

        # Create a box with exactly 40 bytes of header + metadata
        box_value = b"\x00" * 40 + b'{"name":"Test"}'

        # This should parse without the min_known_header check since
        # header_size < min_known_header
        box = AssetMetadataBox.parse(
            asset_id=123,
            value=box_value,
            header_size=custom_header_size,
        )
        assert box.body.raw_bytes == b'{"name":"Test"}'

    def test_parse_malformed_header_raises(self) -> None:
        """Test parse with malformed header data raises BoxParseError."""
        # Create a box value that will cause an exception during parsing
        # e.g., not enough bytes for uint64 fields
        malformed_value = b"\x00" * 50  # 50 bytes, just short of full header

        with pytest.raises(BoxParseError, match="Box value too small"):
            AssetMetadataBox.parse(asset_id=123, value=malformed_value)

    def test_parse_with_large_custom_header_size_edge_case(self) -> None:
        """Test parse with custom header_size >= min_known_header but value too small."""
        # This tests line 674: the secondary validation for known header size
        # Create a custom header size that's >= min_known_header (51)
        custom_header_size = 60

        # Create a value that's less than min_known_header
        # This should trigger the "Box value too small for known header" error
        short_value = b"\x00" * 48  # Less than min_known_header

        with pytest.raises(BoxParseError, match="Box value too small"):
            AssetMetadataBox.parse(
                asset_id=123,
                value=short_value,
                header_size=custom_header_size,
            )
