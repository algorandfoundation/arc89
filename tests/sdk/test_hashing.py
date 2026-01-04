"""
Unit tests for src.hashing module.

Tests cover:
- sha512_256 hash function
- sha256 hash function
- compute_header_hash
- paginate
- compute_page_hash
- compute_metadata_hash
- compute_arc3_metadata_hash
"""

import base64
import json

import pytest

from smart_contracts import constants as const
from src.asa_metadata_registry import hashing
from src.asa_metadata_registry.codec import asset_id_to_box_name


class TestSha512_256:  # noqa: N801
    """Tests for sha512_256 hash function."""

    def test_empty_bytes(self) -> None:
        """Test hashing empty bytes."""
        result = hashing.sha512_256(b"")
        assert len(result) == 32
        # Known SHA-512/256 hash of empty string
        expected = bytes.fromhex(
            "c672b8d1ef56ed28ab87c3622c5114069bdd3ad7b8f9737498d0c01ecef0967a"
        )
        assert result == expected

    def test_simple_string(self) -> None:
        """Test hashing simple string."""
        result = hashing.sha512_256(b"hello world")
        assert len(result) == 32
        # Known SHA-512/256 hash of "hello world"
        expected = bytes.fromhex(
            "0ac561fac838104e3f2e4ad107b4bee3e938bf15f2b15f009ccccd61a913f017"
        )
        assert result == expected

    def test_deterministic(self) -> None:
        """Test that hash is deterministic."""
        data = b"test data"
        result1 = hashing.sha512_256(data)
        result2 = hashing.sha512_256(data)
        assert result1 == result2

    def test_different_inputs_different_outputs(self) -> None:
        """Test that different inputs produce different hashes."""
        result1 = hashing.sha512_256(b"data1")
        result2 = hashing.sha512_256(b"data2")
        assert result1 != result2


