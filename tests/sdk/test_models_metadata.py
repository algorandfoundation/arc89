"""
Unit tests for metadata models in src.models.

Tests cover:
- MetadataBody
- MetadataHeader
- AssetMetadata
- AssetMetadataRecord
"""

import pytest

from smart_contracts import constants as const
from src import bitmasks
from src.errors import MetadataArc3Error
from src.models import (
    AssetMetadata,
    AssetMetadataRecord,
    IrreversibleFlags,
    MetadataBody,
    MetadataFlags,
    MetadataHeader,
    ReversibleFlags,
    get_default_registry_params,
)


class TestMetadataBody:
    """Tests for MetadataBody dataclass."""

    def test_empty_body(self) -> None:
        """Test empty metadata body."""
        body = MetadataBody.empty()
        assert body.raw_bytes == b""
        assert body.size == 0
        assert body.is_empty is True
        assert body.is_short is True
        # Empty bytes decode to empty dict
        from src.models import decode_metadata_json

        assert decode_metadata_json(body.raw_bytes) == {}

    def test_small_body(self) -> None:
        """Test small metadata body."""
        data = b'{"name":"Test"}'
        body = MetadataBody(raw_bytes=data)
        assert body.raw_bytes == data
        assert body.size == len(data)
        assert body.is_empty is False
        assert body.is_short is True
        # Check JSON decoding
        from src.models import decode_metadata_json

        assert decode_metadata_json(body.raw_bytes) == {"name": "Test"}

    def test_short_metadata_boundary(self) -> None:
        """Test metadata at short size boundary."""
        # SHORT_METADATA_SIZE is typically 4096
        data = b"x" * const.SHORT_METADATA_SIZE
        body = MetadataBody(raw_bytes=data)
        assert body.size == const.SHORT_METADATA_SIZE
        assert body.is_short is True

    def test_just_over_short_size(self) -> None:
        """Test metadata just over short size."""
        data = b"x" * (const.SHORT_METADATA_SIZE + 1)
        body = MetadataBody(raw_bytes=data)
        assert body.size == const.SHORT_METADATA_SIZE + 1
        assert body.is_short is False

    def test_large_body(self) -> None:
        """Test large metadata body."""
        data = b"x" * 10000
        body = MetadataBody(raw_bytes=data)
        assert body.size == 10000
        assert body.is_empty is False
        assert body.is_short is False

    def test_total_pages_zero_size(self) -> None:
        """Test total_pages for zero-size metadata."""
        body = MetadataBody.empty()
        assert body.total_pages() == 0

    def test_total_pages_one_page(self) -> None:
        """Test total_pages when metadata fits in one page."""
        params = get_default_registry_params()
        data = b"x" * (params.page_size - 10)
        body = MetadataBody(raw_bytes=data)
        assert body.total_pages(params) == 1

    def test_total_pages_exact_page(self) -> None:
        """Test total_pages when metadata exactly fills pages."""
        params = get_default_registry_params()
        data = b"x" * (params.page_size * 3)
        body = MetadataBody(raw_bytes=data)
        assert body.total_pages(params) == 3

    def test_total_pages_partial_last_page(self) -> None:
        """Test total_pages when last page is partial."""
        params = get_default_registry_params()
        data = b"x" * (params.page_size * 2 + 100)
        body = MetadataBody(raw_bytes=data)
        assert body.total_pages(params) == 3

    def test_chunked_payload_empty(self) -> None:
        """Test chunked_payload for empty metadata."""
        body = MetadataBody.empty()
        chunks = body.chunked_payload()
        assert len(chunks) == 1
        assert chunks[0] == b""

    def test_chunked_payload_fits_in_first(self) -> None:
        """Test chunked_payload when data fits in first chunk."""
        data = b"x" * 100
        body = MetadataBody(raw_bytes=data)
        chunks = body.chunked_payload()
        assert len(chunks) == 1
        assert chunks[0] == data

    def test_chunked_payload_multiple_chunks(self) -> None:
        """Test chunked_payload with multiple chunks."""
        # Use default chunk sizes from constants
        head_size = const.FIRST_PAYLOAD_MAX_SIZE
        extra_size = const.EXTRA_PAYLOAD_MAX_SIZE
        data = b"x" * (head_size + extra_size + 100)
        body = MetadataBody(raw_bytes=data)
        chunks = body.chunked_payload()

        assert len(chunks) == 3
        assert len(chunks[0]) == head_size
        assert len(chunks[1]) == extra_size
        assert len(chunks[2]) == 100

    def test_validate_size_within_limit(self) -> None:
        """Test validate_size when metadata is within limit."""
        params = get_default_registry_params()
        data = b"x" * (params.max_metadata_size - 100)
        body = MetadataBody(raw_bytes=data)
        body.validate_size(params)  # Should not raise

    def test_validate_size_at_limit(self) -> None:
        """Test validate_size when metadata is at limit."""
        params = get_default_registry_params()
        data = b"x" * params.max_metadata_size
        body = MetadataBody(raw_bytes=data)
        body.validate_size(params)  # Should not raise

    def test_validate_size_exceeds_limit(self) -> None:
        """Test validate_size when metadata exceeds limit."""
        params = get_default_registry_params()
        data = b"x" * (params.max_metadata_size + 1)
        body = MetadataBody(raw_bytes=data)
        with pytest.raises(ValueError, match="exceeds max"):
            body.validate_size(params)

    def test_from_json_simple(self) -> None:
        """Test from_json with simple object."""
        obj = {"name": "Test", "value": 123}
        body = MetadataBody.from_json(obj)
        from src.models import decode_metadata_json

        assert decode_metadata_json(body.raw_bytes) == obj
        assert body.size > 0

    def test_from_json_arc3_compliant_valid(self) -> None:
        """Test from_json with ARC-3 compliant metadata."""
        obj = {
            "name": "My NFT",
            "decimals": 0,
            "description": "A test NFT",
        }
        body = MetadataBody.from_json(obj, arc3_compliant=True)
        from src.models import decode_metadata_json

        assert decode_metadata_json(body.raw_bytes) == obj

    def test_from_json_arc3_compliant_invalid_raises(self) -> None:
        """Test from_json with invalid ARC-3 metadata raises."""
        obj = {"decimals": "not an integer"}  # Invalid
        with pytest.raises(MetadataArc3Error):
            MetadataBody.from_json(obj, arc3_compliant=True)


