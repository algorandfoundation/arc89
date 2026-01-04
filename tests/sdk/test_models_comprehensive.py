"""
Comprehensive tests for uncovered functionality in src.models.

This test file focuses on edge cases and paths that weren't covered by existing tests:
- MetadataHeader.serialized property
- MetadataHeader.expected_identifiers
- MetadataHeader.from_tuple error cases
- MetadataBody.get_page error cases
- MetadataBody.json property
- AssetMetadataRecord hash validation methods
- AssetMetadata convenience properties
- AssetMetadata hash computation with asa_am
- AssetMetadata.from_bytes
- AssetMetadata.compute_header_hash
- AssetMetadata.compute_page_hash
"""

import pytest

from smart_contracts import constants as const
from src.asa_metadata_registry import (
    AssetMetadata,
    AssetMetadataRecord,
    IrreversibleFlags,
    MetadataArc3Error,
    MetadataBody,
    MetadataFlags,
    MetadataHeader,
    ReversibleFlags,
    bitmasks,
    compute_metadata_hash,
    get_default_registry_params,
)


class TestMetadataHeaderAdvanced:
    """Advanced tests for MetadataHeader."""

    def test_serialized_property(self) -> None:
        """Test serialized property produces correct bytes."""
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc20=True),
            irreversible=IrreversibleFlags(arc3=True, immutable=True),
        )
        header = MetadataHeader(
            identifiers=bitmasks.MASK_ID_SHORT,
            flags=flags,
            metadata_hash=b"\xaa" * 32,
            last_modified_round=12345,
            deprecated_by=67890,
        )
        serialized = header.serialized

        assert len(serialized) == const.HEADER_SIZE
        assert serialized[0] == bitmasks.MASK_ID_SHORT
        assert serialized[1] == flags.reversible_byte
        assert serialized[2] == flags.irreversible_byte
        assert serialized[3:35] == b"\xaa" * 32
        # Check uint64 encoding
        assert int.from_bytes(serialized[35:43], "big") == 12345
        assert int.from_bytes(serialized[43:51], "big") == 67890

    def test_expected_identifiers_short_body(self) -> None:
        """Test expected_identifiers with short body."""
        header = MetadataHeader(
            identifiers=0,  # Not set initially
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=0,
            deprecated_by=0,
        )
        body = MetadataBody(b'{"name":"Test"}')
        expected = header.expected_identifiers(body=body)
        assert expected & bitmasks.MASK_ID_SHORT == bitmasks.MASK_ID_SHORT

    def test_expected_identifiers_long_body(self) -> None:
        """Test expected_identifiers with long body."""
        header = MetadataHeader(
            identifiers=bitmasks.MASK_ID_SHORT,  # Set initially
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=0,
            deprecated_by=0,
        )
        # Create body larger than SHORT_METADATA_SIZE
        body = MetadataBody(b"x" * (const.SHORT_METADATA_SIZE + 1))
        expected = header.expected_identifiers(body=body)
        assert expected & bitmasks.MASK_ID_SHORT == 0

    def test_expected_identifiers_preserves_reserved_bits(self) -> None:
        """Test expected_identifiers preserves reserved bits."""
        # Set some reserved bits
        header = MetadataHeader(
            identifiers=0b11110000,  # Reserved bits set
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=0,
            deprecated_by=0,
        )
        body = MetadataBody(b'{"name":"Test"}')
        expected = header.expected_identifiers(body=body)
        # Should preserve reserved bits and set short bit
        assert expected & 0b11110000 == 0b11110000
        assert expected & bitmasks.MASK_ID_SHORT == bitmasks.MASK_ID_SHORT

    def test_from_tuple_invalid_identifiers_type(self) -> None:
        """Test from_tuple with non-int identifiers."""
        with pytest.raises(TypeError, match="identifiers must be int"):
            MetadataHeader.from_tuple(["not int", 0, 0, b"\x00" * 32, 0, 0])

    def test_from_tuple_identifiers_out_of_range(self) -> None:
        """Test from_tuple with identifiers out of uint8 range."""
        with pytest.raises(ValueError, match="identifiers must fit in uint8"):
            MetadataHeader.from_tuple([256, 0, 0, b"\x00" * 32, 0, 0])

    def test_from_tuple_invalid_reversible_flags_type(self) -> None:
        """Test from_tuple with non-int reversible flags."""
        with pytest.raises(TypeError, match=r"reversible_flags must be int 0..255"):
            MetadataHeader.from_tuple([0, "not int", 0, b"\x00" * 32, 0, 0])

    def test_from_tuple_invalid_irreversible_flags_type(self) -> None:
        """Test from_tuple with non-int irreversible flags."""
        with pytest.raises(TypeError, match=r"irreversible_flags must be int 0..255"):
            MetadataHeader.from_tuple([0, 0, "not int", b"\x00" * 32, 0, 0])

    def test_from_tuple_invalid_hash_length(self) -> None:
        """Test from_tuple with wrong hash length."""
        with pytest.raises(ValueError, match="metadata_hash must be 32 bytes"):
            MetadataHeader.from_tuple([0, 0, 0, b"\x00" * 31, 0, 0])

    def test_from_tuple_hash_as_list(self) -> None:
        """Test from_tuple with hash as list of ints."""
        hash_list = [0] * 32
        header = MetadataHeader.from_tuple([0, 0, 0, hash_list, 100, 200])
        assert header.metadata_hash == b"\x00" * 32

    def test_from_tuple_invalid_last_modified_round_type(self) -> None:
        """Test from_tuple with non-int last_modified_round."""
        with pytest.raises(TypeError, match="last_modified_round must be int"):
            MetadataHeader.from_tuple([0, 0, 0, b"\x00" * 32, "not int", 0])

    def test_from_tuple_invalid_deprecated_by_type(self) -> None:
        """Test from_tuple with non-int deprecated_by."""
        with pytest.raises(TypeError, match="deprecated_by must be int"):
            MetadataHeader.from_tuple([0, 0, 0, b"\x00" * 32, 0, "not int"])

    def test_is_deprecated_property(self) -> None:
        """Test is_deprecated property."""
        header_not_deprecated = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=0,
            deprecated_by=0,
        )
        assert header_not_deprecated.is_deprecated is False

        header_deprecated = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=0,
            deprecated_by=5000,
        )
        assert header_deprecated.is_deprecated is True


