"""Factory helpers for creating test fixtures for ASA Metadata Registry tests."""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from algokit_utils import AlgoAmount

from smart_contracts.asa_metadata_registry import constants as const
from smart_contracts.asa_metadata_registry import enums

from . import bitmasks


@dataclass
class MbrDelta:
    """
    Simple Python representation of MBR Delta for testing.
    Mimics the ARC-89 MbrDelta ABI type but uses native Python types.
    """

    sign: int  # Enum: MBR_DELTA_NULL (0), MBR_DELTA_POS (1), or MBR_DELTA_NEG (255)
    amount: AlgoAmount  # MBR amount in microALGO (always positive)

    @property
    def signed_amount(self) -> int:
        """
        Get the MBR delta (in microALGO) as a signed integer.

        Returns:
            Positive int for growth (POS)
            Negative int for shrink (NEG)
            Zero for no change (NULL)
        """
        if self.sign == enums.MBR_DELTA_POS:
            return self.amount.micro_algo
        elif self.sign == enums.MBR_DELTA_NEG:
            return -self.amount.micro_algo
        else:  # MBR_DELTA_NULL
            return 0


@dataclass
class AssetMetadata:
    """
    Represents an Asset Metadata Box for testing purposes.

    This class implements the ARC-89 specification for Asset Metadata,
    including all header fields, metadata body, hash computation, and
    ARC compliance checks.
    """

    # Asset context
    asset_id: int

    # Header fields
    identifiers: int = 0
    reversible_flags: int = 0
    irreversible_flags: int = 0
    metadata_hash: bytes = field(default_factory=lambda: b"\x00" * 32)
    last_modified_round: int = 0
    deprecated_by: int = 0

    # Body
    metadata_bytes: bytes = b""

    def __post_init__(self):
        """Initialize computed fields after dataclass initialization."""
        # Auto-set short metadata identifier based on size
        self._update_short_identifier()

    # ==================== GETTERS ====================

    @property
    def size(self) -> int:
        """Get the size of the metadata in bytes."""
        return len(self.metadata_bytes)

    @property
    def is_short(self) -> bool:
        """Check if metadata is identified as short."""
        return (self.identifiers & bitmasks.MASK_ID_SHORT) != 0

    @property
    def is_arc20(self) -> bool:
        """Check if ASA is declared as ARC-20 Smart ASA."""
        return (self.reversible_flags & bitmasks.MASK_REV_ARC20) != 0

    @property
    def is_arc62(self) -> bool:
        """Check if ARC-62 Circulating Supply is enabled."""
        return (self.reversible_flags & bitmasks.MASK_REV_ARC62) != 0

    @property
    def is_arc3(self) -> bool:
        """Check if metadata is ARC-3 compliant."""
        return (self.irreversible_flags & bitmasks.MASK_IRR_ARC3) != 0

    @property
    def is_arc89_native(self) -> bool:
        """Check if ASA is ARC-89 native."""
        return (self.irreversible_flags & bitmasks.MASK_IRR_ARC89_NATIVE) != 0

    @property
    def is_immutable(self) -> bool:
        """Check if metadata is immutable."""
        return (self.irreversible_flags & bitmasks.MASK_IRR_IMMUTABLE) != 0

    @property
    def total_pages(self) -> int:
        """Calculate the total number of pages for the metadata."""
        if self.size == 0:
            return 0
        return (self.size + const.PAGE_SIZE - 1) // const.PAGE_SIZE

    @property
    def header_bytes(self) -> bytes:
        """Get the complete metadata header as bytes."""
        return (
            self.identifiers.to_bytes(1, "big")
            + self.reversible_flags.to_bytes(1, "big")
            + self.irreversible_flags.to_bytes(1, "big")
            + self.metadata_hash
            + self.last_modified_round.to_bytes(8, "big")
            + self.deprecated_by.to_bytes(8, "big")
        )

    @property
    def box_value(self) -> bytes:
        """Get the complete Asset Metadata Box value (header + body)."""
        return self.header_bytes + self.metadata_bytes

    @property
    def box_name(self) -> bytes:
        """Get the Asset Metadata Box name (8-byte big-endian asset ID)."""
        return self.asset_id.to_bytes(const.ASSET_METADATA_BOX_KEY_SIZE, "big")

    # ==================== SETTERS ====================

    def set_metadata(self, metadata: bytes | str | dict) -> None:
        """
        Set the metadata bytes and update computed fields.

        Args:
            metadata: Either raw bytes, a JSON string, or a dict that will be encoded
        """
        if isinstance(metadata, str):
            self.metadata_bytes = metadata.encode("utf-8")
        elif isinstance(metadata, dict):
            self.metadata_bytes = json.dumps(metadata, separators=(",", ":")).encode(
                "utf-8"
            )
        else:
            self.metadata_bytes = metadata

        self._update_short_identifier()

    def set_reversible_flag(self, *, flag_mask: int, value: bool) -> None:
        """
        Set a specific reversible flag bit.

        Args:
            flag_mask: The bitmask for the reversible flag to set
            value: True to set the bit, False to clear it
        """
        if value:
            self.reversible_flags |= flag_mask
        else:
            self.reversible_flags &= ~flag_mask

    def set_irreversible_flag(self, *, flag_mask: int, value: bool = True) -> None:
        """
        Set a specific irreversible flag bit.

        Args:
            flag_mask: The bitmask for the irreversible flag to set
            value: True to set the bit, False to clear it (default: True)

        Note:
            In practice, irreversible flags should only be set to True,
            but this factory class allows clearing for testing purposes.
        """
        if value:
            self.irreversible_flags |= flag_mask
        else:
            self.irreversible_flags &= ~flag_mask

    def set_arc20(self, *, value: bool) -> None:
        """Set the ARC-20 Smart ASA flag."""
        self.set_reversible_flag(flag_mask=bitmasks.MASK_REV_ARC20, value=value)

    def set_arc62(self, *, value: bool) -> None:
        """Set the ARC-62 Circulating Supply flag."""
        self.set_reversible_flag(flag_mask=bitmasks.MASK_REV_ARC62, value=value)

    def set_arc3(self, *, value: bool) -> None:
        """Set the ARC-3 compliant flag."""
        self.set_irreversible_flag(flag_mask=bitmasks.MASK_IRR_ARC3, value=value)

    def set_arc89_native(self, *, value: bool) -> None:
        """Set the ARC-89 native ASA flag."""
        self.set_irreversible_flag(flag_mask=bitmasks.MASK_IRR_ARC89_NATIVE, value=value)

    def set_immutable(self, *, value: bool) -> None:
        """Set the metadata immutability flag."""
        self.set_irreversible_flag(flag_mask=bitmasks.MASK_IRR_IMMUTABLE, value=value)

    # ==================== HASH COMPUTATION ====================

    def compute_header_hash(self) -> bytes:
        """
        Compute the Metadata Header Hash (hh) according to ARC-89.

        Formula:
        hh = SHA-512/256("arc0089/header" || Asset ID || Metadata Identifiers ||
                         Reversible Flags || Irreversible Flags || Metadata Size)

        Returns:
            32-byte header hash
        """
        domain = const.HASH_DOMAIN_HEADER
        asset_id_bytes = self.asset_id.to_bytes(const.UINT64_SIZE, "big")
        identifiers = self.identifiers.to_bytes(const.BYTE_SIZE, "big")
        rev_flags = self.reversible_flags.to_bytes(const.BYTE_SIZE, "big")
        irr_flags = self.irreversible_flags.to_bytes(const.BYTE_SIZE, "big")
        size = self.size.to_bytes(const.UINT16_SIZE, "big")

        preimage = domain + asset_id_bytes + identifiers + rev_flags + irr_flags + size
        return hashlib.new("sha512_256", preimage).digest()

    def compute_page_hash(self, page_index: int) -> bytes:
        """
        Compute the Page Hash (ph[i]) for a specific page according to ARC-89.

        Formula:
        ph[i] = SHA-512/256("arc0089/page" || Asset ID || Page Index ||
                            Page Size || Page Content)

        Args:
            page_index: 0-based page index

        Returns:
            32-byte page hash
        """
        if page_index >= self.total_pages:
            raise ValueError(
                f"Page index {page_index} out of range (total pages: {self.total_pages})"
            )

        domain = const.HASH_DOMAIN_PAGE
        asset_id_bytes = self.asset_id.to_bytes(const.UINT64_SIZE, "big")
        page_index_byte = page_index.to_bytes(const.UINT8_SIZE, "big")

        # Get page content
        start = page_index * const.PAGE_SIZE
        end = min(start + const.PAGE_SIZE, self.size)
        page_content = self.metadata_bytes[start:end]
        page_size = len(page_content)
        page_size_bytes = page_size.to_bytes(const.UINT16_SIZE, "big")

        preimage = (
            domain + asset_id_bytes + page_index_byte + page_size_bytes + page_content
        )
        return hashlib.new("sha512_256", preimage).digest()

    def compute_metadata_hash(self) -> bytes:
        """
        Compute the complete Asset Metadata Hash (am) according to ARC-89.

        Formula:
        - If total_pages > 0:
          am = SHA-512/256("arc0089/am" || hh || ph[0] || ph[1] || ... || ph[n-1])
        - If total_pages == 0:
          am = SHA-512/256("arc0089/am" || hh)

        Returns:
            32-byte metadata hash
        """
        domain = const.HASH_DOMAIN_METADATA
        hh = self.compute_header_hash()

        # Start with domain and header hash
        preimage = domain + hh

        # Append all page hashes if pages exist
        for i in range(self.total_pages):
            ph = self.compute_page_hash(i)
            preimage += ph

        return hashlib.new("sha512_256", preimage).digest()

    def update_metadata_hash(self) -> None:
        """Recompute and update the stored metadata hash."""
        self.metadata_hash = self.compute_metadata_hash()

    # ==================== UTILITIES ====================

    def _update_short_identifier(self) -> None:
        """Update the short metadata identifier based on current metadata size."""
        if self.size <= const.SHORT_METADATA_SIZE:
            self.identifiers |= bitmasks.MASK_ID_SHORT
        else:
            self.identifiers &= ~bitmasks.MASK_ID_SHORT

    def chunked_payload(self) -> list[bytes]:
        """
        Get the metadata payload split into chunks for ARC-89 transmission.

        Returns:
            List of byte chunks
        """
        return AssetMetadata.chunk_payload(self.metadata_bytes)

    def get_page(self, page_index: int) -> bytes:
        """
        Get the content of a specific page.

        Args:
            page_index: 0-based page index

        Returns:
            Page content bytes (may be less than PAGE_SIZE for the last page)
        """
        if page_index >= self.total_pages:
            raise ValueError(
                f"Page index {page_index} out of range (total pages: {self.total_pages})"
            )

        start = page_index * const.PAGE_SIZE
        end = min(start + const.PAGE_SIZE, self.size)
        return self.metadata_bytes[start:end]

    def get_mbr_delta(
        self, old_size: int | None = None, *, delete: bool = False
    ) -> MbrDelta:
        """
        Calculate the MBR delta for this metadata by comparing old and new states.

        - Creation: old_size is None, delete is False -> +full box MBR
        - Update: old_size is provided, delete is False -> +/- difference
        - Deletion: old_size is provided, delete is True -> -full box MBR
        """

        def box_mbr(metadata_body_size: int) -> int:
            # FLAT_MBR + BYTE_MBR * (box_name_size + box_value_size)
            return const.FLAT_MBR + const.BYTE_MBR * (
                const.ASSET_METADATA_BOX_KEY_SIZE
                + const.HEADER_SIZE
                + metadata_body_size
            )

        if delete:
            delta = -box_mbr(self.size)
        else:
            old_mbr = 0 if old_size is None else box_mbr(old_size)
            new_mbr = box_mbr(self.size)
            delta = new_mbr - old_mbr

        if delta > 0:
            return MbrDelta(
                sign=enums.MBR_DELTA_POS, amount=AlgoAmount(micro_algo=delta)
            )
        if delta < 0:
            return MbrDelta(
                sign=enums.MBR_DELTA_NEG,
                amount=AlgoAmount(micro_algo=abs(delta)),  # Always positive
            )
        return MbrDelta(sign=enums.MBR_DELTA_NULL, amount=AlgoAmount(micro_algo=0))

    def to_json(self) -> dict:
        """
        Convert metadata bytes to a JSON dict (if valid JSON).

        Returns:
            Parsed JSON dict

        Raises:
            json.JSONDecodeError: If metadata is not valid JSON
        """
        return json.loads(self.metadata_bytes.decode("utf-8"))

    def validate_size(self) -> bool:
        """
        Validate that the metadata size is within limits.

        Returns:
            True if size is valid, False otherwise
        """
        return self.size <= const.MAX_METADATA_SIZE

    def validate_json(self) -> bool:
        """
        Validate that the metadata is valid UTF-8 encoded JSON.

        Returns:
            True if valid JSON, False otherwise
        """
        try:
            json.loads(self.metadata_bytes.decode("utf-8"))
            return True
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

    # ==================== VISUALIZATION ====================

    def print_header(self) -> None:
        print(f"Identifiers: {self.identifiers:08b}")
        print(f"Reversible Flags: {self.reversible_flags:08b}")
        print(f"Irreversible Flags: {self.irreversible_flags:08b}")
        print(f"Metadata Hash: {self.metadata_hash.hex()}")
        print(f"Last Modified Round: {self.last_modified_round}")
        print(f"Deprecated By: {self.deprecated_by}")

    def print_metadata(self) -> None:
        try:
            obj = json.loads(self.metadata_bytes.decode("utf-8"))
            print(json.dumps(obj, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, UnicodeDecodeError):
            print("⚠️ Invalid JSON:")
            print(self.metadata_bytes.decode("utf-8", errors="replace"))

    @classmethod
    def chunk_payload(cls, payload: bytes) -> list[bytes]:
        """
        Split payload into chunks:
        - First chunk: up to FIRST_PAYLOAD_MAX_SIZE.
        - Subsequent chunks: up to OTHER_PAYLOAD_MAX_SIZE.
        """
        if payload == b"":
            return [b""]

        chunks: list[bytes] = []
        # First chunk
        first = payload[: const.FIRST_PAYLOAD_MAX_SIZE]
        chunks.append(first)

        # Remaining chunks
        remaining = payload[len(first) :]
        if remaining:
            for i in range(0, len(remaining), const.EXTRA_PAYLOAD_MAX_SIZE):
                chunks.append(remaining[i : i + const.EXTRA_PAYLOAD_MAX_SIZE])

        return chunks

    @classmethod
    def from_box_value(cls, asset_id: int, box_value: bytes) -> "AssetMetadata":
        """
        Create an AssetMetadata instance from a box value.

        Args:
            asset_id: The asset ID
            box_value: The complete box value (header + body)

        Returns:
            AssetMetadata instance
        """
        if len(box_value) < const.HEADER_SIZE:
            raise ValueError("Box value too short for header")

        # Parse header
        identifiers = box_value[const.IDX_METADATA_IDENTIFIERS]
        rev_flags = box_value[const.IDX_REVERSIBLE_FLAGS]
        irr_flags = box_value[const.IDX_IRREVERSIBLE_FLAGS]
        metadata_hash = box_value[
            const.IDX_METADATA_HASH : const.IDX_METADATA_HASH + const.METADATA_HASH_SIZE
        ]
        last_modified_round = int.from_bytes(
            box_value[
                const.IDX_LAST_MODIFIED_ROUND : const.IDX_LAST_MODIFIED_ROUND
                + const.LAST_MODIFIED_ROUND_SIZE
            ],
            "big",
        )
        deprecated_by = int.from_bytes(
            box_value[
                const.IDX_DEPRECATED_BY: const.IDX_DEPRECATED_BY
                + const.DEPRECATED_BY_SIZE
            ],
            "big",
        )

        # Parse body
        metadata_bytes = box_value[const.IDX_METADATA :]

        return cls(
            asset_id=asset_id,
            identifiers=identifiers,
            reversible_flags=rev_flags,
            irreversible_flags=irr_flags,
            metadata_hash=metadata_hash,
            last_modified_round=last_modified_round,
            metadata_bytes=metadata_bytes,
            deprecated_by=deprecated_by,
        )

    @classmethod
    def create(
        cls,
        *,
        asset_id: int,
        metadata: bytes | str | dict,
        immutable: bool = False,
        arc3_compliant: bool = False,
        arc89_native: bool = False,
        arc20: bool = False,
        arc62: bool = False,
        last_modified_round: int = 0,
    ) -> "AssetMetadata":
        """
        Factory method to create an AssetMetadata instance with common parameters.

        Args:
            asset_id: The asset ID
            metadata: Metadata as bytes, string, or dict
            immutable: Set immutable flag
            arc3_compliant: Set ARC-3 compliant flag
            arc89_native: Set ARC-89 native flag
            arc20: Set ARC-20 Smart ASA flag
            arc62: Set ARC-62 flag
            last_modified_round: Last modified round number

        Returns:
            AssetMetadata instance with hash computed
        """
        instance = cls(
            asset_id=asset_id, last_modified_round=last_modified_round
        )

        # Set metadata (this will auto-update short identifier)
        instance.set_metadata(metadata)

        # Set individual flags
        if immutable:
            instance.set_immutable(value=True)
        if arc3_compliant:
            instance.set_arc3(value=True)
        if arc89_native:
            instance.set_arc89_native(value=True)
        if arc20:
            instance.set_arc20(value=True)
        if arc62:
            instance.set_arc62(value=True)

        # Compute and set the metadata hash
        instance.update_metadata_hash()

        return instance


def create_arc3_metadata(
    name: str,
    description: str = "",
    image: str = "",
    external_url: str = "",
    properties: dict | None = None,
) -> dict:
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
    metadata: dict[str, Any] = {
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

    return metadata


def create_test_metadata(
    asset_id: int, metadata_content: dict | None = None, **kwargs: Any
) -> AssetMetadata:
    """
    Convenience function to create test metadata with sensible defaults.

    Args:
        asset_id: The asset ID
        metadata_content: Optional metadata dict (defaults to simple ARC-3 metadata)
        **kwargs: Additional arguments passed to AssetMetadata.create()

    Returns:
        AssetMetadata instance
    """
    if metadata_content is None:
        metadata_content = create_arc3_metadata(
            name=f"Test Asset {asset_id}",
            description="Test asset metadata",
        )

    return AssetMetadata.create(asset_id=asset_id, metadata=metadata_content, **kwargs)


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

    metadata = AssetMetadata.create(
        asset_id=asset_id,
        metadata=metadata_bytes,
    )
    assert (
        metadata.total_pages == page_count
    ), f"Expected {page_count} pages, got {metadata.total_pages}"

    return metadata
