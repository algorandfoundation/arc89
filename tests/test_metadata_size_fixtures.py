"""Tests demonstrating the use of metadata size fixtures."""

from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata


def test_empty_metadata_fixture(empty_metadata):
    """Test the empty metadata fixture."""
    assert empty_metadata.asset_id == 1
    assert empty_metadata.size == 0
    assert empty_metadata.total_pages == 0
    assert empty_metadata.is_short  # Empty is considered short
    assert empty_metadata.validate_size()

    # Empty metadata should still have valid hash (just header)
    assert len(empty_metadata.metadata_hash) == 32
    assert empty_metadata.metadata_hash != b"\x00" * 32

    # Header should still be 42 bytes
    assert len(empty_metadata.header_bytes) == const.METADATA_HEADER_SIZE

    print(f"✓ Empty metadata: {empty_metadata.size} bytes")


def test_short_metadata_fixture(short_metadata):
    """Test the short metadata fixture."""
    assert short_metadata.asset_id == 2
    assert short_metadata.size > 0
    assert short_metadata.size <= const.SHORT_METADATA_SIZE
    assert short_metadata.is_short
    assert short_metadata.is_arc3
    assert short_metadata.is_arc89_native
    assert short_metadata.validate_size()
    assert short_metadata.validate_json()

    # Short metadata can be operated on directly by AVM
    json_data = short_metadata.to_json()
    assert "name" in json_data
    assert json_data["name"] == "Short Metadata Test"

    # Should have at least 1 page (even if small)
    assert short_metadata.total_pages >= 1

    print(
        f"✓ Short metadata: {short_metadata.size} bytes (≤ {const.SHORT_METADATA_SIZE})"
    )


def test_maxed_metadata_fixture(maxed_metadata):
    """Test the maximum size metadata fixture."""
    assert maxed_metadata.asset_id == 3
    assert maxed_metadata.size == const.MAX_METADATA_SIZE
    assert not maxed_metadata.is_short  # Too large to be short
    assert maxed_metadata.validate_size()

    # Should have maximum number of pages
    expected_pages = (const.MAX_METADATA_SIZE + const.PAGE_SIZE - 1) // const.PAGE_SIZE
    assert maxed_metadata.total_pages == expected_pages
    assert maxed_metadata.total_pages <= const.MAX_PAGES

    # Verify we can get each page
    for page_idx in range(maxed_metadata.total_pages):
        page = maxed_metadata.get_page(page_idx)
        assert len(page) > 0
        # Last page might be partial
        if page_idx < maxed_metadata.total_pages - 1:
            assert len(page) == const.PAGE_SIZE

    # Hash computation should work even for max size
    hash_value = maxed_metadata.compute_metadata_hash()
    assert len(hash_value) == 32
    assert hash_value == maxed_metadata.metadata_hash

    print(
        f"✓ Maxed metadata: {maxed_metadata.size} bytes (= {const.MAX_METADATA_SIZE})"
    )
    print(f"  Pages: {maxed_metadata.total_pages}")


def test_oversized_metadata_fixture(oversized_metadata):
    """Test the oversized metadata fixture."""
    assert oversized_metadata.asset_id == 4
    assert oversized_metadata.size > const.MAX_METADATA_SIZE
    assert not oversized_metadata.is_short
    assert not oversized_metadata.validate_size()  # Should fail validation

    # Should still be able to compute hash (even though invalid)
    hash_value = oversized_metadata.compute_metadata_hash()
    assert len(hash_value) == 32

    # MBR calculation should still work
    mbr_delta = oversized_metadata.get_mbr_delta(old_size=None)
    assert mbr_delta.sign > 0  # Positive for creation
    assert mbr_delta.amount > 0

    print(
        f"✓ Oversized metadata: {oversized_metadata.size} bytes (> {const.MAX_METADATA_SIZE})"
    )
    print(
        f"  Exceeds limit by: {oversized_metadata.size - const.MAX_METADATA_SIZE} bytes"
    )