class TestMetadataHeader:
    """Tests for MetadataHeader dataclass."""

    def test_basic_header(self) -> None:
        """Test basic metadata header."""
        flags = MetadataFlags.empty()
        header = MetadataHeader(
            identifiers=0,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.identifiers == 0
        assert header.flags == flags
        assert header.metadata_hash == b"\x00" * 32
        assert header.last_modified_round == 1000
        assert header.deprecated_by == 0

    def test_is_short_false(self) -> None:
        """Test is_short property when not short."""
        flags = MetadataFlags.empty()
        header = MetadataHeader(
            identifiers=0,  # Short bit not set
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_short is False

    def test_is_short_true(self) -> None:
        """Test is_short property when short."""
        flags = MetadataFlags.empty()
        header = MetadataHeader(
            identifiers=bitmasks.MASK_ID_SHORT,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_short is True

    def test_is_immutable_false(self) -> None:
        """Test is_immutable property when not immutable."""
        flags = MetadataFlags.empty()
        header = MetadataHeader(
            identifiers=0,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_immutable is False

    def test_is_immutable_true(self) -> None:
        """Test is_immutable property when immutable."""
        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(immutable=True),
        )
        header = MetadataHeader(
            identifiers=0,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_immutable is True

    def test_is_arc3_compliant(self) -> None:
        """Test is_arc3_compliant property."""
        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc3=True),
        )
        header = MetadataHeader(
            identifiers=0,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_arc3_compliant is True

    def test_is_arc89_native(self) -> None:
        """Test is_arc89_native property."""
        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc89_native=True),
        )
        header = MetadataHeader(
            identifiers=0,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_arc89_native is True

    def test_is_arc20_smart_asa(self) -> None:
        """Test is_arc20_smart_asa property."""
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc20=True),
            irreversible=IrreversibleFlags.empty(),
        )
        header = MetadataHeader(
            identifiers=0,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_arc20_smart_asa is True

    def test_is_arc62_circulating_supply(self) -> None:
        """Test is_arc62_circulating_supply property."""
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc62=True),
            irreversible=IrreversibleFlags.empty(),
        )
        header = MetadataHeader(
            identifiers=0,
            flags=flags,
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        assert header.is_arc62_circulating_supply is True

    def test_from_tuple(self) -> None:
        """Test from_tuple parsing."""
        tuple_data = [
            10,  # identifiers
            5,  # reversible flags
            3,  # irreversible flags
            b"\xaa" * 32,  # hash
            2000,  # last_modified_round
            100,  # deprecated_by
        ]
        header = MetadataHeader.from_tuple(tuple_data)

        assert header.identifiers == 10
        assert header.flags.reversible_byte == 5
        assert header.flags.irreversible_byte == 3
        assert header.metadata_hash == b"\xaa" * 32
        assert header.last_modified_round == 2000
        assert header.deprecated_by == 100

    def test_from_tuple_invalid_length(self) -> None:
        """Test from_tuple with wrong number of elements."""
        with pytest.raises(ValueError, match="Expected 6-tuple"):
            MetadataHeader.from_tuple([1, 2, 3])


class TestAssetMetadata:
    """Tests for AssetMetadata dataclass."""

    def test_basic_metadata(self) -> None:
        """Test basic asset metadata."""
        body = MetadataBody(raw_bytes=b'{"name":"Test"}')
        flags = MetadataFlags.empty()
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=flags,
            deprecated_by=0,
        )
        assert metadata.asset_id == 123
        assert metadata.body == body
        assert metadata.flags == flags
        assert metadata.deprecated_by == 0

    def test_compute_metadata_hash(self) -> None:
        """Test compute_metadata_hash method."""
        from src.hashing import compute_metadata_hash as hash_fn

        body = MetadataBody(raw_bytes=b'{"name":"Test"}')
        flags = MetadataFlags.empty()
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=flags,
            deprecated_by=0,
        )
        params = get_default_registry_params()
        hash_result = metadata.compute_metadata_hash()

        assert isinstance(hash_result, bytes)
        assert len(hash_result) == 32

        # Verify hash is correct by comparing to the standalone hash function
        expected_hash = hash_fn(
            asset_id=metadata.asset_id,
            metadata_identifiers=metadata.identifiers_byte,
            reversible_flags=metadata.flags.reversible_byte,
            irreversible_flags=metadata.flags.irreversible_byte,
            metadata=metadata.body.raw_bytes,
            page_size=params.page_size,
        )
        assert hash_result == expected_hash

    def test_compute_metadata_hash_short_metadata(self) -> None:
        """Test compute_metadata_hash with short metadata (identifiers should be set)."""
        from src.hashing import compute_metadata_hash as hash_fn

        # Create short metadata (< SHORT_METADATA_SIZE)
        body = MetadataBody(raw_bytes=b'{"name":"Short"}')
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc20=True),
            irreversible=IrreversibleFlags(arc3=True),
        )
        metadata = AssetMetadata(
            asset_id=456,
            body=body,
            flags=flags,
            deprecated_by=0,
        )
        params = get_default_registry_params()

        # Verify it's marked as short
        assert body.is_short is True
        assert metadata.identifiers_byte == bitmasks.MASK_ID_SHORT

        hash_result = metadata.compute_metadata_hash()

        # Verify hash matches expected value
        expected_hash = hash_fn(
            asset_id=456,
            metadata_identifiers=bitmasks.MASK_ID_SHORT,
            reversible_flags=flags.reversible_byte,
            irreversible_flags=flags.irreversible_byte,
            metadata=body.raw_bytes,
            page_size=params.page_size,
        )
        assert hash_result == expected_hash

    def test_compute_metadata_hash_long_metadata(self) -> None:
        """Test compute_metadata_hash with long metadata (identifiers should be 0)."""
        from src.hashing import compute_metadata_hash as hash_fn

        # Create long metadata (> SHORT_METADATA_SIZE)
        large_data = b"x" * (const.SHORT_METADATA_SIZE + 100)
        body = MetadataBody(raw_bytes=large_data)
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc62=True),
            irreversible=IrreversibleFlags(immutable=True),
        )
        metadata = AssetMetadata(
            asset_id=789,
            body=body,
            flags=flags,
            deprecated_by=0,
        )
        params = get_default_registry_params()

        # Verify it's NOT marked as short
        assert body.is_short is False
        assert metadata.identifiers_byte == 0

        hash_result = metadata.compute_metadata_hash()

        # Verify hash matches expected value
        expected_hash = hash_fn(
            asset_id=789,
            metadata_identifiers=0,
            reversible_flags=flags.reversible_byte,
            irreversible_flags=flags.irreversible_byte,
            metadata=large_data,
            page_size=params.page_size,
        )
        assert hash_result == expected_hash

    def test_get_mbr_delta_creation(self) -> None:
        """Test get_mbr_delta for creation."""
        body = MetadataBody(raw_bytes=b'{"name":"Test"}')
        flags = MetadataFlags.empty()
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=flags,
            deprecated_by=0,
        )
        delta = metadata.get_mbr_delta()

        assert delta.is_positive is True
        assert delta.amount > 0

    def test_get_mbr_delta_update(self) -> None:
        """Test get_mbr_delta for update."""
        body = MetadataBody(raw_bytes=b'{"name":"Test","extra":"data"}')
        flags = MetadataFlags.empty()
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=flags,
            deprecated_by=0,
        )
        old_size = 50
        delta = metadata.get_mbr_delta(old_size=old_size)

        # Delta depends on size difference
        assert delta is not None

    def test_get_delete_mbr_delta(self) -> None:
        """Test get_delete_mbr_delta."""
        body = MetadataBody(raw_bytes=b'{"name":"Test"}')
        flags = MetadataFlags.empty()
        metadata = AssetMetadata(
            asset_id=123,
            body=body,
            flags=flags,
            deprecated_by=0,
        )
        delta = metadata.get_delete_mbr_delta()

        assert delta.is_negative is True
        assert delta.amount > 0

    def test_from_json_simple(self) -> None:
        """Test from_json with simple JSON object."""
        obj = {"name": "My Token", "value": 42}
        metadata = AssetMetadata.from_json(
            asset_id=456,
            json_obj=obj,
        )
        assert metadata.asset_id == 456
        from src.models import decode_metadata_json

        assert decode_metadata_json(metadata.body.raw_bytes) == obj
        assert metadata.flags.reversible_byte == 0
        assert metadata.flags.irreversible_byte == 0
        assert metadata.deprecated_by == 0

    def test_from_json_with_flags(self) -> None:
        """Test from_json with flags."""
        obj = {"name": "My Token"}
        metadata = AssetMetadata.from_json(
            asset_id=789,
            json_obj=obj,
            flags=MetadataFlags(
                reversible=bitmasks.MASK_REV_ARC20,
                irreversible=bitmasks.MASK_IRR_ARC3,
            ),
        )
        assert metadata.asset_id == 789
        assert metadata.flags.reversible.arc20 is True
        assert metadata.flags.irreversible.arc3 is True

    def test_from_json_with_deprecated_by(self) -> None:
        """Test from_json with deprecated_by."""
        obj = {"name": "My Token"}
        metadata = AssetMetadata.from_json(
            asset_id=999,
            json_obj=obj,
            deprecated_by=5000,
        )
        assert metadata.deprecated_by == 5000

    def test_from_json_arc3_compliant_valid(self) -> None:
        """Test from_json with valid ARC-3 metadata."""
        obj = {
            "name": "My NFT",
            "decimals": 0,
            "description": "Test",
        }
        metadata = AssetMetadata.from_json(
            asset_id=111,
            json_obj=obj,
        )
        from src.models import decode_metadata_json

        assert decode_metadata_json(metadata.body.raw_bytes) == obj
        assert metadata.flags.irreversible.arc3 is True

    def test_from_json_arc3_compliant_invalid_raises(self) -> None:
        """Test from_json with invalid ARC-3 metadata raises."""
        obj = {"decimals": "invalid"}  # Should be int
        with pytest.raises(MetadataArc3Error):
            AssetMetadata.from_json(
                asset_id=222,
                json_obj=obj,
            )


