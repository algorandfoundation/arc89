"""
These tests exercise real local network interactions (e.g., simulations and on-chain ASA lookups/creation)
via the provided localnet-backed fixtures.
"""

import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams, SigningAccount
from algosdk.error import AlgodHTTPError

from asa_metadata_registry import (
    AsaMetadataRegistryRead,
    AsaMetadataRegistryWrite,
    AssetMetadata,
    MbrDelta,
    SimulateOptions,
    flags,
)
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)

# ================================================================
# Single Transaction Compose Simulation Tests (integration)
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
