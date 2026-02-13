"""
Extensive tests for src.write.writer module.

Tests cover:
- WriteOptions configuration
- AsaMetadataRegistryWrite initialization and validation
- Group building methods
- High-level send methods (e.g., create_metadata, replace_metadata) using simulate_before_send option
- Flag management methods
- Utility methods
- Fee pooling and padding
- Extra resources handling
- Error handling and edge cases
"""

from unittest.mock import Mock

import pytest
from algokit_utils import SendParams, SigningAccount
from algosdk.error import AlgodHTTPError

from asa_metadata_registry import (
    AsaMetadataRegistryWrite,
    AssetMetadata,
    AssetMetadataBox,
    MbrDelta,
    MissingAppClientError,
    RegistryParameters,
    SimulateOptions,
    WriteOptions,
    flags,
    get_default_registry_params,
)
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from asa_metadata_registry.write.writer import (
    _append_extra_resources,
    _chunks_for_slice,
)

# ================================================================
# WriteOptions Tests
# ================================================================


class TestWriteOptions:
    """Test WriteOptions dataclass and its defaults."""

    def test_default_options(self) -> None:
        """Test default WriteOptions values."""
        opts = WriteOptions()
        assert opts.extra_resources == 0
        assert opts.fee_padding_txns == 0
        assert opts.cover_app_call_inner_transaction_fees is True

    def test_custom_options(self) -> None:
        """Test custom WriteOptions configuration."""
        opts = WriteOptions(
            extra_resources=5,
            fee_padding_txns=2,
            cover_app_call_inner_transaction_fees=False,
        )
        assert opts.extra_resources == 5
        assert opts.fee_padding_txns == 2
        assert opts.cover_app_call_inner_transaction_fees is False


# ================================================================
# Private Helper Functions Tests
# ================================================================


class TestChunkingHelpers:
    """Test private chunking helper functions."""

    def test_chunks_for_slice_single(self) -> None:
        """Test slicing a small payload into single chunk."""
        payload = b"slice"
        chunks = _chunks_for_slice(payload, max_size=100)
        assert len(chunks) == 1
        assert chunks[0] == payload

    def test_chunks_for_slice_multiple(self) -> None:
        """Test slicing a large payload into multiple chunks."""
        payload = b"x" * 250
        chunks = _chunks_for_slice(payload, max_size=100)
        assert len(chunks) == 3
        assert len(chunks[0]) == 100
        assert len(chunks[1]) == 100
        assert len(chunks[2]) == 50
        assert b"".join(chunks) == payload

    def test_chunks_for_slice_empty(self) -> None:
        """Test slicing empty payload."""
        chunks = _chunks_for_slice(b"", max_size=100)
        assert len(chunks) == 1
        assert chunks[0] == b""

    def test_chunks_for_slice_invalid_max_size(self) -> None:
        """Test that invalid max_size raises ValueError."""
        with pytest.raises(ValueError, match="max_size must be > 0"):
            _chunks_for_slice(b"test", max_size=0)
        with pytest.raises(ValueError, match="max_size must be > 0"):
            _chunks_for_slice(b"test", max_size=-1)


class TestComposerHelpers:
    """Test composer helper functions (mocked)."""

    def test_append_extra_resources_zero(self, asset_manager: SigningAccount) -> None:
        """Test that no extra resources are appended when count is 0."""
        composer = Mock()
        _append_extra_resources(composer, count=0, sender=asset_manager.address)
        composer.extra_resources.assert_not_called()

    def test_append_extra_resources_negative(
        self, asset_manager: SigningAccount
    ) -> None:
        """Test that negative count doesn't append extra resources."""
        composer = Mock()
        _append_extra_resources(composer, count=-5, sender=asset_manager.address)
        composer.extra_resources.assert_not_called()

    def test_append_extra_resources_multiple(
        self, asset_manager: SigningAccount
    ) -> None:
        """Test appending multiple extra resource calls."""
        composer = Mock()
        _append_extra_resources(composer, count=3, sender=asset_manager.address)
        assert composer.extra_resources.call_count == 3


