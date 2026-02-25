"""
Extensive tests for src.write.writer module.

Tests cover:
- WriteOptions configuration
- AsaMetadataRegistryWrite initialization and validation
- Group building methods
- High-level send methods (e.g., create_metadata, replace_metadata)
- Flag management methods
- Utility methods
- Fee pooling and padding
- Extra resources handling
- Error handling and edge cases
"""

from unittest.mock import Mock

import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams, SendParams, SigningAccount
from algosdk.error import AlgodHTTPError

from asa_metadata_registry import (
    AsaMetadataRegistryRead,
    AsaMetadataRegistryWrite,
    AssetMetadata,
    AssetMetadataBox,
    InvalidArc3PropertiesError,
    InvalidFlagIndexError,
    IrreversibleFlags,
    MbrDelta,
    MetadataFlags,
    MissingAppClientError,
    RegistryParameters,
    ReversibleFlags,
    SimulateOptions,
    WriteOptions,
    flags,
    get_default_registry_params,
)
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from asa_metadata_registry.validation import (
    is_positive_uint64,
    validate_arc3_properties,
)
from asa_metadata_registry.write.writer import (
    _append_extra_resources,
    _chunks_for_slice,
)
from tests.helpers.factories import create_arc3_payload, create_test_metadata
from tests.helpers.utils import create_metadata

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
        assert opts.populate_app_call_resources is True

    def test_custom_options(self) -> None:
        """Test custom WriteOptions configuration."""
        opts = WriteOptions(
            extra_resources=5,
            fee_padding_txns=2,
            cover_app_call_inner_transaction_fees=False,
            populate_app_call_resources=False,
        )
        assert opts.extra_resources == 5
        assert opts.fee_padding_txns == 2
        assert opts.cover_app_call_inner_transaction_fees is False
        assert opts.populate_app_call_resources is False


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