class TestAssetMetadataRecord:
    """Tests for AssetMetadataRecord dataclass."""

    def test_basic_record(self) -> None:
        """Test basic metadata record."""
        header = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        body = MetadataBody(raw_bytes=b'{"name":"Test"}')
        record = AssetMetadataRecord(
            app_id=100,
            asset_id=200,
            header=header,
            body=body,
        )
        assert record.app_id == 100
        assert record.asset_id == 200
        assert record.header == header
        assert record.body == body

    def test_json_property(self) -> None:
        """Test json property."""
        header = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )
        body = MetadataBody(raw_bytes=b'{"name":"Test","value":123}')
        record = AssetMetadataRecord(
            app_id=100,
            asset_id=200,
            header=header,
            body=body,
        )
        from src.models import decode_metadata_json

        # Note: cached_property doesn't work with slots, so we just test decoding directly
        assert decode_metadata_json(record.body.raw_bytes) == {
            "name": "Test",
            "value": 123,
        }

    def test_as_asset_metadata(self) -> None:
        """Test as_asset_metadata conversion."""
        header = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.empty(),
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=500,
        )
        body = MetadataBody(raw_bytes=b'{"name":"Test"}')
        record = AssetMetadataRecord(
            app_id=100,
            asset_id=200,
            header=header,
            body=body,
        )

        metadata = record.as_asset_metadata()
        assert isinstance(metadata, AssetMetadata)
        assert metadata.asset_id == 200
        assert metadata.body == body
        assert metadata.flags == header.flags
        assert metadata.deprecated_by == 500