class TestMetadataBodyAdvanced:
    """Advanced tests for MetadataBody."""

    def test_json_property(self) -> None:
        """Test json property decodes correctly."""
        body = MetadataBody(b'{"name":"Test","value":123}')
        assert body.json == {"name": "Test", "value": 123}

    def test_json_property_empty(self) -> None:
        """Test json property with empty body."""
        body = MetadataBody.empty()
        assert body.json == {}

    def test_get_page_negative_index_raises(self) -> None:
        """Test get_page with negative index."""
        body = MetadataBody(b"x" * 1000)
        with pytest.raises(ValueError, match="page_index must be non-negative"):
            body.get_page(-1)

    def test_get_page_index_out_of_range_raises(self) -> None:
        """Test get_page with index beyond total pages."""
        body = MetadataBody(b"x" * 1000)
        with pytest.raises(ValueError, match="out of range"):
            body.get_page(100)

    def test_get_page_first_page(self) -> None:
        """Test get_page for first page."""
        params = get_default_registry_params()
        data = b"x" * (params.page_size * 2)
        body = MetadataBody(data)
        page = body.get_page(0, params)
        assert len(page) == params.page_size
        assert page == b"x" * params.page_size

    def test_get_page_middle_page(self) -> None:
        """Test get_page for middle page."""
        params = get_default_registry_params()
        data = b"x" * (params.page_size * 3)
        body = MetadataBody(data)
        page = body.get_page(1, params)
        assert len(page) == params.page_size
        assert page == b"x" * params.page_size

    def test_get_page_last_page_full(self) -> None:
        """Test get_page for last page when it's full."""
        params = get_default_registry_params()
        data = b"x" * (params.page_size * 2)
        body = MetadataBody(data)
        page = body.get_page(1, params)
        assert len(page) == params.page_size

    def test_get_page_last_page_partial(self) -> None:
        """Test get_page for partial last page."""
        params = get_default_registry_params()
        data = b"x" * (params.page_size + 100)
        body = MetadataBody(data)
        page = body.get_page(1, params)
        assert len(page) == 100