class TestValidateArc3Properties:
    """Test is_positive_uint64 and validate_arc3_properties helpers."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (1, True),
            (2**64 - 1, True),
            (0, False),
            (-1, False),
            (2**64, False),
            (1.0, False),
            ("1", False),
            (None, False),
        ],
    )
    def test_is_positive_uint64(
        self, value: object, expected: bool  # noqa: FBT001
    ) -> None:
        """Test is_positive_uint64 helper."""
        assert is_positive_uint64(value) is expected

    @pytest.mark.parametrize("arc_key", ["arc-20", "arc-62"])
    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({}, id="no_properties"),
            pytest.param({"properties": "not-a-dict"}, id="properties_not_dict"),
            pytest.param({"properties": {"other-key": 1}}, id="missing_arc_key"),
            pytest.param(
                {"properties": {"arc-20": "not-a-dict", "arc-62": "not-a-dict"}},
                id="arc_key_not_dict",
            ),
            pytest.param(
                {"properties": {"arc-20": {}, "arc-62": {}}},
                id="missing_application_id",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": 0},
                        "arc-62": {"application-id": 0},
                    }
                },
                id="app_id_zero",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": -1},
                        "arc-62": {"application-id": -1},
                    }
                },
                id="app_id_negative",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": "123"},
                        "arc-62": {"application-id": "123"},
                    }
                },
                id="app_id_string",
            ),
            pytest.param(
                {
                    "properties": {
                        "arc-20": {"application-id": 2**64},
                        "arc-62": {"application-id": 2**64},
                    }
                },
                id="app_id_overflow",
            ),
        ],
    )
    def test_invalid_raises(self, body: dict[str, object], arc_key: str) -> None:
        """Test invalid properties raises."""
        with pytest.raises(InvalidArc3PropertiesError):
            validate_arc3_properties(body, arc_key)

    @pytest.mark.parametrize("arc_key", ["arc-20", "arc-62"])
    def test_valid_passes(self, arc_key: str) -> None:
        """Test valid properties passes."""
        body = {"properties": {arc_key: {"application-id": 123456}}}
        validate_arc3_properties(body, arc_key)


# ================================================================
# Send Group Helper Tests
# ================================================================


class TestSendGroupHelper:
    """Test _send_group helper behavior (mocked)."""

    def test_send_group_build_send_params_from_options(self) -> None:
        """Test _send_group derives SendParams from WriteOptions."""
        composer = Mock()
        send_result = Mock()
        composer.send.return_value = send_result
        options = WriteOptions(
            cover_app_call_inner_transaction_fees=False,
            populate_app_call_resources=False,
        )

        result = AsaMetadataRegistryWrite._send_group(
            send_params=None,
            options=options,
            composer=composer,
        )
        assert result is send_result
        composer.simulate.assert_not_called()
        composer.send.assert_called_once()
        sent = composer.send.call_args.kwargs["send_params"]
        assert sent["cover_app_call_inner_transaction_fees"] is False
        assert sent["populate_app_call_resources"] is False

    def test_send_group_use_provided_send_params(self) -> None:
        """Test _send_group uses provided send_params."""
        composer = Mock()
        send_result = Mock()
        composer.send.return_value = send_result
        send_params = SendParams(
            cover_app_call_inner_transaction_fees=False,
            populate_app_call_resources=False,
        )

        result = AsaMetadataRegistryWrite._send_group(
            send_params=send_params,
            options=WriteOptions(
                cover_app_call_inner_transaction_fees=True,
                populate_app_call_resources=True,
            ),
            composer=composer,
        )
        assert result is send_result
        composer.simulate.assert_not_called()
        composer.send.assert_called_once()
        sent = composer.send.call_args.kwargs["send_params"]
        assert sent is send_params

    def test_send_group_build_send_params_with_default_options(self) -> None:
        """Test _send_group derives default SendParams when options are omitted."""
        composer = Mock()
        send_result = Mock()
        composer.send.return_value = send_result

        result = AsaMetadataRegistryWrite._send_group(
            send_params=None,
            options=None,
            composer=composer,
        )
        assert result is send_result
        composer.simulate.assert_not_called()
        composer.send.assert_called_once()
        sent = composer.send.call_args.kwargs["send_params"]
        assert sent["cover_app_call_inner_transaction_fees"] is True
        assert sent["populate_app_call_resources"] is True

    def test_send_group_simulate_over_send(self) -> None:
        """Test _send_group uses simulate when SimulateOptions is provided."""
        composer = Mock()
        simulate_result = Mock()
        composer.simulate.return_value = simulate_result
        send_params = SendParams(
            cover_app_call_inner_transaction_fees=False,
            populate_app_call_resources=False,
        )
        simulate = SimulateOptions(
            allow_more_logs=True,
            allow_empty_signatures=True,
            extra_opcode_budget=4567,
            allow_unnamed_resources=True,
            exec_trace_config={"enable": True},
            simulation_round=999,
            skip_signatures=False,
        )

        result = AsaMetadataRegistryWrite._send_group(
            send_params=send_params,
            options=WriteOptions(),
            composer=composer,
            simulate=simulate,
        )
        assert result is simulate_result
        composer.send.assert_not_called()
        composer.simulate.assert_called_once_with(
            allow_more_logs=True,
            allow_empty_signatures=True,
            extra_opcode_budget=4567,
            allow_unnamed_resources=True,
            exec_trace_config={"enable": True},
            simulation_round=999,
            skip_signatures=False,
        )


class TestSendGroupHelperSimulate:
    """Test _send_group helper for simulation."""

    def test_send_group_simulate(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        short_metadata: AssetMetadata,
    ) -> None:
        """Test simulating a create metadata transaction group."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        composer = writer.build_create_metadata_group(
            asset_manager=asset_manager, metadata=short_metadata
        )
        simulate = SimulateOptions()  # Any custom options can go here
        simulate_result = writer._send_group(
            send_params=None,
            options=None,
            composer=composer,
            simulate=simulate,
        )

        assert simulate_result is not None
        assert simulate_result.returns

        # Example of inspecting a return value from simulate
        ret_val = simulate_result.returns[0].value
        assert isinstance(ret_val, (tuple, list))
        mbr_delta = MbrDelta.from_tuple(ret_val)
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

        # Simulate must not persist metadata
        with pytest.raises(AlgodHTTPError, match="box not found"):
            asa_metadata_registry_client.state.box.asset_metadata.get_value(
                short_metadata.asset_id
            )


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