class TestSha256:
    """Tests for sha256 hash function."""

    def test_empty_bytes(self) -> None:
        """Test hashing empty bytes."""
        result = hashing.sha256(b"")
        assert len(result) == 32
        # Known SHA-256 hash of empty string
        expected = bytes.fromhex(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        assert result == expected

    def test_simple_string(self) -> None:
        """Test hashing simple string."""
        result = hashing.sha256(b"hello world")
        assert len(result) == 32
        # Known SHA-256 hash of "hello world"
        expected = bytes.fromhex(
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        )
        assert result == expected

    def test_deterministic(self) -> None:
        """Test that hash is deterministic."""
        data = b"test data"
        result1 = hashing.sha256(data)
        result2 = hashing.sha256(data)
        assert result1 == result2

    def test_different_inputs_different_outputs(self) -> None:
        """Test that different inputs produce different hashes."""
        result1 = hashing.sha256(b"data1")
        result2 = hashing.sha256(b"data2")
        assert result1 != result2


class TestComputeHeaderHash:
    """Tests for compute_header_hash function."""

    def test_basic_header_hash(self) -> None:
        """Test computing header hash with basic parameters."""
        result = hashing.compute_header_hash(
            asset_id=12345,
            metadata_identifiers=0b10101010,
            reversible_flags=0b11001100,
            irreversible_flags=0b00110011,
            metadata_size=1024,
        )
        assert len(result) == 32

    def test_zero_values(self) -> None:
        """Test header hash with all zero values."""
        result = hashing.compute_header_hash(
            asset_id=0,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata_size=0,
        )
        assert len(result) == 32

    def test_max_values(self) -> None:
        """Test header hash with maximum values."""
        result = hashing.compute_header_hash(
            asset_id=2**64 - 1,
            metadata_identifiers=255,
            reversible_flags=255,
            irreversible_flags=255,
            metadata_size=65535,
        )
        assert len(result) == 32

    def test_deterministic(self) -> None:
        """Test that header hash is deterministic."""
        params = {
            "asset_id": 99999,
            "metadata_identifiers": 42,
            "reversible_flags": 128,
            "irreversible_flags": 64,
            "metadata_size": 512,
        }
        result1 = hashing.compute_header_hash(**params)
        result2 = hashing.compute_header_hash(**params)
        assert result1 == result2

    def test_different_asset_id_different_hash(self) -> None:
        """Test that different asset IDs produce different hashes."""
        result1 = hashing.compute_header_hash(
            asset_id=1,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata_size=100,
        )
        result2 = hashing.compute_header_hash(
            asset_id=2,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata_size=100,
        )
        assert result1 != result2

    def test_different_identifiers_different_hash(self) -> None:
        """Test that different metadata identifiers produce different hashes."""
        result1 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=1,
            reversible_flags=0,
            irreversible_flags=0,
            metadata_size=100,
        )
        result2 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=2,
            reversible_flags=0,
            irreversible_flags=0,
            metadata_size=100,
        )
        assert result1 != result2

    def test_different_reversible_flags_different_hash(self) -> None:
        """Test that different reversible flags produce different hashes."""
        result1 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=1,
            irreversible_flags=0,
            metadata_size=100,
        )
        result2 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=2,
            irreversible_flags=0,
            metadata_size=100,
        )
        assert result1 != result2

    def test_different_irreversible_flags_different_hash(self) -> None:
        """Test that different irreversible flags produce different hashes."""
        result1 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=1,
            metadata_size=100,
        )
        result2 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=2,
            metadata_size=100,
        )
        assert result1 != result2

    def test_different_metadata_size_different_hash(self) -> None:
        """Test that different metadata sizes produce different hashes."""
        result1 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata_size=100,
        )
        result2 = hashing.compute_header_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata_size=200,
        )
        assert result1 != result2

    def test_metadata_identifiers_out_of_range_negative_raises(self) -> None:
        """Test that negative metadata_identifiers raises ValueError."""
        with pytest.raises(ValueError, match="metadata_identifiers must fit in byte"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=-1,
                reversible_flags=0,
                irreversible_flags=0,
                metadata_size=100,
            )

    def test_metadata_identifiers_out_of_range_overflow_raises(self) -> None:
        """Test that metadata_identifiers > 255 raises ValueError."""
        with pytest.raises(ValueError, match="metadata_identifiers must fit in byte"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=256,
                reversible_flags=0,
                irreversible_flags=0,
                metadata_size=100,
            )

    def test_reversible_flags_out_of_range_negative_raises(self) -> None:
        """Test that negative reversible_flags raises ValueError."""
        with pytest.raises(ValueError, match="reversible_flags must fit in byte"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=0,
                reversible_flags=-1,
                irreversible_flags=0,
                metadata_size=100,
            )

    def test_reversible_flags_out_of_range_overflow_raises(self) -> None:
        """Test that reversible_flags > 255 raises ValueError."""
        with pytest.raises(ValueError, match="reversible_flags must fit in byte"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=0,
                reversible_flags=256,
                irreversible_flags=0,
                metadata_size=100,
            )

    def test_irreversible_flags_out_of_range_negative_raises(self) -> None:
        """Test that negative irreversible_flags raises ValueError."""
        with pytest.raises(ValueError, match="irreversible_flags must fit in byte"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=0,
                reversible_flags=0,
                irreversible_flags=-1,
                metadata_size=100,
            )

    def test_irreversible_flags_out_of_range_overflow_raises(self) -> None:
        """Test that irreversible_flags > 255 raises ValueError."""
        with pytest.raises(ValueError, match="irreversible_flags must fit in byte"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=0,
                reversible_flags=0,
                irreversible_flags=256,
                metadata_size=100,
            )

    def test_metadata_size_out_of_range_negative_raises(self) -> None:
        """Test that negative metadata_size raises ValueError."""
        with pytest.raises(ValueError, match="metadata_size must fit in uint16"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=0,
                reversible_flags=0,
                irreversible_flags=0,
                metadata_size=-1,
            )

    def test_metadata_size_out_of_range_overflow_raises(self) -> None:
        """Test that metadata_size > 65535 raises ValueError."""
        with pytest.raises(ValueError, match="metadata_size must fit in uint16"):
            hashing.compute_header_hash(
                asset_id=100,
                metadata_identifiers=0,
                reversible_flags=0,
                irreversible_flags=0,
                metadata_size=65536,
            )

    def test_header_hash_domain_separator(self) -> None:
        """Test that header hash uses correct domain separator."""
        # The hash should include the domain separator const.HASH_DOMAIN_HEADER
        # We can verify by manually constructing the expected input
        asset_id = 12345
        metadata_identifiers = 10
        reversible_flags = 20
        irreversible_flags = 30
        metadata_size = 500

        expected_data = (
            const.HASH_DOMAIN_HEADER
            + asset_id_to_box_name(asset_id)
            + bytes([metadata_identifiers])
            + bytes([reversible_flags])
            + bytes([irreversible_flags])
            + metadata_size.to_bytes(const.UINT16_SIZE, "big", signed=False)
        )
        expected_hash = hashing.sha512_256(expected_data)

        result = hashing.compute_header_hash(
            asset_id=asset_id,
            metadata_identifiers=metadata_identifiers,
            reversible_flags=reversible_flags,
            irreversible_flags=irreversible_flags,
            metadata_size=metadata_size,
        )
        assert result == expected_hash