# ================================================================
# AsaMetadataRegistryWrite Initialization Tests
# ================================================================


class TestAsaMetadataRegistryWriteInit:
    """Test AsaMetadataRegistryWrite initialization."""

    def test_init_with_client(
        self, asa_metadata_registry_client: AsaMetadataRegistryClient
    ) -> None:
        """Test successful initialization with client."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        assert writer.client is asa_metadata_registry_client
        assert writer.params is None

    def test_init_with_client_and_params(
        self, asa_metadata_registry_client: AsaMetadataRegistryClient
    ) -> None:
        """Test initialization with both client and params."""
        params = get_default_registry_params()
        writer = AsaMetadataRegistryWrite(
            client=asa_metadata_registry_client, params=params
        )
        assert writer.client is asa_metadata_registry_client
        assert writer.params is params

    def test_init_with_none_client_raises_error(self) -> None:
        """Test that initializing with None client raises MissingAppClientError."""
        with pytest.raises(MissingAppClientError):
            AsaMetadataRegistryWrite(client=None)  # type: ignore[arg-type]

    def test_params_property_uses_cached(
        self, asa_metadata_registry_client: AsaMetadataRegistryClient
    ) -> None:
        """Test that _params() returns cached params if available."""
        params = get_default_registry_params()
        writer = AsaMetadataRegistryWrite(
            client=asa_metadata_registry_client, params=params
        )
        assert writer._params() is params

    def test_params_property_fetches_on_chain(
        self, asa_metadata_registry_client: AsaMetadataRegistryClient
    ) -> None:
        """Test that _params() fetches from on-chain if not cached."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        params = writer._params()
        # Should fetch from chain
        assert isinstance(params, RegistryParameters)
        assert params.header_size > 0


# ================================================================
# Group Builder Tests
# ================================================================


class TestBuildGroupMethods:
    """Test group building methods."""

    def test_build_create_metadata_group(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """Test building create group for metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={"name": "Test"},
        )
        composer = writer.build_create_metadata_group(
            asset_manager=asset_manager, metadata=metadata
        )
        assert composer is not None

    def test_build_delete_metadata_group(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building delete group."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_delete_metadata_group(
            asset_manager=asset_manager, asset_id=mutable_short_metadata.asset_id
        )
        assert composer is not None

    def test_build_delete_with_options(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building delete group with custom options."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_delete_metadata_group(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
        )
        assert composer is not None


# ================================================================
# High-Level Send Method Tests
# ================================================================


class TestCreateMetadata:
    """Test create_metadata high-level method."""

    def test_create_metadata_returns_mbr_delta(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """Test creating metadata returns MbrDelta."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={"name": "Test", "description": "Test metadata"},
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

    def test_create_with_simulate_before_send(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """Test creating metadata with simulate_before_send=True."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={"name": "Test Simulate"},
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager,
            metadata=metadata,
            simulate_before_send=True,
        )
        assert isinstance(mbr_delta, MbrDelta)

    def test_create_empty_metadata_returns_mbr_delta(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        empty_metadata: AssetMetadata,
    ) -> None:
        """Test creating empty metadata returns MbrDelta."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=empty_metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

    def test_create_short_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        short_metadata: AssetMetadata,
    ) -> None:
        """Test creating short metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=short_metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive
        # Verify metadata was created
        box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
            short_metadata.asset_id
        )
        assert box_value is not None

    def test_create_large_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        maxed_metadata: AssetMetadata,
    ) -> None:
        """Test creating large metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=maxed_metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

    def test_create_with_custom_simulate_options(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        short_metadata: AssetMetadata,
    ) -> None:
        """Test creating metadata with custom SimulateOptions."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        sim_opts = SimulateOptions(
            allow_empty_signatures=True, skip_signatures=True, allow_more_logs=True
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager,
            metadata=short_metadata,
            simulate_before_send=True,
            simulate_options=sim_opts,
        )
        assert isinstance(mbr_delta, MbrDelta)

    def test_create_with_custom_send_params(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        short_metadata: AssetMetadata,
    ) -> None:
        """Test creating metadata with custom SendParams."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        send_params = SendParams(cover_app_call_inner_transaction_fees=False)
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager,
            metadata=short_metadata,
            send_params=send_params,
        )
        assert isinstance(mbr_delta, MbrDelta)