class TestCreateMetadataArc3Compliant:
    """Test create_metadata validation for declared ARC-3 compliant ASAs."""

    def test_arc3_decimals_validation_skipped_when_decimals_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """
        If 'decimals' isn't present in JSON, writer must not fetch ASA params or
        validate decimals.
        """

        # Patch validate_arc3_values where it's imported/used (writer module).
        from asa_metadata_registry.write import writer as writer_module

        validate_mock = Mock()
        monkeypatch.setattr(writer_module, "validate_arc3_values", validate_mock)

        # If decimals validation were attempted, this on-chain API would be called.
        get_by_id_mock = Mock(
            side_effect=AssertionError("asset.get_by_id should not be called")
        )
        monkeypatch.setattr(
            asa_metadata_registry_client.algorand.asset,
            "get_by_id",
            get_by_id_mock,
            raising=True,
        )

        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={
                "name": "No Decimals",
                "description": "Should skip decimals validation",
            },
        )

        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager,
            metadata=metadata,
            validate_arc3=True,
        )

        assert isinstance(mbr_delta, MbrDelta)
        validate_mock.assert_not_called()
        get_by_id_mock.assert_not_called()

    def test_arc3_decimals_zero_triggers_decimals_validation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_89_asa: int,
    ) -> None:
        """
        When 'decimals' is explicitly set to 0, writer must fetch ASA params and
        run decimals validation under validate_arc3=True.
        """

        # Patch validate_arc3_values where it's imported/used (writer module).
        from asa_metadata_registry.write import writer as writer_module

        validate_mock = Mock()
        monkeypatch.setattr(writer_module, "validate_arc3_values", validate_mock)

        # Decimals validation should fetch on-chain ASA params even when decimals == 0.
        get_by_id_mock = Mock(return_value={"params": {"decimals": 0}})
        monkeypatch.setattr(
            asa_metadata_registry_client.algorand.asset,
            "get_by_id",
            get_by_id_mock,
            raising=True,
        )

        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_89_asa,
            json_obj={
                "name": "Zero Decimals",
                "description": "Should trigger decimals validation",
                "decimals": 0,
            },
        )

        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager,
            metadata=metadata,
            validate_arc3=True,
        )

        assert isinstance(mbr_delta, MbrDelta)
        # Writer must fetch ASA params and invoke ARC-3 validation.
        get_by_id_mock.assert_called_once()
        validate_mock.assert_called_once()

    def test_invalid_properties_no_rev_flags_creates_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_3_asa: int,
    ) -> None:
        """Test that arc3 flag without arc20/arc62 reversible flags skips properties validation."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_3_asa,
            json_obj=create_arc3_payload(name="ARC3 Compliant Test", properties={}),
            flags=MetadataFlags(
                reversible=ReversibleFlags(), irreversible=IrreversibleFlags(arc3=True)
            ),
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

    @pytest.mark.parametrize(
        "rev_flag",
        [
            pytest.param(ReversibleFlags(arc20=True), id="arc20"),
            pytest.param(ReversibleFlags(arc62=True), id="arc62"),
        ],
    )
    def test_no_arc3_flag_skips_validation(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_3_asa: int,
        rev_flag: ReversibleFlags,
    ) -> None:
        """Test that arc20/arc62 reversible flags without arc3 flag skip properties validation."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_3_asa,
            json_obj=create_arc3_payload(name="ARC3 Compliant Test", properties={}),
            flags=MetadataFlags(
                reversible=rev_flag, irreversible=IrreversibleFlags(arc3=False)
            ),
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

    def test_both_flags_valid_properties_creates_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_3_asa: int,
    ) -> None:
        """Test that both arc20+arc62 flags with valid properties creates metadata successfully."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_3_asa,
            json_obj=create_arc3_payload(
                name="ARC3 Compliant Test",
                properties={
                    "arc-20": {"application-id": 123456},
                    "arc-62": {"application-id": 654321},
                },
            ),
            flags=MetadataFlags(
                reversible=ReversibleFlags(arc20=True, arc62=True),
                irreversible=IrreversibleFlags(arc3=True),
            ),
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive

    @pytest.mark.parametrize(
        "rev_flag,prop_key",
        [
            pytest.param(ReversibleFlags(arc20=True), "arc-20", id="arc20"),
            pytest.param(ReversibleFlags(arc62=True), "arc-62", id="arc62"),
        ],
    )
    def test_valid_properties_creates_metadata(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_3_asa: int,
        rev_flag: ReversibleFlags,
        prop_key: str,
    ) -> None:
        """Test that valid properties with arc3 + arc20/arc62 flags creates metadata successfully."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=arc_3_asa,
            json_obj=create_arc3_payload(
                name="ARC3 Compliant Test",
                properties={prop_key: {"application-id": 123456}},
            ),
            flags=MetadataFlags(
                reversible=rev_flag, irreversible=IrreversibleFlags(arc3=True)
            ),
        )
        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager, metadata=metadata
        )
        assert isinstance(mbr_delta, MbrDelta)
        assert mbr_delta.is_positive


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
# Single Transaction Compose Simulation Tests
# ================================================================