class TestPaginate:
    """Tests for paginate function."""

    def test_empty_metadata(self) -> None:
        """Test paginating empty metadata."""
        result = hashing.paginate(b"", page_size=100)
        assert result == []

    def test_single_page_exact(self) -> None:
        """Test metadata that fits exactly in one page."""
        metadata = b"x" * 100
        result = hashing.paginate(metadata, page_size=100)
        assert len(result) == 1
        assert result[0] == metadata

    def test_single_page_partial(self) -> None:
        """Test metadata smaller than one page."""
        metadata = b"hello"
        result = hashing.paginate(metadata, page_size=100)
        assert len(result) == 1
        assert result[0] == metadata

    def test_multiple_pages_exact(self) -> None:
        """Test metadata that fits exactly in multiple pages."""
        metadata = b"x" * 300
        result = hashing.paginate(metadata, page_size=100)
        assert len(result) == 3
        assert all(len(page) == 100 for page in result)
        assert b"".join(result) == metadata

    def test_multiple_pages_partial_last(self) -> None:
        """Test metadata with partial last page."""
        metadata = b"x" * 250
        result = hashing.paginate(metadata, page_size=100)
        assert len(result) == 3
        assert len(result[0]) == 100
        assert len(result[1]) == 100
        assert len(result[2]) == 50
        assert b"".join(result) == metadata

    def test_page_size_one(self) -> None:
        """Test paginating with page size of 1."""
        metadata = b"hello"
        result = hashing.paginate(metadata, page_size=1)
        assert len(result) == 5
        assert all(len(page) == 1 for page in result)
        assert b"".join(result) == metadata

    def test_page_size_larger_than_metadata(self) -> None:
        """Test page size larger than metadata."""
        metadata = b"hello"
        result = hashing.paginate(metadata, page_size=1000)
        assert len(result) == 1
        assert result[0] == metadata

    def test_page_size_zero_raises(self) -> None:
        """Test that page_size of 0 raises ValueError."""
        with pytest.raises(ValueError, match="page_size must be > 0"):
            hashing.paginate(b"test", page_size=0)

    def test_page_size_negative_raises(self) -> None:
        """Test that negative page_size raises ValueError."""
        with pytest.raises(ValueError, match="page_size must be > 0"):
            hashing.paginate(b"test", page_size=-1)

    def test_preserves_metadata_content(self) -> None:
        """Test that pagination preserves metadata content."""
        metadata = b"The quick brown fox jumps over the lazy dog"
        result = hashing.paginate(metadata, page_size=10)
        reassembled = b"".join(result)
        assert reassembled == metadata

    def test_large_metadata(self) -> None:
        """Test paginating large metadata."""
        metadata = b"A" * 10000
        result = hashing.paginate(metadata, page_size=1024)
        assert len(result) == 10  # 10000 / 1024 = 9.765... -> 10 pages
        assert b"".join(result) == metadata


