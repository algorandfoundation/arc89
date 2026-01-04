"""
Integration tests for src.read.reader module with real smart contracts.

These tests use actual deployed contracts and verify the reader works
end-to-end with both BOX and AVM sources.
"""

import pytest

from src.asa_metadata_registry import (
    AsaMetadataRegistryRead,
    AssetMetadata,
    MetadataSource,
)
from src.asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from src.asa_metadata_registry.codec import asset_id_to_box_name, b64url_encode

# ================================================================
# Test Reader with Uploaded Metadata
# ================================================================


class TestReaderWithAlgod:
    """Test reader with algod (BOX source) using uploaded metadata."""

    def test_get_asset_metadata_short_box_source(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test reading short metadata via BOX source."""
        result = reader_with_algod.get_asset_metadata(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert result.asset_id == mutable_short_metadata.asset_id
        assert result.body.raw_bytes == mutable_short_metadata.body.raw_bytes
        assert result.header.is_short is True

    def test_get_asset_metadata_maxed_box_source(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_maxed_metadata: AssetMetadata,
    ) -> None:
        """Test reading maxed metadata via BOX source."""
        result = reader_with_algod.get_asset_metadata(
            asset_id=mutable_maxed_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert result.asset_id == mutable_maxed_metadata.asset_id
        assert len(result.body.raw_bytes) == mutable_maxed_metadata.size
        assert result.header.is_short is False

    def test_get_asset_metadata_empty_box_source(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_empty_metadata: AssetMetadata,
    ) -> None:
        """Test reading empty metadata via BOX source."""
        result = reader_with_algod.get_asset_metadata(
            asset_id=mutable_empty_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert result.asset_id == mutable_empty_metadata.asset_id
        assert len(result.body.raw_bytes) == 0
        assert result.header.is_short is True

    def test_check_metadata_exists_true(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test checking metadata existence when it exists."""
        result = reader_with_algod.arc89_check_metadata_exists(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert result.asa_exists is True
        assert result.metadata_exists is True

    def test_is_metadata_immutable_false(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test checking immutability of mutable metadata."""
        result = reader_with_algod.arc89_is_metadata_immutable(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert result is False

    def test_is_metadata_immutable_true(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        immutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test checking immutability of immutable metadata."""
        result = reader_with_algod.arc89_is_metadata_immutable(
            asset_id=immutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert result is True

    def test_is_metadata_short_true(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test checking if metadata is short (true case)."""
        is_short, round_num = reader_with_algod.arc89_is_metadata_short(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert is_short is True
        assert isinstance(round_num, int)
        assert round_num > 0

    def test_is_metadata_short_false(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_maxed_metadata: AssetMetadata,
    ) -> None:
        """Test checking if metadata is short (false case)."""
        is_short, round_num = reader_with_algod.arc89_is_metadata_short(
            asset_id=mutable_maxed_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert is_short is False
        assert isinstance(round_num, int)

    def test_get_metadata_header(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting metadata header."""
        header = reader_with_algod.arc89_get_metadata_header(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert header.last_modified_round > 0
        assert len(header.metadata_hash) == 32

    def test_get_metadata_pagination(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting metadata pagination info."""
        pagination = reader_with_algod.arc89_get_metadata_pagination(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert pagination.metadata_size == mutable_short_metadata.size
        assert pagination.total_pages >= 0

    def test_get_metadata_first_page(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting first page of metadata."""
        page = reader_with_algod.arc89_get_metadata(
            asset_id=mutable_short_metadata.asset_id,
            page=0,
            source=MetadataSource.BOX,
        )

        assert len(page.page_content) > 0
        assert page.last_modified_round > 0

    def test_get_metadata_slice(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting a slice of metadata."""
        slice_data = reader_with_algod.arc89_get_metadata_slice(
            asset_id=mutable_short_metadata.asset_id,
            offset=0,
            size=10,
            source=MetadataSource.BOX,
        )

        assert len(slice_data) <= 10
        assert slice_data == mutable_short_metadata.body.raw_bytes[:10]

    def test_get_metadata_header_hash(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting metadata header hash."""
        header_hash = reader_with_algod.arc89_get_metadata_header_hash(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert len(header_hash) == 32

    def test_get_metadata_page_hash(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting metadata page hash."""
        page_hash = reader_with_algod.arc89_get_metadata_page_hash(
            asset_id=mutable_short_metadata.asset_id,
            page=0,
            source=MetadataSource.BOX,
        )

        assert len(page_hash) == 32

    def test_get_metadata_hash(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting full metadata hash."""
        metadata_hash = reader_with_algod.arc89_get_metadata_hash(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        assert len(metadata_hash) == 32


class TestReaderWithAvm:
    """Test reader with AVM source using uploaded metadata."""

    def test_get_asset_metadata_short_avm_source(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test reading short metadata via AVM source."""
        result = reader_with_avm.get_asset_metadata(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert result.asset_id == mutable_short_metadata.asset_id
        assert result.body.raw_bytes == mutable_short_metadata.body.raw_bytes
        assert result.header.is_short is True

    def test_get_asset_metadata_maxed_avm_source(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
        mutable_maxed_metadata: AssetMetadata,
    ) -> None:
        """Test reading maxed metadata via AVM source."""
        result = reader_with_avm.get_asset_metadata(
            asset_id=mutable_maxed_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert result.asset_id == mutable_maxed_metadata.asset_id
        assert len(result.body.raw_bytes) == mutable_maxed_metadata.size

    def test_check_metadata_exists_avm(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test checking metadata existence via AVM."""
        result = reader_with_avm.arc89_check_metadata_exists(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert result.asa_exists is True
        assert result.metadata_exists is True

    def test_is_metadata_immutable_avm(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
        immutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test checking immutability via AVM."""
        result = reader_with_avm.arc89_is_metadata_immutable(
            asset_id=immutable_short_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert result is True

    def test_get_metadata_header_avm(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test getting metadata header via AVM."""
        header = reader_with_avm.arc89_get_metadata_header(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert header.last_modified_round > 0
        assert len(header.metadata_hash) == 32

    def test_get_metadata_pagination_avm(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
        mutable_maxed_metadata: AssetMetadata,
    ) -> None:
        """Test getting pagination info via AVM."""
        pagination = reader_with_avm.arc89_get_metadata_pagination(
            asset_id=mutable_maxed_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert pagination.metadata_size == mutable_maxed_metadata.size
        assert pagination.total_pages > 1  # Maxed metadata should be multi-page

    def test_get_metadata_registry_parameters(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
    ) -> None:
        """Test getting registry parameters via AVM."""
        params = reader_with_avm.arc89_get_metadata_registry_parameters(
            source=MetadataSource.AVM
        )

        assert params.header_size > 0
        assert params.max_metadata_size > 0


class TestReaderFull:
    """Test reader with both algod and AVM configured (AUTO mode)."""

    def test_auto_source_prefers_box(
        self,
        reader_full: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test AUTO source prefers BOX when available."""
        # AUTO should use BOX (faster) when both are available
        result = reader_full.get_asset_metadata(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.AUTO,
        )

        assert result.asset_id == mutable_short_metadata.asset_id
        assert result.body.raw_bytes == mutable_short_metadata.body.raw_bytes

    def test_box_and_avm_consistency(
        self,
        reader_full: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test BOX and AVM sources return consistent results."""
        box_result = reader_full.get_asset_metadata(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        avm_result = reader_full.get_asset_metadata(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        # Both should return same metadata
        assert box_result.body.raw_bytes == avm_result.body.raw_bytes
        assert box_result.header.is_short == avm_result.header.is_short
        assert box_result.header.is_immutable == avm_result.header.is_immutable

    def test_header_hash_consistency(
        self,
        reader_full: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test header hash is consistent between BOX and AVM."""
        box_hash = reader_full.arc89_get_metadata_header_hash(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        avm_hash = reader_full.arc89_get_metadata_header_hash(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert box_hash == avm_hash

    def test_metadata_hash_consistency(
        self,
        reader_full: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test metadata hash is consistent between BOX and AVM."""
        box_hash = reader_full.arc89_get_metadata_hash(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        avm_hash = reader_full.arc89_get_metadata_hash(
            asset_id=mutable_short_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert box_hash == avm_hash

    def test_pagination_consistency(
        self,
        reader_full: AsaMetadataRegistryRead,
        mutable_maxed_metadata: AssetMetadata,
    ) -> None:
        """Test pagination info is consistent between BOX and AVM."""
        box_pagination = reader_full.arc89_get_metadata_pagination(
            asset_id=mutable_maxed_metadata.asset_id,
            source=MetadataSource.BOX,
        )

        avm_pagination = reader_full.arc89_get_metadata_pagination(
            asset_id=mutable_maxed_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        assert box_pagination.metadata_size == avm_pagination.metadata_size
        assert box_pagination.page_size == avm_pagination.page_size
        assert box_pagination.total_pages == avm_pagination.total_pages


class TestReaderJsonExtraction:
    """Test JSON key extraction methods."""

    def test_get_string_by_key_box(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
        json_obj: dict[str, object],
    ) -> None:
        """Test extracting string value by key via BOX."""
        result = reader_with_algod.arc89_get_metadata_string_by_key(
            asset_id=mutable_short_metadata.asset_id,
            key="name",
            source=MetadataSource.BOX,
        )

        assert result == json_obj["name"]

    def test_get_uint64_by_key_box(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
        json_obj: dict[str, object],
    ) -> None:
        """Test extracting uint64 value by key via BOX."""
        result = reader_with_algod.arc89_get_metadata_uint64_by_key(
            asset_id=mutable_short_metadata.asset_id,
            key="answer",
            source=MetadataSource.BOX,
        )

        assert result == json_obj["answer"]

    def test_get_object_by_key_box(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test extracting object value by key via BOX."""
        result = reader_with_algod.arc89_get_metadata_object_by_key(
            asset_id=mutable_short_metadata.asset_id,
            key="date",
            source=MetadataSource.BOX,
        )

        # Result should be JSON string
        import json

        obj = json.loads(result)
        assert "day" in obj
        assert "month" in obj
        assert "year" in obj

    @pytest.mark.parametrize("encoding", [0, 1])
    def test_get_b64_bytes_by_key_box(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        mutable_short_metadata: AssetMetadata,
        encoding: int,
    ) -> None:
        """Test extracting base64-encoded bytes by key via BOX."""
        key = "gh_b64_url" if encoding == 0 else "gh_b64_std"

        result = reader_with_algod.arc89_get_metadata_b64_bytes_by_key(
            asset_id=mutable_short_metadata.asset_id,
            key=key,
            b64_encoding=encoding,
            source=MetadataSource.BOX,
        )

        # Should return decoded bytes
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestReaderArc90Uri:
    """Test ARC-90 URI resolution."""

    def test_resolve_from_asset_url(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        arc_89_asa: int,
    ) -> None:
        """Test resolving URI from ASA's url field."""
        uri = reader_with_algod.resolve_arc90_uri(asset_id=arc_89_asa)

        assert uri.asset_id == arc_89_asa
        assert uri.app_id is not None

    def test_resolve_from_explicit_uri(
        self,
        reader_with_algod: AsaMetadataRegistryRead,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc_89_asa: int,
    ) -> None:
        """Test resolving from explicit metadata URI."""

        # Encode the asset ID as base64url for the box parameter
        box_encoded = b64url_encode(asset_id_to_box_name(arc_89_asa))
        uri_string = f"algorand://net:localnet/app/{asa_metadata_registry_client.app_id}?box={box_encoded}"

        uri = reader_with_algod.resolve_arc90_uri(metadata_uri=uri_string)

        assert uri.asset_id == arc_89_asa
        assert uri.app_id == asa_metadata_registry_client.app_id

    def test_get_partial_uri(
        self,
        reader_with_avm: AsaMetadataRegistryRead,
    ) -> None:
        """Test getting partial URI from registry."""
        uri = reader_with_avm.arc89_get_metadata_partial_uri(source=MetadataSource.AVM)

        assert isinstance(uri, str)
        assert "algorand://" in uri


class TestReaderEdgeCases:
    """Test edge cases with real contracts."""

    def test_empty_metadata_edge_case(
        self,
        reader_full: AsaMetadataRegistryRead,
        mutable_empty_metadata: AssetMetadata,
    ) -> None:
        """Test handling of empty metadata (edge case)."""
        result = reader_full.get_asset_metadata(
            asset_id=mutable_empty_metadata.asset_id,
            source=MetadataSource.AUTO,
        )

        assert len(result.body.raw_bytes) == 0

        # Pagination should work correctly
        pagination = reader_full.arc89_get_metadata_pagination(
            asset_id=mutable_empty_metadata.asset_id
        )
        assert pagination.metadata_size == 0
        assert pagination.total_pages == 0

    def test_large_metadata_paging(
        self,
        reader_full: AsaMetadataRegistryRead,
        mutable_maxed_metadata: AssetMetadata,
    ) -> None:
        """Test reading large metadata across multiple pages."""
        result = reader_full.get_asset_metadata(
            asset_id=mutable_maxed_metadata.asset_id,
            source=MetadataSource.AVM,
        )

        # Verify all pages were read correctly
        assert len(result.body.raw_bytes) == mutable_maxed_metadata.size

        # Check pagination
        pagination = reader_full.arc89_get_metadata_pagination(
            asset_id=mutable_maxed_metadata.asset_id
        )
        assert pagination.total_pages > 1

    def test_immutable_flag_respected(
        self,
        reader_full: AsaMetadataRegistryRead,
        immutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test that immutable flag is correctly read."""
        result = reader_full.get_asset_metadata(
            asset_id=immutable_short_metadata.asset_id
        )

        assert result.header.is_immutable is True

        # Verify via is_metadata_immutable getter
        is_immutable = reader_full.arc89_is_metadata_immutable(
            asset_id=immutable_short_metadata.asset_id
        )
        assert is_immutable is True