class TestWriteSingleTransactionSimulation:
    """Test direct composer.simulate() for single-transaction writer methods."""

    def test_simulate_set_reversible_flag_single_transaction(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
        reader_with_algod: AsaMetadataRegistryRead,
    ) -> None:
        """Test simulating set_reversible_flag via direct composer."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee

        before = reader_with_algod.box.get_asset_metadata_record(
            asset_id=mutable_short_metadata.asset_id,
        )

        composer = writer.client.new_group()
        composer.arc89_set_reversible_flag(
            args=(mutable_short_metadata.asset_id, flags.REV_FLG_ARC20, True),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=min_fee)
            ),
        )

        simulate = SimulateOptions()  # Any custom options can go here
        simulate_result = composer.simulate(
            allow_more_logs=simulate.allow_more_logs,
            allow_empty_signatures=simulate.allow_empty_signatures,
            allow_unnamed_resources=simulate.allow_unnamed_resources,
            extra_opcode_budget=simulate.extra_opcode_budget,
            exec_trace_config=simulate.exec_trace_config,
            simulation_round=simulate.simulation_round,
            skip_signatures=simulate.skip_signatures,
        )

        assert simulate_result is not None
        assert simulate_result.simulate_response is not None
        assert len(simulate_result.returns) == 1
        assert simulate_result.returns[0].decode_error is None
        assert simulate_result.returns[0].value is None
        after = reader_with_algod.box.get_asset_metadata_record(
            asset_id=mutable_short_metadata.asset_id
        )
        assert after == before


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

    def test_fail_invalid_flag_index(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
    ) -> None:
        """Test that an out-of-range flag index raises InvalidFlagIndexError."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        with pytest.raises(InvalidFlagIndexError):
            writer.set_reversible_flag(
                asset_manager=asset_manager,
                asset_id=mutable_short_metadata.asset_id,
                flag_index=flags.REV_FLG_RESERVED_7 + 1,
                value=True,
            )

    @pytest.mark.parametrize(
        "flag_index",
        [
            pytest.param(flags.REV_FLG_ARC20, id="arc20"),
            pytest.param(flags.REV_FLG_ARC62, id="arc62"),
        ],
    )
    def test_fail_arc3_invalid_properties(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        arc_3_asa: int,
        flag_index: int,
    ) -> None:
        """Test that missing properties with arc3 + arc20/arc62 flags raises InvalidArc3PropertiesError."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = create_test_metadata(
            arc_3_asa,
            metadata_content=create_arc3_payload(name="ARC3 Test", properties={}),
            flags=MetadataFlags(
                reversible=ReversibleFlags.empty(),
                irreversible=IrreversibleFlags(arc3=True),
            ),
        )
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=arc_3_asa,
            metadata=metadata,
        )
        with pytest.raises(InvalidArc3PropertiesError):
            writer.set_reversible_flag(
                asset_manager=asset_manager,
                asset_id=arc_3_asa,
                flag_index=flag_index,
                value=True,
            )

    @pytest.mark.parametrize(
        "flag_index,arc_key",
        [
            pytest.param(flags.REV_FLG_ARC20, "arc-20", id="arc20"),
            pytest.param(flags.REV_FLG_ARC62, "arc-62", id="arc62"),
        ],
    )
    def test_arc3_valid_properties_sets_flag(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        reader_with_algod: AsaMetadataRegistryRead,
        arc_3_asa: int,
        flag_index: int,
        arc_key: str,
    ) -> None:
        """Test that valid properties with arc3 + arc20/arc62 flags sets the flag successfully."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = create_test_metadata(
            arc_3_asa,
            metadata_content=create_arc3_payload(
                name="ARC3 Test", properties={arc_key: {"application-id": 123456}}
            ),
            flags=MetadataFlags(
                reversible=ReversibleFlags.empty(),
                irreversible=IrreversibleFlags(arc3=True),
            ),
        )
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=arc_3_asa,
            metadata=metadata,
        )
        writer.set_reversible_flag(
            asset_manager=asset_manager,
            asset_id=arc_3_asa,
            flag_index=flag_index,
            value=True,
        )
        record = reader_with_algod.box.get_asset_metadata_record(
            asset_id=arc_3_asa,
        )
        assert record is not None
        assert record.header.flags.reversible.arc20 is (
            flag_index == flags.REV_FLG_ARC20
        )
        assert record.header.flags.reversible.arc62 is (
            flag_index == flags.REV_FLG_ARC62
        )


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
            flag_index=flags.REV_FLG_RESERVED_3,
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
        assert result.header.is_arc20_smart_asa is True
        assert result.header.flags.reversible.arc20 is True
        assert result.header.flags.reversible.reserved_3 is True
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
        options = WriteOptions(extra_resources=2, fee_padding_txns=1)
        composer = writer.build_replace_metadata_group(
            asset_manager=asset_manager,
            metadata=new_metadata,
            assume_current_size=mutable_short_metadata.size,
            options=options,
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
        options = WriteOptions(extra_resources=1, fee_padding_txns=2)
        composer = writer.build_delete_metadata_group(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            options=options,
        )
        assert composer is not None


# ================================================================
# High-Level Send Method Tests (Replace)
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


class TestReplaceMetadataSlice:
    """Test replace_metadata_slice high-level method."""

    def test_replace_slice(
        self,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        mutable_short_metadata: AssetMetadata,
        reader_with_algod: AsaMetadataRegistryRead,
    ) -> None:
        """Test replacing a slice of metadata."""
        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        writer.replace_metadata_slice(
            asset_manager=asset_manager,
            asset_id=mutable_short_metadata.asset_id,
            offset=0,
            payload=b"patch",
        )
        record = reader_with_algod.box.get_asset_metadata_record(
            asset_id=mutable_short_metadata.asset_id,
        )
        assert record is not None
        body = record.body.raw_bytes
        assert body[:5].decode("utf-8") == "patch"