class TestComputePageHash:
    """Tests for compute_page_hash function."""

    def test_basic_page_hash(self) -> None:
        """Test computing page hash with basic parameters."""
        result = hashing.compute_page_hash(
            asset_id=12345,
            page_index=0,
            page_content=b"hello world",
        )
        assert len(result) == 32

    def test_empty_page(self) -> None:
        """Test page hash with empty content."""
        result = hashing.compute_page_hash(
            asset_id=100,
            page_index=0,
            page_content=b"",
        )
        assert len(result) == 32

    def test_max_page_size(self) -> None:
        """Test page hash with maximum page size (uint16 max)."""
        result = hashing.compute_page_hash(
            asset_id=100,
            page_index=0,
            page_content=b"x" * 65535,
        )
        assert len(result) == 32

    def test_deterministic(self) -> None:
        """Test that page hash is deterministic."""
        params = {
            "asset_id": 99999,
            "page_index": 5,
            "page_content": b"test page content",
        }
        result1 = hashing.compute_page_hash(**params)
        result2 = hashing.compute_page_hash(**params)
        assert result1 == result2

    def test_different_asset_id_different_hash(self) -> None:
        """Test that different asset IDs produce different hashes."""
        result1 = hashing.compute_page_hash(
            asset_id=1,
            page_index=0,
            page_content=b"content",
        )
        result2 = hashing.compute_page_hash(
            asset_id=2,
            page_index=0,
            page_content=b"content",
        )
        assert result1 != result2

    def test_different_page_index_different_hash(self) -> None:
        """Test that different page indices produce different hashes."""
        result1 = hashing.compute_page_hash(
            asset_id=100,
            page_index=0,
            page_content=b"content",
        )
        result2 = hashing.compute_page_hash(
            asset_id=100,
            page_index=1,
            page_content=b"content",
        )
        assert result1 != result2

    def test_different_page_content_different_hash(self) -> None:
        """Test that different page content produces different hashes."""
        result1 = hashing.compute_page_hash(
            asset_id=100,
            page_index=0,
            page_content=b"content1",
        )
        result2 = hashing.compute_page_hash(
            asset_id=100,
            page_index=0,
            page_content=b"content2",
        )
        assert result1 != result2

    def test_page_index_max(self) -> None:
        """Test page hash with maximum page index (255)."""
        result = hashing.compute_page_hash(
            asset_id=100,
            page_index=255,
            page_content=b"test",
        )
        assert len(result) == 32

    def test_page_index_out_of_range_negative_raises(self) -> None:
        """Test that negative page_index raises ValueError."""
        with pytest.raises(ValueError, match="page_index must fit in uint8"):
            hashing.compute_page_hash(
                asset_id=100,
                page_index=-1,
                page_content=b"test",
            )

    def test_page_index_out_of_range_overflow_raises(self) -> None:
        """Test that page_index > 255 raises ValueError."""
        with pytest.raises(ValueError, match="page_index must fit in uint8"):
            hashing.compute_page_hash(
                asset_id=100,
                page_index=256,
                page_content=b"test",
            )

    def test_page_content_too_large_raises(self) -> None:
        """Test that page_content larger than uint16 max raises ValueError."""
        with pytest.raises(ValueError, match="page_content length must fit in uint16"):
            hashing.compute_page_hash(
                asset_id=100,
                page_index=0,
                page_content=b"x" * 65536,
            )

    def test_page_hash_domain_separator(self) -> None:
        """Test that page hash uses correct domain separator."""
        asset_id = 12345
        page_index = 3
        page_content = b"test page"

        expected_data = (
            const.HASH_DOMAIN_PAGE
            + asset_id_to_box_name(asset_id)
            + bytes([page_index])
            + len(page_content).to_bytes(const.UINT16_SIZE, "big", signed=False)
            + page_content
        )
        expected_hash = hashing.sha512_256(expected_data)

        result = hashing.compute_page_hash(
            asset_id=asset_id,
            page_index=page_index,
            page_content=page_content,
        )
        assert result == expected_hash