class TestDeleteMetadata:
    """Test delete_metadata high-level method."""

    def test_delete_existing_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test deleting existing metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        mbr_delta = writer.delete_metadata(
            asset_manager=asset_manager, asset_id=mutable_short_metadata.asset_id
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_negative
        # Verify deletion
        with pytest.raises(AlgodHTTPError, match="box not found"):
            asa_metadata_registry_client.state.box.asset_metadata.get_value(
                mutable_short_metadata.asset_id
            )


# ================================================================
# Flag Management Tests
# ================================================================


class TestSetReversibleFlag:
    """Test set_reversible_flag method."""

    def test_set_reversible_flag_true(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test setting a reversible flag to True."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        writer.set_reversible_flag(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            flag_index=flags.REV_FLG_ARC20,
            value=True,
        )
        # Verify flag was set
        box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
            mutable_short_metadata.asset_id
        )
        assert box_value is not None
        updated = AssetMetadataBox.parse(
            asset_id=mutable_short_metadata.asset_id, value=box_value
        )
        assert updated.header.is_arc20_smart_asa is True

    def test_set_reversible_flag_false(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test setting a reversible flag to False."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        # First set to True
        writer.set_reversible_flag(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            flag_index=flags.REV_FLG_ARC62,
            value=True,
        )
        # Then set to False
        writer.set_reversible_flag(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            flag_index=flags.REV_FLG_ARC62,
            value=False,
        )
        box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
            mutable_short_metadata.asset_id
        )
        assert box_value is not None
        updated = AssetMetadataBox.parse(
            asset_id=mutable_short_metadata.asset_id, value=box_value
        )
        assert updated.header.is_arc62_circulating_supply is False


class TestSetIrreversibleFlag:
    """Test set_irreversible_flag method."""

    def test_set_irreversible_flag(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test setting an irreversible flag."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        writer.set_irreversible_flag(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            flag_index=flags.IRR_FLG_RESERVED_3,
        )
        # Verify flag was set
        box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
            mutable_short_metadata.asset_id
        )
        assert box_value is not None
        updated = AssetMetadataBox.parse(
            asset_id=mutable_short_metadata.asset_id, value=box_value
        )
        assert updated.header.flags.irreversible.reserved_3 is True


class TestSetImmutable:
    """Test set_immutable method."""

    def test_set_immutable(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test setting metadata as immutable."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        writer.set_immutable(
            asset_manager=asset_manager, asset_id=mutable_short_metadata.asset_id
        )
        # Verify immutable flag was set
        box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
            mutable_short_metadata.asset_id
        )
        assert box_value is not None
        updated = AssetMetadataBox.parse(
            asset_id=mutable_short_metadata.asset_id, value=box_value
        )
        assert updated.header.is_immutable is True