class TestAssetMetadataRecordAdvanced:
    """Advanced tests for AssetMetadataRecord hash validation methods."""

    def test_expected_metadata_hash(self) -> None:
        """Test expected_metadata_hash delegates to AssetMetadataBox."""
        header = MetadataHeader(
            identifiers=bitmasks.MASK_ID_SHORT,
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=0,
            deprecated_by=0,
        )
        body = MetadataBody(b'{"name":"Test"}')
        record = AssetMetadataRecord(
            app_id=100,
            asset_id=200,
            header=header,
            body=body,
        )

        expected = record.expected_metadata_hash()
        assert len(expected) == 32

    def test_hash_matches(self) -> None:
        """Test hash_matches delegates to AssetMetadataBox."""

        metadata = b'{"name":"Test"}'
        params = get_default_registry_params()

        correct_hash = compute_metadata_hash(
            asset_id=200,
            metadata_identifiers=bitmasks.MASK_ID_SHORT,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=metadata,
            page_size=params.page_size,
        )

        header = MetadataHeader(
            identifiers=bitmasks.MASK_ID_SHORT,
            flags=MetadataFlags.empty(),
            metadata_hash=correct_hash,
            last_modified_round=0,
            deprecated_by=0,
        )
        body = MetadataBody(metadata)
        record = AssetMetadataRecord(
            app_id=100,
            asset_id=200,
            header=header,
            body=body,
        )

        assert record.hash_matches() is True

    def test_json_property(self) -> None:
        """Test json property on AssetMetadataRecord."""
        header = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=0,
            deprecated_by=0,
        )
        body = MetadataBody(b'{"name":"Test","count":42}')
        record = AssetMetadataRecord(
            app_id=100,
            asset_id=200,
            header=header,
            body=body,
        )

        assert record.json == {"name": "Test", "count": 42}