class TestComputeMetadataHash:
    """Tests for compute_metadata_hash function."""

    def test_empty_metadata(self) -> None:
        """Test metadata hash with empty metadata."""
        result = hashing.compute_metadata_hash(
            asset_id=12345,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=b"",
            page_size=1024,
        )
        assert len(result) == 32

    def test_single_page_metadata(self) -> None:
        """Test metadata hash with single page of metadata."""
        result = hashing.compute_metadata_hash(
            asset_id=12345,
            metadata_identifiers=1,
            reversible_flags=2,
            irreversible_flags=3,
            metadata=b"hello world",
            page_size=1024,
        )
        assert len(result) == 32

    def test_multiple_pages_metadata(self) -> None:
        """Test metadata hash with multiple pages."""
        metadata = b"x" * 3000
        result = hashing.compute_metadata_hash(
            asset_id=12345,
            metadata_identifiers=1,
            reversible_flags=2,
            irreversible_flags=3,
            metadata=metadata,
            page_size=1024,
        )
        assert len(result) == 32

    def test_deterministic(self) -> None:
        """Test that metadata hash is deterministic."""
        params = {
            "asset_id": 99999,
            "metadata_identifiers": 5,
            "reversible_flags": 10,
            "irreversible_flags": 15,
            "metadata": b"test metadata content",
            "page_size": 1024,
        }
        result1 = hashing.compute_metadata_hash(**params)
        result2 = hashing.compute_metadata_hash(**params)
        assert result1 == result2

    def test_different_metadata_different_hash(self) -> None:
        """Test that different metadata produces different hashes."""
        result1 = hashing.compute_metadata_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=b"metadata1",
            page_size=1024,
        )
        result2 = hashing.compute_metadata_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=b"metadata2",
            page_size=1024,
        )
        assert result1 != result2

    def test_different_page_size_different_hash(self) -> None:
        """Test that different page sizes produce different hashes."""
        metadata = b"x" * 2000
        result1 = hashing.compute_metadata_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=metadata,
            page_size=512,
        )
        result2 = hashing.compute_metadata_hash(
            asset_id=100,
            metadata_identifiers=0,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=metadata,
            page_size=1024,
        )
        assert result1 != result2

    def test_metadata_hash_includes_header_hash(self) -> None:
        """Test that metadata hash incorporates header hash."""
        asset_id = 12345
        metadata_identifiers = 5
        reversible_flags = 10
        irreversible_flags = 15
        metadata = b"test"
        page_size = 1024

        # Compute expected hash manually
        hh = hashing.compute_header_hash(
            asset_id=asset_id,
            metadata_identifiers=metadata_identifiers,
            reversible_flags=reversible_flags,
            irreversible_flags=irreversible_flags,
            metadata_size=len(metadata),
        )
        pages = hashing.paginate(metadata, page_size=page_size)

        data = const.HASH_DOMAIN_METADATA + hh
        for i, p in enumerate(pages):
            data += hashing.compute_page_hash(
                asset_id=asset_id, page_index=i, page_content=p
            )
        expected = hashing.sha512_256(data)

        result = hashing.compute_metadata_hash(
            asset_id=asset_id,
            metadata_identifiers=metadata_identifiers,
            reversible_flags=reversible_flags,
            irreversible_flags=irreversible_flags,
            metadata=metadata,
            page_size=page_size,
        )
        assert result == expected

    def test_empty_metadata_only_includes_header_hash(self) -> None:
        """Test that empty metadata hash only includes header hash."""
        asset_id = 12345
        metadata_identifiers = 5
        reversible_flags = 10
        irreversible_flags = 15

        hh = hashing.compute_header_hash(
            asset_id=asset_id,
            metadata_identifiers=metadata_identifiers,
            reversible_flags=reversible_flags,
            irreversible_flags=irreversible_flags,
            metadata_size=0,
        )
        expected = hashing.sha512_256(const.HASH_DOMAIN_METADATA + hh)

        result = hashing.compute_metadata_hash(
            asset_id=asset_id,
            metadata_identifiers=metadata_identifiers,
            reversible_flags=reversible_flags,
            irreversible_flags=irreversible_flags,
            metadata=b"",
            page_size=1024,
        )
        assert result == expected

    def test_different_header_params_different_hash(self) -> None:
        """Test that different header parameters affect the hash."""
        metadata = b"same content"

        result1 = hashing.compute_metadata_hash(
            asset_id=100,
            metadata_identifiers=1,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=metadata,
            page_size=1024,
        )
        result2 = hashing.compute_metadata_hash(
            asset_id=100,
            metadata_identifiers=2,
            reversible_flags=0,
            irreversible_flags=0,
            metadata=metadata,
            page_size=1024,
        )
        assert result1 != result2