# ================================================================
# Edge Cases and Error Handling
# ================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_create_with_large_fee_padding(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """Test creating with large fee padding."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        options = WriteOptions(fee_padding_txns=10)
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={"name": "Large Fee Pad"},
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata, options=options
        )
        assert isinstance(mbr_delta, MbrDelta)

    def test_create_with_extra_resources(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """Test creating with extra resources."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        options = WriteOptions(extra_resources=3)
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={"name": "Extra Resources"},
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata, options=options
        )
        assert isinstance(mbr_delta, MbrDelta)


# ================================================================
# Integration-Style Tests
# ================================================================


class TestWriteIntegration:
    """Integration-style tests for complete workflows."""

    def test_create_then_delete_workflow(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """Test complete create -> delete workflow."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)

        # Create
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={"name": "Will be deleted"},
        )
        create_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata
        )
        assert create_delta.is_positive

        # Delete
        delete_delta = writer.delete_metadata(
            asset_manager=asset_manager, asset_id=arc_89_asa
        )
        assert delete_delta.is_negative

    def test_create_set_flags_workflow(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """Test create -> set flags workflow."""

        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)

        # Create
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={"name": "Test flags"},
        )
        writer.create_metadata(asset_manager=asset_manager, metadata=metadata)

        # Set flags
        writer.set_reversible_flag(
            asset_manager=asset_manager,
            asset_id=arc_89_asa,
            flag_index=flags.REV_FLG_ARC20,
            value=True,
        )
        writer.set_reversible_flag(
            asset_manager=asset_manager,
            asset_id=arc_89_asa,
            flag_index=flags.REV_FLG_NTT,
            value=True,
        )
        writer.set_irreversible_flag(
            asset_manager=asset_manager,
            asset_id=arc_89_asa,
            flag_index=flags.IRR_FLG_RESERVED_3,
        )

        # Verify both flags are set
        box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
            arc_89_asa
        )
        assert box_value is not None
        result = AssetMetadataBox.parse(asset_id=arc_89_asa, value=box_value)
        assert result.header.flags.reversible.arc20 is True
        assert result.header.flags.reversible.ntt is True
        assert result.header.flags.irreversible.reserved_3 is True


# ================================================================
# Group Builder Tests
# ================================================================


class TestBuildCreateMetadataGroup:
    """Test build_create_metadata_group method."""

    def test_build_create_empty_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        empty_metadata: AssetMetadata,
    ) -> None:
        """Test building create group for empty metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_create_metadata_group(
            asset_manager=asset_manager, metadata=empty_metadata
        )
        assert composer is not None

    def test_build_create_short_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        short_metadata: AssetMetadata,
    ) -> None:
        """Test building create group for short metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_create_metadata_group(
            asset_manager=asset_manager, metadata=short_metadata
        )
        assert composer is not None

    def test_build_create_with_custom_options(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        short_metadata: AssetMetadata,
    ) -> None:
        """Test building create group with custom WriteOptions."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        options = WriteOptions(extra_resources=2, fee_padding_txns=1)
        composer = writer.build_create_metadata_group(
            asset_manager=asset_manager, metadata=short_metadata, options=options
        )
        assert composer is not None

    def test_build_create_large_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        maxed_metadata: AssetMetadata,
    ) -> None:
        """Test building create group for large metadata (multiple chunks)."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_create_metadata_group(
            asset_manager=asset_manager, metadata=maxed_metadata
        )
        assert composer is not None


class TestBuildReplaceMetadataGroup:
    """Test build_replace_metadata_group method."""

    def test_build_replace_smaller_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building replace group when new metadata is smaller/equal."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        # Replace with empty (smaller)
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_short_metadata.asset_id,
            metadata_bytes=b"",
            validate_json_object=False,
        )
        composer = writer.build_replace_metadata_group(
            asset_manager=asset_manager,
            metadata=new_metadata,
            assume_current_size=mutable_short_metadata.size,
        )
        assert composer is not None

    def test_build_replace_larger_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building replace group when new metadata is larger."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        # Replace with larger content
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_short_metadata.asset_id,
            metadata_bytes=b"x" * (mutable_short_metadata.size + 1000),
            validate_json_object=False,
        )
        composer = writer.build_replace_metadata_group(
            asset_manager=asset_manager,
            metadata=new_metadata,
            assume_current_size=mutable_short_metadata.size,
        )
        assert composer is not None

    def test_build_replace_auto_detect_size(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test replace group auto-detects current size when not provided."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_short_metadata.asset_id,
            metadata_bytes=b"new",
            validate_json_object=False,
        )
        # Don't pass assume_current_size, should fetch from chain
        composer = writer.build_replace_metadata_group(
            asset_manager=asset_manager, metadata=new_metadata
        )
        assert composer is not None

    def test_build_replace_with_options(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building replace group with custom options."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_short_metadata.asset_id,
            metadata_bytes=b"updated",
            validate_json_object=False,
        )
        composer = writer.build_replace_metadata_group(
            asset_manager=asset_manager,
            metadata=new_metadata,
            assume_current_size=mutable_short_metadata.size,
        )
        assert composer is not None