def test_size_comparison():
    """Test to show the size progression."""
    # Create metadata of various sizes
    sizes = [
        0,
        100,
        1000,
        const.SHORT_METADATA_SIZE,
        const.SHORT_METADATA_SIZE + 1,
        const.MAX_METADATA_SIZE,
    ]

    for size in sizes:
        content = "x" * size
        metadata = AssetMetadata.create(
            asset_id=999, metadata=content.encode("utf-8") if content else b""
        )

        is_short = metadata.is_short
        is_valid = metadata.validate_size()
        pages = metadata.total_pages

        print(f"Size {size:6d}: short={is_short}, valid={is_valid}, pages={pages}")


def test_fixtures_with_smart_contract_operations(
    empty_metadata, short_metadata, maxed_metadata
):
    """
    Example test showing how to use fixtures in smart contract tests.
    This demonstrates the typical workflow for testing metadata creation.
    """

    # Test 1: Empty metadata should be accepted
    assert empty_metadata.validate_size()
    empty_box_value = empty_metadata.box_value
    assert len(empty_box_value) == const.METADATA_HEADER_SIZE  # Header only

    # Test 2: Short metadata is optimal for AVM operations
    if short_metadata.is_short:
        # Smart contract can operate directly on this metadata
        short_box_value = short_metadata.box_value
        assert (
            len(short_box_value)
            <= const.METADATA_HEADER_SIZE + const.SHORT_METADATA_SIZE
        )

    # Test 3: Maxed metadata tests the upper limit
    assert maxed_metadata.size == const.MAX_METADATA_SIZE
    maxed_box_value = maxed_metadata.box_value
    assert len(maxed_box_value) == const.METADATA_HEADER_SIZE + const.MAX_METADATA_SIZE

    # All should have valid hashes
    for metadata in [empty_metadata, short_metadata, maxed_metadata]:
        assert len(metadata.metadata_hash) == 32
        assert metadata.metadata_hash != b"\x00" * 32


def test_mbr_calculations_for_different_sizes(
    empty_metadata, short_metadata, maxed_metadata
):
    """Test MBR calculations for different metadata sizes."""

    # Calculate MBR for each size
    sizes_and_metadata = [
        ("empty", empty_metadata),
        ("short", short_metadata),
        ("maxed", maxed_metadata),
    ]

    for label, metadata in sizes_and_metadata:
        mbr_delta = metadata.get_mbr_delta(old_size=None)

        # All should require positive MBR for creation
        assert mbr_delta.sign > 0
        assert mbr_delta.amount > 0

        print(
            f"{label:6s} metadata MBR: {mbr_delta.amount:8d} microALGO ({mbr_delta.amount/1_000_000:.6f} ALGO)"
        )

    # Maxed should require the most MBR
    empty_delta = empty_metadata.get_mbr_delta(old_size=None)
    short_delta = short_metadata.get_mbr_delta(old_size=None)
    maxed_delta = maxed_metadata.get_mbr_delta(old_size=None)

    assert empty_delta.amount < short_delta.amount < maxed_delta.amount


def test_pagination_across_sizes(empty_metadata, short_metadata, maxed_metadata):
    """Test pagination behavior for different sizes."""

    # Empty: no pages
    assert empty_metadata.total_pages == 0

    # Short: should have 1 page (or maybe 2 depending on exact size)
    assert short_metadata.total_pages >= 1
    if short_metadata.size <= const.PAGE_SIZE:
        assert short_metadata.total_pages == 1

    # Maxed: should have many pages
    assert maxed_metadata.total_pages > 1
    assert maxed_metadata.total_pages <= const.MAX_PAGES

    # Verify each metadata's pages
    for metadata in [short_metadata, maxed_metadata]:
        total_content_size = 0
        for page_idx in range(metadata.total_pages):
            page = metadata.get_page(page_idx)
            total_content_size += len(page)

            # Each page except last should be full
            if page_idx < metadata.total_pages - 1:
                assert len(page) == const.PAGE_SIZE

        # Total should match metadata size
        assert total_content_size == metadata.size

        print(
            f"{metadata.asset_id}: {metadata.total_pages} pages, {total_content_size} bytes total"
        )