class TestComputeArc3MetadataHash:
    """Tests for compute_arc3_metadata_hash function."""

    def test_simple_json_no_extra_metadata(self) -> None:
        """Test ARC-3 hash with simple JSON without extra_metadata."""
        json_obj = {"name": "Test Asset", "description": "A test asset"}
        json_bytes = json.dumps(json_obj).encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # Without extra_metadata, should use SHA-256
        expected = hashing.sha256(json_bytes)
        assert result == expected

    def test_json_with_extra_metadata(self) -> None:
        """Test ARC-3 hash with extra_metadata field."""
        extra_data = b"extra binary data"
        extra_b64 = base64.b64encode(extra_data).decode("ascii")

        json_obj = {
            "name": "Test Asset",
            "description": "A test asset",
            "extra_metadata": extra_b64,
        }
        json_bytes = json.dumps(json_obj).encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # With extra_metadata, should use SHA-512/256 double hash
        json_h = hashing.sha512_256(const.ARC3_HASH_AMJ_PREFIX + json_bytes)
        expected = hashing.sha512_256(const.ARC3_HASH_AM_PREFIX + json_h + extra_data)
        assert result == expected

    def test_json_with_empty_extra_metadata(self) -> None:
        """Test ARC-3 hash with empty extra_metadata."""
        extra_b64 = base64.b64encode(b"").decode("ascii")

        json_obj = {
            "name": "Test Asset",
            "extra_metadata": extra_b64,
        }
        json_bytes = json.dumps(json_obj).encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # Should still use double hash
        json_h = hashing.sha512_256(const.ARC3_HASH_AMJ_PREFIX + json_bytes)
        expected = hashing.sha512_256(const.ARC3_HASH_AM_PREFIX + json_h + b"")
        assert result == expected

    def test_deterministic(self) -> None:
        """Test that ARC-3 hash is deterministic."""
        json_obj = {"name": "Test", "description": "Test"}
        json_bytes = json.dumps(json_obj).encode("utf-8")

        result1 = hashing.compute_arc3_metadata_hash(json_bytes)
        result2 = hashing.compute_arc3_metadata_hash(json_bytes)
        assert result1 == result2

    def test_different_json_different_hash(self) -> None:
        """Test that different JSON produces different hashes."""
        json1 = json.dumps({"name": "Asset1"}).encode("utf-8")
        json2 = json.dumps({"name": "Asset2"}).encode("utf-8")

        result1 = hashing.compute_arc3_metadata_hash(json1)
        result2 = hashing.compute_arc3_metadata_hash(json2)
        assert result1 != result2

    def test_json_array_no_extra_metadata(self) -> None:
        """Test ARC-3 hash with JSON array (no extra_metadata key)."""
        json_bytes = json.dumps([1, 2, 3]).encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # JSON array has no extra_metadata, should use SHA-256
        expected = hashing.sha256(json_bytes)
        assert result == expected

    def test_json_string_no_extra_metadata(self) -> None:
        """Test ARC-3 hash with JSON string (no extra_metadata key)."""
        json_bytes = json.dumps("hello world").encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # JSON string has no extra_metadata, should use SHA-256
        expected = hashing.sha256(json_bytes)
        assert result == expected

    def test_json_number_no_extra_metadata(self) -> None:
        """Test ARC-3 hash with JSON number (no extra_metadata key)."""
        json_bytes = json.dumps(42).encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # JSON number has no extra_metadata, should use SHA-256
        expected = hashing.sha256(json_bytes)
        assert result == expected

    def test_invalid_utf8_raises(self) -> None:
        """Test that invalid UTF-8 raises ValueError."""
        invalid_bytes = b"\xff\xfe"  # Invalid UTF-8

        with pytest.raises(
            ValueError, match="Metadata file must be UTF-8 encoded JSON"
        ):
            hashing.compute_arc3_metadata_hash(invalid_bytes)

    def test_invalid_json_raises(self) -> None:
        """Test that invalid JSON raises ValueError."""
        invalid_json = b"{invalid json"

        with pytest.raises(ValueError, match="Invalid JSON metadata file"):
            hashing.compute_arc3_metadata_hash(invalid_json)

    def test_extra_metadata_not_string_raises(self) -> None:
        """Test that non-string extra_metadata raises ValueError."""
        json_obj = {
            "name": "Test",
            "extra_metadata": 123,  # Not a string
        }
        json_bytes = json.dumps(json_obj).encode("utf-8")

        with pytest.raises(
            ValueError, match='"extra_metadata" must be a base64 string when present'
        ):
            hashing.compute_arc3_metadata_hash(json_bytes)

    def test_extra_metadata_invalid_base64_raises(self) -> None:
        """Test that invalid base64 extra_metadata raises ValueError."""
        json_obj = {
            "name": "Test",
            "extra_metadata": "not valid base64!!!",
        }
        json_bytes = json.dumps(json_obj).encode("utf-8")

        with pytest.raises(
            ValueError, match='Could not base64-decode "extra_metadata"'
        ):
            hashing.compute_arc3_metadata_hash(json_bytes)

    def test_complex_json_with_extra_metadata(self) -> None:
        """Test ARC-3 hash with complex JSON structure and extra_metadata."""
        extra_data = b"\x00\x01\x02\x03\x04"
        extra_b64 = base64.b64encode(extra_data).decode("ascii")

        json_obj = {
            "name": "Complex Asset",
            "description": "A complex test asset",
            "decimals": 6,
            "properties": {
                "color": "blue",
                "size": "large",
            },
            "tags": ["tag1", "tag2", "tag3"],
            "extra_metadata": extra_b64,
        }
        json_bytes = json.dumps(json_obj).encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # Verify correct computation
        json_h = hashing.sha512_256(const.ARC3_HASH_AMJ_PREFIX + json_bytes)
        expected = hashing.sha512_256(const.ARC3_HASH_AM_PREFIX + json_h + extra_data)
        assert result == expected

    def test_extra_metadata_with_special_chars(self) -> None:
        """Test ARC-3 hash with extra_metadata containing special characters."""
        extra_data = b"Special \x00 chars \xff\xfe"
        extra_b64 = base64.b64encode(extra_data).decode("ascii")

        json_obj = {
            "name": "Test",
            "extra_metadata": extra_b64,
        }
        json_bytes = json.dumps(json_obj).encode("utf-8")

        result = hashing.compute_arc3_metadata_hash(json_bytes)
        assert len(result) == 32

        # Verify correct computation
        json_h = hashing.sha512_256(const.ARC3_HASH_AMJ_PREFIX + json_bytes)
        expected = hashing.sha512_256(const.ARC3_HASH_AM_PREFIX + json_h + extra_data)
        assert result == expected

    def test_whitespace_in_json(self) -> None:
        """Test that whitespace in JSON affects hash (as expected)."""
        json1 = json.dumps({"name": "Test"}).encode("utf-8")
        json2 = json.dumps({"name": "Test"}, indent=2).encode("utf-8")

        # Different whitespace should produce different hashes
        result1 = hashing.compute_arc3_metadata_hash(json1)
        result2 = hashing.compute_arc3_metadata_hash(json2)
        assert result1 != result2

    def test_extra_metadata_field_ordering(self) -> None:
        """Test that field ordering in JSON affects hash (as expected)."""
        extra_b64 = base64.b64encode(b"test").decode("ascii")

        # Different field orderings
        json1 = json.dumps({"name": "Test", "extra_metadata": extra_b64}).encode(
            "utf-8"
        )
        json2 = json.dumps({"extra_metadata": extra_b64, "name": "Test"}).encode(
            "utf-8"
        )

        result1 = hashing.compute_arc3_metadata_hash(json1)
        result2 = hashing.compute_arc3_metadata_hash(json2)
        # Different ordering should produce different hashes
        assert result1 != result2
