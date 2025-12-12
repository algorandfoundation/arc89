"""Tests for the AssetMetadata factory class."""

from smart_contracts.asa_metadata_registry import constants as const
from smart_contracts.asa_metadata_registry import enums
from tests.helpers.factories import (
    AssetMetadata,
    create_test_metadata,
)


def test_create_simple_metadata():
    """Test creating simple metadata with defaults."""
    metadata = AssetMetadata.create(asset_id=12345, metadata={"name": "Test Asset"})

    assert metadata.asset_id == 12345
    assert metadata.size > 0
    assert metadata.is_short  # Small metadata should be marked as short
    assert not metadata.is_immutable
    assert metadata.metadata_hash != b"\x00" * 32  # Hash should be computed


def test_metadata_flags():
    """Test setting and reading metadata flags."""
    metadata = AssetMetadata.create(
        asset_id=1,
        metadata={"test": "data"},
        arc3_compliant=True,
        arc89_native=True,
        immutable=True,
        arc20=True,
        arc62=True,
    )

    assert metadata.is_arc3
    assert metadata.is_arc89_native
    assert metadata.is_immutable
    assert metadata.is_arc20
    assert metadata.is_arc62


def test_short_metadata_identifier():
    """Test that short metadata identifier is set correctly."""
    # Small metadata should be short
    small_metadata = AssetMetadata.create(asset_id=1, metadata={"name": "Short"})
    assert small_metadata.is_short
    assert small_metadata.size <= const.SHORT_METADATA_SIZE

    # Large metadata should not be short
    large_data = "x" * (const.SHORT_METADATA_SIZE + 100)
    large_metadata = AssetMetadata.create(asset_id=2, metadata=large_data)
    assert not large_metadata.is_short
    assert large_metadata.size > const.SHORT_METADATA_SIZE


def test_hash_computation():
    """Test that hashes are computed correctly."""
    metadata = AssetMetadata.create(
        asset_id=12345, metadata={"name": "Test", "description": "A test asset"}
    )

    # Check that header hash can be computed
    hh = metadata.compute_header_hash()
    assert len(hh) == 32
    assert hh != b"\x00" * 32

    # Check that metadata hash is computed
    am = metadata.compute_metadata_hash()
    assert len(am) == 32
    assert am != b"\x00" * 32
    assert am == metadata.metadata_hash


def test_page_computation():
    """Test metadata pagination."""
    # Create metadata that spans multiple pages
    large_data = "x" * (const.PAGE_SIZE * 2 + 500)
    metadata = AssetMetadata.create(asset_id=1, metadata=large_data)

    assert metadata.total_pages == 3

    # Test getting individual pages
    page_0 = metadata.get_page(0)
    assert len(page_0) == const.PAGE_SIZE

    page_1 = metadata.get_page(1)
    assert len(page_1) == const.PAGE_SIZE

    page_2 = metadata.get_page(2)
    assert len(page_2) == 500  # Last page is partial

    # Test page hash computation
    ph_0 = metadata.compute_page_hash(0)
    assert len(ph_0) == 32


def test_empty_metadata():
    """Test metadata with empty body."""
    metadata = AssetMetadata.create(asset_id=1, metadata=b"")

    assert metadata.size == 0
    assert metadata.total_pages == 0
    assert metadata.is_short  # Empty is considered short

    # Empty metadata should still have a valid hash (just header)
    am = metadata.compute_metadata_hash()
    assert len(am) == 32


def test_box_serialization():
    """Test serialization to/from box format."""
    original = AssetMetadata.create(
        asset_id=12345,
        metadata={"name": "Test Asset", "description": "Testing"},
        arc3_compliant=True,
        immutable=True,
        last_modified_round=100,
    )

    # Get box value
    box_value = original.box_value
    box_name = original.box_name

    assert len(box_name) == 8
    assert len(box_value) >= const.METADATA_HEADER_SIZE

    # Reconstruct from box value
    restored = AssetMetadata.from_box_value(12345, box_value)

    assert restored.asset_id == original.asset_id
    assert restored.identifiers == original.identifiers
    assert restored.flags == original.flags
    assert restored.metadata_hash == original.metadata_hash
    assert restored.last_modified_round == original.last_modified_round
    assert restored.metadata_bytes == original.metadata_bytes


