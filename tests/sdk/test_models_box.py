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
from src.models import AssetMetadataBox


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