class TestAssetMetadataAdvanced:
    """Advanced tests for AssetMetadata."""

    def test_convenience_properties(self) -> None:
        """Test all convenience properties."""
        body = MetadataBody(b'{"name":"Test"}')
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc20=True, arc62=True),
            irreversible=IrreversibleFlags(
                arc3=True, arc89_native=True, immutable=True
            ),
        )
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=flags,
            deprecated_by=5000,
        )

        assert metadata.is_empty is False
        assert metadata.is_short is True
        assert metadata.size == len(body.raw_bytes)
        assert metadata.is_immutable is True
        assert metadata.is_arc3_compliant is True
        assert metadata.is_arc89_native is True
        assert metadata.is_arc20_smart_asa is True
        assert metadata.is_arc62_circulating_supply is True
        assert metadata.is_deprecated is True

    def test_compute_header_hash(self) -> None:
        """Test compute_header_hash."""
        body = MetadataBody(b'{"name":"Test"}')
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=MetadataFlags.empty(),
            deprecated_by=0,
        )

        header_hash = metadata.compute_header_hash()
        assert len(header_hash) == 32
        assert header_hash != b"\x00" * 32

    def test_compute_page_hash(self) -> None:
        """Test compute_page_hash."""
        params = get_default_registry_params()
        body = MetadataBody(b"x" * (params.page_size * 2))
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=MetadataFlags.empty(),
            deprecated_by=0,
        )

        page_hash_0 = metadata.compute_page_hash(page_index=0)
        page_hash_1 = metadata.compute_page_hash(page_index=1)

        assert len(page_hash_0) == 32
        assert len(page_hash_1) == 32
        assert (
            page_hash_0 != page_hash_1
        )  # Different pages should have different hashes

    def test_compute_metadata_hash_with_asa_am(self) -> None:
        """Test compute_metadata_hash with asa_am override."""
        asa_am = b"\xaa" * 32
        body = MetadataBody(b'{"name":"Test"}')
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=MetadataFlags(
                reversible=ReversibleFlags.empty(),
                irreversible=IrreversibleFlags(immutable=True),
            ),
            deprecated_by=0,
        )

        # With asa_am, should return asa_am directly
        result = metadata.compute_metadata_hash(asa_am=asa_am)
        assert result == asa_am

    def test_compute_metadata_hash_asa_am_invalid_length(self) -> None:
        """Test compute_metadata_hash with asa_am of wrong length."""
        body = MetadataBody(b'{"name":"Test"}')
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=MetadataFlags.empty(),
            deprecated_by=0,
        )

        with pytest.raises(ValueError, match="must be exactly 32 bytes"):
            metadata.compute_metadata_hash(asa_am=b"\xaa" * 31)

    def test_compute_metadata_hash_asa_am_requires_immutable(self) -> None:
        """Test compute_metadata_hash with asa_am requires immutable flag."""
        asa_am = b"\xaa" * 32
        body = MetadataBody(b'{"name":"Test"}')
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=MetadataFlags.empty(),  # NOT immutable
            deprecated_by=0,
        )

        with pytest.raises(ValueError, match="ASA `am` override requires immutable"):
            metadata.compute_metadata_hash(asa_am=asa_am)

    def test_compute_metadata_hash_asa_am_all_zeros_ignored(self) -> None:
        """Test compute_metadata_hash with all-zero asa_am."""
        asa_am = b"\x00" * 32
        body = MetadataBody(b'{"name":"Test"}')
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=MetadataFlags.empty(),
            deprecated_by=0,
        )

        # All-zero asa_am should be ignored
        result = metadata.compute_metadata_hash(asa_am=asa_am)
        assert result != asa_am

    def test_from_bytes_simple(self) -> None:
        """Test from_bytes with simple metadata."""
        metadata_bytes = b'{"name":"Test"}'
        metadata = AssetMetadata.from_bytes(
            asset_id=123,
            metadata_bytes=metadata_bytes,
        )

        assert metadata.asset_id == 123
        assert metadata.body.raw_bytes == metadata_bytes
        assert metadata.flags.reversible_byte == 0
        assert metadata.flags.irreversible_byte == 0

    def test_from_bytes_with_flags(self) -> None:
        """Test from_bytes with custom flags."""
        metadata_bytes = b'{"name":"Test"}'
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc20=True),
            irreversible=IrreversibleFlags(arc3=True),
        )
        metadata = AssetMetadata.from_bytes(
            asset_id=456,
            metadata_bytes=metadata_bytes,
            flags=flags,
        )

        assert metadata.flags.reversible.arc20 is True
        assert metadata.flags.irreversible.arc3 is True

    def test_from_bytes_with_deprecated_by(self) -> None:
        """Test from_bytes with deprecated_by."""
        metadata_bytes = b'{"name":"Test"}'
        metadata = AssetMetadata.from_bytes(
            asset_id=789,
            metadata_bytes=metadata_bytes,
            deprecated_by=5000,
        )

        assert metadata.deprecated_by == 5000

    def test_from_bytes_validate_json_false(self) -> None:
        """Test from_bytes with validate_json_object=False."""
        # Invalid JSON, but validation disabled
        metadata_bytes = b"not valid json"
        metadata = AssetMetadata.from_bytes(
            asset_id=123,
            metadata_bytes=metadata_bytes,
            validate_json_object=False,
        )

        assert metadata.body.raw_bytes == metadata_bytes

    def test_from_bytes_arc3_compliant(self) -> None:
        """Test from_bytes with arc3_compliant=True."""
        metadata_bytes = b'{"name":"Test","decimals":0}'
        metadata = AssetMetadata.from_bytes(
            asset_id=123,
            metadata_bytes=metadata_bytes,
            arc3_compliant=True,
        )

        assert metadata.body.raw_bytes == metadata_bytes

    def test_from_bytes_arc3_compliant_invalid_raises(self) -> None:
        """Test from_bytes with arc3_compliant=True and invalid metadata."""
        metadata_bytes = b'{"decimals":"not int"}'

        with pytest.raises(MetadataArc3Error):
            AssetMetadata.from_bytes(
                asset_id=123,
                metadata_bytes=metadata_bytes,
                arc3_compliant=True,
            )