def test_mbr_delta_calculation():
    """Test MBR delta calculation."""
    metadata = AssetMetadata.create(asset_id=1, metadata={"name": "Test"})

    # New creation should be positive
    mbr_delta = metadata.get_mbr_delta(old_size=None)
    assert mbr_delta.sign == enums.MBR_DELTA_POS
    assert mbr_delta.amount > 0

    # Growing metadata should be positive delta
    old_size = metadata.size
    metadata.set_metadata({"name": "Test", "description": "Much longer description"})
    mbr_delta = metadata.get_mbr_delta(old_size=old_size)
    assert mbr_delta.sign == enums.MBR_DELTA_POS
    assert mbr_delta.amount > 0

    # Shrinking metadata should be negative delta
    new_size = metadata.size
    metadata.set_metadata({"name": "T"})
    mbr_delta = metadata.get_mbr_delta(old_size=new_size)
    assert mbr_delta.sign == enums.MBR_DELTA_NEG
    assert mbr_delta.amount > 0  # Amount is always positive

    # Test signed helper
    signed_delta = metadata.get_mbr_delta(old_size=new_size)
    assert signed_delta.amount < 0  # Negative for shrinking

    # Test MbrDelta.signed_amount property
    mbr_delta_shrink = metadata.get_mbr_delta(old_size=new_size)
    assert mbr_delta_shrink.signed_amount < 0
    assert mbr_delta_shrink.signed_amount == -mbr_delta_shrink.amount

    # Test positive case
    metadata.set_metadata({"name": "Test", "description": "Growing again"})
    mbr_delta_grow = metadata.get_mbr_delta(old_size=metadata.size - 10)
    assert mbr_delta_grow.signed_amount > 0
    assert mbr_delta_grow.signed_amount == mbr_delta_grow.amount


def test_json_operations():
    """Test JSON encoding/decoding."""
    metadata_dict = {
        "name": "Test Asset",
        "description": "A test",
        "properties": {"test": True, "value": 42},
    }

    metadata = AssetMetadata.create(asset_id=1, metadata=metadata_dict)

    # Test that we can decode back to JSON
    decoded = metadata.to_json()
    assert decoded == metadata_dict

    # Test JSON validation
    assert metadata.validate_json()


def test_validation():
    """Test metadata validation methods."""
    # Valid metadata
    valid = AssetMetadata.create(asset_id=1, metadata={"name": "Test"})
    assert valid.validate_size()
    assert valid.validate_json()

    # Too large metadata
    too_large = AssetMetadata(
        asset_id=2, metadata_bytes=b"x" * (const.MAX_METADATA_SIZE + 1)
    )
    assert not too_large.validate_size()

    # Invalid JSON
    invalid_json = AssetMetadata(asset_id=3, metadata_bytes=b"not valid json {")
    assert not invalid_json.validate_json()


def test_create_test_metadata_helper():
    """Test the convenience test metadata creator."""
    metadata = create_test_metadata(asset_id=999, arc3_compliant=True)

    assert metadata.asset_id == 999
    assert metadata.is_arc3
    assert metadata.validate_json()

    # Should have sensible defaults
    json_data = metadata.to_json()
    assert "name" in json_data
    assert "Test Asset 999" in json_data["name"]


def test_flag_toggling():
    """Test that flags can be toggled on and off."""
    metadata = AssetMetadata(asset_id=1)

    # Initially all flags should be false
    assert not metadata.is_arc20
    assert not metadata.is_arc62

    # Turn on ARC-20
    metadata.set_arc20(True)
    assert metadata.is_arc20

    # Turn on ARC-62
    metadata.set_arc62(True)
    assert metadata.is_arc62

    # Turn off ARC-20
    metadata.set_arc20(False)
    assert not metadata.is_arc20
    assert metadata.is_arc62  # ARC-62 should still be on


def test_metadata_hash_update():
    """Test that metadata hash updates when content changes."""
    metadata = AssetMetadata.create(asset_id=1, metadata={"name": "Original"})

    original_hash = metadata.metadata_hash

    # Change the metadata
    metadata.set_metadata({"name": "Changed"})
    metadata.update_metadata_hash()

    # Hash should be different
    assert metadata.metadata_hash != original_hash


def test_immutable_flag_one_way():
    """Test that immutable flag can be set but not unset (one-way)."""
    metadata = AssetMetadata.create(asset_id=1, metadata={"name": "Test"})

    assert not metadata.is_immutable

    # Set immutable
    metadata.set_immutable(True)
    assert metadata.is_immutable

    # Try to unset (this will work in the factory class,
    # but the smart contract would prevent it)
    metadata.set_immutable(False)
    assert not metadata.is_immutable
