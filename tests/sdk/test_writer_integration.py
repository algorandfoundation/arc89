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
    IrreversibleFlags,
    MbrDelta,
    MetadataFlags,
    ReversibleFlags,
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


# ================================================================
# Integration tests for create_metadata(validate_immutable=...)
# ================================================================


class TestCreateMetadataImmutable:
    """Integration tests for create_metadata(validate_immutable=...)."""

    def test_rejects_when_asa_has_metadata_hash_and_not_immutable(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """If the ASA already has a metadata hash, validate_immutable requires metadata.is_immutable."""

        from algokit_utils import AssetCreateParams

        # Create a real ASA with a non-empty metadata_hash.
        asset_id = asa_metadata_registry_client.algorand.send.asset_create(
            params=AssetCreateParams(
                sender=asset_manager.address,
                total=1,
                asset_name="ARC89 With Hash",
                unit_name="A89H",
                url=arc89_partial_uri,
                decimals=0,
                default_frozen=False,
                manager=asset_manager.address,
                clawback=asset_manager.address,
                metadata_hash=b"\x01" * 32,
            )
        ).asset_id

        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=asset_id, json_obj={"name": "Not immutable"}
        )

        from asa_metadata_registry import RequiresImmutableMetadataError

        with pytest.raises(RequiresImmutableMetadataError):
            writer.create_metadata(
                asset_manager=asset_manager,
                metadata=metadata,
                validate_immutable=True,
            )

    def test_allows_when_metadata_is_immutable_if_asa_has_metadata_hash(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """If metadata is flagged immutable, validate_immutable should allow creation."""

        from algokit_utils import AssetCreateParams

        asset_id = asa_metadata_registry_client.algorand.send.asset_create(
            params=AssetCreateParams(
                sender=asset_manager.address,
                total=1,
                asset_name="ARC89 With Hash 2",
                unit_name="A89H2",
                url=arc89_partial_uri,
                decimals=0,
                default_frozen=False,
                manager=asset_manager.address,
                clawback=asset_manager.address,
                metadata_hash=b"\x02" * 32,
            )
        ).asset_id

        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=asset_id,
            json_obj={"name": "Immutable"},
            flags=MetadataFlags(
                reversible=ReversibleFlags(),
                irreversible=IrreversibleFlags(immutable=True),
            ),
        )

        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager,
            metadata=metadata,
            validate_immutable=True,
        )
        assert isinstance(mbr_delta, MbrDelta)

    def test_allows_non_immutable_when_asa_has_no_metadata_hash(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """If the ASA has no metadata hash set, validate_immutable shouldn't block non-immutable metadata."""

        from algokit_utils import AssetCreateParams

        asset_id = asa_metadata_registry_client.algorand.send.asset_create(
            params=AssetCreateParams(
                sender=asset_manager.address,
                total=1,
                asset_name="ARC89 No Hash",
                unit_name="A89N",
                url=arc89_partial_uri,
                decimals=0,
                default_frozen=False,
                manager=asset_manager.address,
                clawback=asset_manager.address,
            )
        ).asset_id

        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)
        metadata = AssetMetadata.from_json(
            asset_id=asset_id, json_obj={"name": "Mutable"}
        )

        mbr_delta = writer.create_metadata(
            asset_manager=asset_manager,
            metadata=metadata,
            validate_immutable=True,
        )
        assert isinstance(mbr_delta, MbrDelta)


# ================================================================
# Integration tests for ASA existence checks
# ================================================================


class TestAsaExists:
    """Integration tests for ASA existence checks."""

    def test_needs_asa_params_true_fails_when_asa_does_not_exist(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
    ) -> None:
        """When needs_asa_params is true and the ASA doesn't exist, we should surface the algod error."""

        writer = AsaMetadataRegistryWrite(client=asa_metadata_registry_client)

        # Use an asset id that should not exist on fresh localnet state.
        # We don't create an ASA on purpose.
        missing_asset_id = 0

        metadata = AssetMetadata.from_json(
            asset_id=missing_asset_id,
            json_obj={"name": "Missing ASA"},
        )

        # validate_immutable=True => needs_asa_params=True => calls asset.get_by_id() and should fail.
        with pytest.raises(Exception) as exc_info:
            writer.create_metadata(
                asset_manager=asset_manager,
                metadata=metadata,
                validate_existing=False,
                validate_immutable=True,
            )

        # Don't over-specify SDK exception types; ensure we're seeing the expected algod failure.
        assert (
            "asset" in str(exc_info.value).lower()
            or "not exist" in str(exc_info.value).lower()
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