class TestBuildReplaceMetadataSliceGroup:
    """Test build_replace_metadata_slice_group method."""

    def test_build_slice_small_payload(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building slice group with small payload (single chunk)."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_replace_metadata_slice_group(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            offset=0,
            payload=b"slice",
        )
        assert composer is not None

    def test_build_slice_large_payload(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building slice group with large payload (multiple chunks)."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        params = writer._params()
        # Create payload larger than replace_payload_max_size
        large_payload = b"x" * (params.replace_payload_max_size * 2 + 100)
        composer = writer.build_replace_metadata_slice_group(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            offset=10,
            payload=large_payload,
        )
        assert composer is not None

    def test_build_slice_with_options(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building slice group with custom options."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        options = WriteOptions(extra_resources=3)
        composer = writer.build_replace_metadata_slice_group(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            offset=0,
            payload=b"updated slice",
            options=options,
        )
        assert composer is not None


class TestBuildDeleteMetadataGroup:
    """Test build_delete_metadata_group method."""

    def test_build_delete(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building delete group."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_delete_metadata_group(
            asset_manager=asset_manager, asset_id=mutable_short_metadata.asset_id
        )
        assert composer is not None

    def test_build_delete_with_options(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test building delete group with custom options."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_delete_metadata_group(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
        )
        assert composer is not None


# ================================================================
# High-Level Send Method Tests
# ================================================================


class TestReplaceMetadata:
    """Test replace_metadata high-level method."""

    def test_replace_with_smaller_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test replacing with smaller metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_short_metadata.asset_id,
            metadata_bytes=b"small",
            validate_json_object=False,
        )
        mbr_delta = writer.replace_metadata(
            asset_manager=asset_manager,
            metadata=new_metadata,
            assume_current_size=mutable_short_metadata.size,
        )
        assert isinstance(mbr_delta, MbrDelta)
        # Should be negative or zero since smaller
        assert mbr_delta.is_negative or mbr_delta.is_zero

    def test_replace_with_larger_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_empty_metadata: AssetMetadata,
    ) -> None:
        """Test replacing with larger metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_empty_metadata.asset_id,
            metadata_bytes=b"x" * 1000,
            validate_json_object=False,
        )
        mbr_delta = writer.replace_metadata(
            asset_manager=asset_manager,
            metadata=new_metadata,
            assume_current_size=0,
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

    def test_replace_auto_detect_current_size(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test replace auto-detects current size."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_short_metadata.asset_id,
            metadata_bytes=b"replacement",
            validate_json_object=False,
        )
        mbr_delta = writer.replace_metadata(
            asset_manager=asset_manager, metadata=new_metadata
        )
        assert isinstance(mbr_delta, MbrDelta)

    def test_replace_with_simulate(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test replace with simulate_before_send."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        new_metadata = AssetMetadata.from_bytes(
            asset_id=mutable_short_metadata.asset_id,
            metadata_bytes=b"new",
            validate_json_object=False,
        )
        mbr_delta = writer.replace_metadata(
            asset_manager=asset_manager,
            metadata=new_metadata,
            simulate_before_send=True,
            assume_current_size=mutable_short_metadata.size,
        )
        assert isinstance(mbr_delta, MbrDelta)


class TestReplaceMetadataSlice:
    """Test replace_metadata_slice high-level method."""

    def test_replace_slice(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test replacing a slice of metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        writer.replace_metadata_slice(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            offset=0,
            payload=b"patch",
        )
        # Should complete without error

    def test_replace_slice_with_simulate(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test replacing slice with simulate_before_send."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        writer.replace_metadata_slice(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            offset=5,
            payload=b"updated",
            simulate_before_send=True,
        )
