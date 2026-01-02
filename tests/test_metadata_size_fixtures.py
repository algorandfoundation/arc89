"""Tests demonstrating the use of metadata size fixtures."""

from src import constants as const
from tests.helpers.factories import AssetMetadata


def test_empty_metadata_fixture(arc_89_asa: int, empty_metadata: AssetMetadata) -> None:
    """Test the empty metadata fixture."""
    assert empty_metadata.asset_id == arc_89_asa
    assert empty_metadata.size == 0
    assert empty_metadata.body.total_pages() == 0
    assert empty_metadata.is_short  # Empty is considered short
    empty_metadata.body.validate_size()  # Should not raise

    # Empty metadata should still have valid hash (just header)
    assert len(empty_metadata.compute_metadata_hash()) == 32
    assert empty_metadata.compute_metadata_hash() != b"\x00" * 32

    print(f"✓ Empty metadata: {empty_metadata.size} bytes")


def test_short_metadata_fixture(arc_89_asa: int, short_metadata: AssetMetadata) -> None:
    """Test the short metadata fixture."""
    assert short_metadata.asset_id == arc_89_asa
    assert short_metadata.size > 0
    assert short_metadata.size <= const.SHORT_METADATA_SIZE
    assert short_metadata.is_short
    short_metadata.body.validate_size()  # Should not raise

    # Short metadata can be operated on directly by AVM
    json_data = short_metadata.body.json
    assert "name" in json_data
    assert json_data["name"] == "Silvio"

    # Should have at least 1 page (even if small)
    assert short_metadata.body.total_pages() >= 1

    print(
        f"✓ Short metadata: {short_metadata.size} bytes (≤ {const.SHORT_METADATA_SIZE})"
    )


def test_maxed_metadata_fixture(arc_89_asa: int, maxed_metadata: AssetMetadata) -> None:
    """Test the maximum size metadata fixture."""
    assert maxed_metadata.asset_id == arc_89_asa
    assert maxed_metadata.size == const.MAX_METADATA_SIZE
    assert not maxed_metadata.is_short  # Too large to be short
    maxed_metadata.body.validate_size()  # Should not raise

    # Should have maximum number of pages
    expected_pages = (const.MAX_METADATA_SIZE + const.PAGE_SIZE - 1) // const.PAGE_SIZE
    assert maxed_metadata.body.total_pages() == expected_pages
    assert maxed_metadata.body.total_pages() <= const.MAX_PAGES

    # Verify we can get each page
    for page_idx in range(maxed_metadata.body.total_pages()):
        page = maxed_metadata.body.get_page(page_idx)
        assert len(page) > 0
        # Last page might be partial
        if page_idx < maxed_metadata.body.total_pages() - 1:
            assert len(page) == const.PAGE_SIZE

    # Hash computation should work even for max size
    hash_value = maxed_metadata.compute_metadata_hash()
    assert len(hash_value) == 32
    assert hash_value == maxed_metadata.compute_metadata_hash()

    print(
        f"✓ Maxed metadata: {maxed_metadata.size} bytes (= {const.MAX_METADATA_SIZE})"
    )
    print(f"  Pages: {maxed_metadata.body.total_pages()}")


def test_oversized_metadata_fixture(
    arc_89_asa: int, oversized_metadata: AssetMetadata
) -> None:
    """Test the oversized metadata fixture."""
    assert oversized_metadata.asset_id == arc_89_asa
    assert oversized_metadata.size > const.MAX_METADATA_SIZE
    assert not oversized_metadata.is_short

    try:
        oversized_metadata.body.validate_size()
        raise AssertionError("Expected validate_size to raise ValueError")
    except ValueError as e:
        assert "exceeds max" in str(e).lower()

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


def test_size_comparison() -> None:
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
        metadata = AssetMetadata.from_bytes(
            asset_id=999,
            metadata_bytes=content.encode("utf-8") if content else b"",
            validate_json_object=False,  # Skip JSON validation for this test
        )

        is_short = metadata.is_short
        pages = metadata.body.total_pages()

        print(f"Size {size:6d}: short={is_short}, pages={pages}")


def test_mbr_calculations_for_different_sizes(
    empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
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

        print(f"{label:6s} metadata MBR: {mbr_delta.amount} microALGO")

    # Maxed should require the most MBR
    empty_delta = empty_metadata.get_mbr_delta(old_size=None)
    short_delta = short_metadata.get_mbr_delta(old_size=None)
    maxed_delta = maxed_metadata.get_mbr_delta(old_size=None)

    assert empty_delta.amount < short_delta.amount < maxed_delta.amount


def test_pagination_across_sizes(
    empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    """Test pagination behavior for different sizes."""

    # Empty: no pages
    assert empty_metadata.body.total_pages() == 0

    # Short: should have 1 page (or maybe 2 depending on exact size)
    assert short_metadata.body.total_pages() >= 1
    if short_metadata.size <= const.PAGE_SIZE:
        assert short_metadata.body.total_pages() == 1

    # Maxed: should have many pages
    assert maxed_metadata.body.total_pages() > 1
    assert maxed_metadata.body.total_pages() <= const.MAX_PAGES

    # Verify each metadata's pages
    for metadata in [short_metadata, maxed_metadata]:
        total_content_size = 0
        for page_idx in range(metadata.body.total_pages()):
            page = metadata.body.get_page(page_idx)
            total_content_size += len(page)

            # Each page except last should be full
            if page_idx < metadata.body.total_pages() - 1:
                assert len(page) == const.PAGE_SIZE

        # Total should match metadata size
        assert total_content_size == metadata.size

        print(
            f"{metadata.asset_id}: {metadata.body.total_pages()} pages, {total_content_size} bytes total"
        )
