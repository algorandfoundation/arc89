"""Factory helpers for creating test fixtures for ASA Metadata Registry tests."""

from asa_metadata_registry import AssetMetadata, MetadataFlags, hashing
from asa_metadata_registry import constants as const


def create_arc3_payload(
    name: str,
    description: str = "",
    image: str = "",
    external_url: str = "",
    properties: dict[str, object] | None = None,
) -> dict[str, object]:
    """
    Create an ARC-3 compliant metadata dictionary.

    Args:
        name: Asset name
        description: Asset description
        image: URL to asset image
        external_url: URL to external website
        properties: Additional properties

    Returns:
        ARC-3 compliant metadata dict
    """
    metadata: dict[str, str | dict[str, object]] = {
        "name": name,
    }

    if description:
        metadata["description"] = description
    if image:
        metadata["image"] = image
    if external_url:
        metadata["external_url"] = external_url
    if properties:
        metadata["properties"] = properties

    return metadata  # type: ignore[return-value]


def compute_arc3_metadata_hash(json_bytes: bytes) -> bytes:
    return hashing.compute_arc3_metadata_hash(json_bytes)


def create_test_metadata(
    asset_id: int,
    *,
    metadata_content: dict[str, object] | None = None,
    flags: MetadataFlags | None = None,
    deprecated_by: int = 0,
    arc3_compliant: bool = False,
) -> AssetMetadata:
    """
    Convenience function to create test metadata with sensible defaults.

    Args:
        asset_id: The asset ID
        metadata_content: Optional metadata dict (defaults to simple ARC-3 metadata)
        flags: Optional metadata flags
        deprecated_by: Optional deprecated_by asset ID
        arc3_compliant: Whether to validate ARC-3 compliance

    Returns:
        AssetMetadata instance
    """
    if metadata_content is None:
        metadata_content = create_arc3_payload(
            name=f"Test Asset {asset_id}",
            description="Test asset metadata",
        )

    return AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=metadata_content,
        flags=flags,
        deprecated_by=deprecated_by,
        arc3_compliant=arc3_compliant,
    )


def create_metadata_with_page_count(
    asset_id: int, page_count: int, filler: bytes
) -> AssetMetadata:
    if page_count < 0 or page_count > const.MAX_PAGES:
        raise ValueError(f"page_count must be between 0 and {const.MAX_PAGES}")

    if page_count == 0:
        # Empty metadata
        size = 0
    elif page_count == 1:
        size = 1 * const.PAGE_SIZE
    else:
        # Minimum size to trigger N pages: (N-1) * PAGE_SIZE + 1
        size = (page_count - 1) * const.PAGE_SIZE + 1

    # Create metadata with the filler bytes repeated to the desired size
    assert len(filler) >= 1, "Filler must be at least 1 byte"
    metadata_bytes = filler * size

    metadata = AssetMetadata.from_bytes(
        asset_id=asset_id,
        metadata_bytes=metadata_bytes,
    )
    assert (
        metadata.body.total_pages() == page_count
    ), f"Expected {page_count} pages, got {metadata.body.total_pages()}"

    return metadata
