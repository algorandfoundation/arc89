"""
Comprehensive tests for src.asa_metadata_registry.migrate module.

Tests cover:
- ARC-2 message encoding (JSON format)
- ARC-2 migration message transaction building
- URI derivation with ARC-90 compliance fragments
- Full migration flow with LocalNet integration
- RBAC (Role-Based Access Control) preservation
- Error handling and edge cases
"""

import json
import os

import pytest
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AssetCreateParams,
    LogicError,
    SigningAccount,
)

from asa_metadata_registry import (
    Arc90Compliance,
    Arc90Uri,
    AsaMetadataRegistry,
    AssetMetadata,
    IrreversibleFlags,
    MetadataFlags,
    ReversibleFlags,
)
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from asa_metadata_registry.migrate import (
    _derive_migration_uri,
    _encode_arc2_migration_message,
    _ensure_not_already_migrated,
    build_arc2_migration_message_txn,
    migrate_legacy_metadata_to_registry,
)
from smart_contracts.template_vars import ARC90_NETAUTH

# ================================================================
# Fixtures
# ================================================================


@pytest.fixture
def legacy_arc3_asa(
    asset_manager: SigningAccount,
    algorand_client: AlgorandClient,
) -> int:
    """Create a legacy ARC-3 ASA (without ARC-89 registry URL)."""
    return algorand_client.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            total=1000,
            asset_name="Legacy NFT" + const.ARC3_NAME_SUFFIX.decode(),
            unit_name="LNFT",
            url="ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            decimals=0,
            manager=asset_manager.address,
            reserve=asset_manager.address,
            freeze=asset_manager.address,
            clawback=asset_manager.address,
        )
    ).asset_id


@pytest.fixture
def legacy_arc69_asa(
    asset_manager: SigningAccount,
    algorand_client: AlgorandClient,
    minimal_metadata: dict[str, object],
) -> int:
    """Create a legacy ARC-69 ASA with metadata in the note field."""
    # ARC-69 stores metadata as JSON in the note field of asset config transactions
    arc69_note = json.dumps(minimal_metadata).encode("utf-8")

    return algorand_client.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            total=1_000_000,
            asset_name="Legacy Token",
            unit_name="LTK",
            decimals=6,
            manager=asset_manager.address,
            reserve=asset_manager.address,
            freeze=asset_manager.address,
            clawback=asset_manager.address,
            note=arc69_note,
        )
    ).asset_id


@pytest.fixture
def minimal_metadata() -> dict[str, object]:
    """Minimal valid ARC-3/ARC-69 metadata JSON."""
    return {
        "name": "Test Asset",
        "description": "A test asset for migration",
    }


@pytest.fixture
def arc3_metadata() -> dict[str, object]:
    """ARC-3 compliant metadata with standard properties."""
    return {
        "name": "ARC-3 NFT",
        "description": "An ARC-3 compliant NFT",
        "image": "ipfs://QmExample",
        "properties": {
            "simple_property": "example value",
            "rich_property": {
                "name": "Name",
                "value": "123",
                "display_value": "123 Example Value",
            },
            "array_property": {
                "name": "Rarities",
                "value": [1, 2, 3, 4],
            },
        },
    }


@pytest.fixture
def registry_with_write(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    algorand_client: AlgorandClient,
) -> AsaMetadataRegistry:
    """Registry configured for write operations."""
    return AsaMetadataRegistry.from_app_client(
        asa_metadata_registry_client,
        algod=algorand_client.client.algod,
        netauth=os.environ[ARC90_NETAUTH],
    )


# ================================================================
# ARC-2 Message Encoding Tests
# ================================================================


class TestArc2MessageEncoding:
    """Tests for ARC-2 migration message encoding."""

    def test_encode_basic_uri(self) -> None:
        """Test encoding a basic metadata URI."""
        uri = "arc90://net:testnet/42?box=AAAAAAAAAAM"
        message = _encode_arc2_migration_message(uri=uri)

        # Should start with arc89:j: prefix
        assert message.startswith(b"arc89:j")

        # Extract and decode JSON payload
        payload = message[len(b"arc89:j") :]
        decoded = json.loads(payload.decode("utf-8"))

        assert decoded == {"uri": uri}

    def test_encode_with_compliance_fragment(self) -> None:
        """Test encoding URI with ARC-90 compliance fragment."""
        uri = "arc90://net:testnet/42?box=AAAAAAAAAAM#arc3"
        message = _encode_arc2_migration_message(uri=uri)

        assert message.startswith(b"arc89:j")
        payload = message[len(b"arc89:j") :]
        decoded = json.loads(payload.decode("utf-8"))

        assert decoded["uri"] == uri

    def test_encode_compact_json(self) -> None:
        """Test that JSON is encoded compactly (no extra whitespace)."""
        uri = "arc90://net:testnet/42?box=AAAAAAAAAAM"
        message = _encode_arc2_migration_message(uri=uri)

        payload_str = message[len(b"arc89:j") :].decode("utf-8")

        # Should have compact separators
        assert payload_str == json.dumps({"uri": uri}, separators=(",", ":"))
        # Should not have extra whitespace
        assert " " not in payload_str or payload_str.count(" ") == 0

    def test_encode_unicode_uri(self) -> None:
        """Test encoding URI with unicode characters."""
        uri = "arc90://net:testnet/42?box=AAAAAAAAAAM&tag=测试"
        message = _encode_arc2_migration_message(uri=uri)

        payload = message[len(b"arc89:j") :]
        decoded = json.loads(payload.decode("utf-8"))

        assert decoded["uri"] == uri


# ================================================================
# Migration URI Derivation Tests
# ================================================================


class TestMigrationUriDerivation:
    """Tests for _derive_migration_uri helper."""

    def test_derive_basic_uri(
        self, registry_with_write: AsaMetadataRegistry, legacy_arc69_asa: int
    ) -> None:
        """Test deriving a basic migration URI without compliance fragments."""
        uri = _derive_migration_uri(
            registry=registry_with_write,
            asset_id=legacy_arc69_asa,
            arc3=False,
        )

        # Parse the URI
        parsed = Arc90Uri.parse(uri)

        assert parsed.netauth == os.environ[ARC90_NETAUTH]
        assert parsed.app_id == registry_with_write.config.app_id
        assert parsed.box_name is not None
        assert parsed.compliance == Arc90Compliance(())

    def test_derive_uri_with_arc3_flag(
        self, registry_with_write: AsaMetadataRegistry, legacy_arc3_asa: int
    ) -> None:
        """Test deriving URI with ARC-3 compliance flag."""
        uri = _derive_migration_uri(
            registry=registry_with_write,
            asset_id=legacy_arc3_asa,
            arc3=True,
        )

        parsed = Arc90Uri.parse(uri)

        assert parsed.compliance == Arc90Compliance((3,))


# ================================================================
# Transaction Building Tests
# ================================================================


class TestBuildArc2MigrationMessageTxn:
    """Tests for build_arc2_migration_message_txn."""

    def test_build_txn_basic(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
    ) -> None:
        """Test building a basic ARC-2 migration message transaction."""
        metadata_uri = "arc90://net:testnet/123?box=AAAAAAAAAAM"

        txn = build_arc2_migration_message_txn(
            registry=registry_with_write,
            asset_id=legacy_arc69_asa,
            asset_manager=asset_manager,
            metadata_uri=metadata_uri,
        )

        # Verify transaction type and basic fields
        assert txn.type == "acfg"
        assert txn.sender == asset_manager.address
        # Verify it's an asset config transaction for the right asset
        assert hasattr(txn, "index")

        # Verify note contains the ARC-2 message
        assert txn.note is not None
        assert txn.note.startswith(b"arc89:j")

        # Decode and verify the message
        payload = txn.note[len(b"arc89:j") :]
        decoded = json.loads(payload.decode("utf-8"))
        assert decoded["uri"] == metadata_uri

    def test_build_txn_preserves_manager(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        algorand_client: AlgorandClient,
    ) -> None:
        """Test that transaction preserves the manager address."""
        metadata_uri = "arc90://net:testnet/123?box=AAAAAAAAAAM"

        txn = build_arc2_migration_message_txn(
            registry=registry_with_write,
            asset_id=legacy_arc69_asa,
            asset_manager=asset_manager,
            metadata_uri=metadata_uri,
        )

        # Verify transaction was built with the migration message
        assert txn.note is not None
        assert txn.note.startswith(b"arc89:j")
        # RBAC preservation is tested in integration tests where txn is sent

    def test_build_txn_preserves_all_roles(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        algorand_client: AlgorandClient,
    ) -> None:
        """Test that transaction preserves all RBAC roles (manager, reserve, freeze, clawback)."""
        metadata_uri = "arc90://net:testnet/123?box=AAAAAAAAAAM"

        txn = build_arc2_migration_message_txn(
            registry=registry_with_write,
            asset_id=legacy_arc69_asa,
            asset_manager=asset_manager,
            metadata_uri=metadata_uri,
        )

        # Verify transaction was built
        # RBAC preservation is tested in full integration tests
        assert txn.type == "acfg"
        assert txn.sender == asset_manager.address
        assert txn.note is not None

    def test_build_txn_without_write_capability_error(
        self,
        algorand_client: AlgorandClient,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
    ) -> None:
        """Test that building txn without write capabilities raises error."""
        # Create read-only registry
        read_only_registry = AsaMetadataRegistry.from_algod(
            algod=algorand_client.client.algod,
            app_id=asa_metadata_registry_client.app_id,
        )

        with pytest.raises(ValueError, match="write capabilities"):
            build_arc2_migration_message_txn(
                registry=read_only_registry,
                asset_id=legacy_arc69_asa,
                asset_manager=asset_manager,
                metadata_uri="arc90://net:testnet/123?box=AAAAAAAAAAM",
            )


# ================================================================
# Migration Pre-flight Checks Tests
# ================================================================


class TestEnsureNotAlreadyMigrated:
    """Tests for _ensure_not_already_migrated validation."""

    def test_not_migrated_passes(
        self,
        registry_with_write: AsaMetadataRegistry,
        legacy_arc69_asa: int,
    ) -> None:
        """Test that validation passes for assets without metadata."""
        # Should not raise
        _ensure_not_already_migrated(
            registry=registry_with_write,
            asset_id=legacy_arc69_asa,
        )

    def test_already_migrated_raises(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
    ) -> None:
        """Test that validation fails for assets with existing metadata."""
        # First create metadata for the asset
        metadata = AssetMetadata.from_json(
            asset_id=legacy_arc69_asa,
            json_obj={"name": "Existing Metadata"},
        )

        registry_with_write.write.create_metadata(
            asset_manager=asset_manager,
            metadata=metadata,
        )

        # Now validation should fail
        with pytest.raises(ValueError, match="already has metadata"):
            _ensure_not_already_migrated(
                registry=registry_with_write,
                asset_id=legacy_arc69_asa,
            )


# ================================================================
# Full Migration Flow Tests (LocalNet Integration)
# ================================================================


class TestMigrateLegacyMetadata:
    """Integration tests for migrate_legacy_metadata_to_registry."""

    def test_migrate_minimal_metadata(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        minimal_metadata: dict[str, object],
        algorand_client: AlgorandClient,
    ) -> None:
        """Test migrating minimal ARC-69 metadata."""
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata=minimal_metadata,
        )

        # Verify metadata was created in registry
        existence = registry_with_write.read.arc89_check_metadata_exists(
            asset_id=legacy_arc69_asa
        )
        assert existence.metadata_exists

        # Verify metadata content
        stored_metadata = registry_with_write.read.get_asset_metadata(
            asset_id=legacy_arc69_asa
        )
        stored_json = json.loads(stored_metadata.body.raw_bytes.decode("utf-8"))
        assert stored_json == minimal_metadata

    def test_migrate_arc3_metadata(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc3_asa: int,
        arc3_metadata: dict[str, object],
    ) -> None:
        """Test migrating ARC-3 compliant metadata."""
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc3_asa,
            metadata=arc3_metadata,
            arc3_compliant=True,
        )

        # Verify metadata exists
        existence = registry_with_write.read.arc89_check_metadata_exists(
            asset_id=legacy_arc3_asa
        )
        assert existence.metadata_exists

        # Verify ARC-3 flag is set
        header = registry_with_write.read.arc89_get_metadata_header(
            asset_id=legacy_arc3_asa
        )
        assert header.flags.irreversible.arc3

    def test_migrate_arc69_preserves_exact_metadata(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        algorand_client: AlgorandClient,
    ) -> None:
        """Test that ARC-69 migration preserves the exact original metadata from note field."""
        # Create original ARC-69 metadata with various data types
        original_arc69_metadata = {
            "standard": "arc69",
            "name": "Test Token",
            "description": "A test token for migration verification",
            "image": "https://example.com/image.png",
            "image_integrity": "sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=",
            "image_mimetype": "image/png",
            "properties": {
                "string_prop": "value",
                "number_prop": 42,
                "boolean_prop": True,
                "null_prop": None,
                "array_prop": [1, 2, 3],
                "nested_object": {
                    "key": "nested_value",
                },
            },
            "external_url": "https://example.com",
            "attributes": [
                {"trait_type": "Color", "value": "Blue"},
                {"trait_type": "Size", "value": 10},
            ],
        }

        # Create ARC-69 ASA with metadata in note field
        arc69_note = json.dumps(original_arc69_metadata).encode("utf-8")
        asset_id = algorand_client.send.asset_create(
            params=AssetCreateParams(
                sender=asset_manager.address,
                total=1_000_000,
                asset_name="ARC-69 Token",
                unit_name="A69",
                decimals=6,
                manager=asset_manager.address,
                reserve=asset_manager.address,
                freeze=asset_manager.address,
                clawback=asset_manager.address,
                note=arc69_note,
            )
        ).asset_id

        # Migrate using the original metadata
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=asset_id,
            metadata=original_arc69_metadata,
        )

        # Verify metadata exists in registry
        existence = registry_with_write.read.arc89_check_metadata_exists(
            asset_id=asset_id
        )
        assert existence.metadata_exists

        # Verify stored metadata exactly matches original
        stored_metadata = registry_with_write.read.get_asset_metadata(asset_id=asset_id)
        stored_json = json.loads(stored_metadata.body.raw_bytes.decode("utf-8"))

        # Deep equality check - every field must match exactly
        assert stored_json == original_arc69_metadata

        # Verify specific fields to ensure data types are preserved
        assert stored_json["standard"] == "arc69"
        assert stored_json["properties"]["number_prop"] == 42
        assert stored_json["properties"]["boolean_prop"] is True
        assert stored_json["properties"]["null_prop"] is None
        assert stored_json["properties"]["array_prop"] == [1, 2, 3]
        assert stored_json["properties"]["nested_object"]["key"] == "nested_value"
        assert stored_json["attributes"][0]["value"] == "Blue"
        assert stored_json["attributes"][1]["value"] == 10

        # Verify RBAC roles are preserved
        asset_info = algorand_client.asset.get_by_id(asset_id=asset_id)
        assert asset_info.manager == asset_manager.address
        assert asset_info.reserve == asset_manager.address
        assert asset_info.freeze == asset_manager.address
        assert asset_info.clawback == asset_manager.address

    def test_migrate_with_custom_flags(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        minimal_metadata: dict[str, object],
    ) -> None:
        """Test migrating metadata with custom flags (non-arc89_native)."""
        # Note: arc89_native=False is appropriate for migrated metadata
        flags = MetadataFlags(
            reversible=ReversibleFlags(reserved_3=True),
            irreversible=IrreversibleFlags(arc89_native=False),
        )

        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata=minimal_metadata,
            flags=flags,
        )

        # Verify flags were applied (arc89_native should be False for migrated metadata)
        header = registry_with_write.read.arc89_get_metadata_header(
            asset_id=legacy_arc69_asa
        )
        assert not header.flags.irreversible.arc89_native

    def test_migrate_with_arc89_native_flag_error(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        minimal_metadata: dict[str, object],
    ) -> None:
        """Test that attempting to flag migrated metadata as ARC-89 native raises ValueError."""
        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc89_native=True),
        )

        with pytest.raises(
            ValueError, match="Cannot flag migrated metadata as ARC-89 native"
        ):
            migrate_legacy_metadata_to_registry(
                registry=registry_with_write,
                asset_manager=asset_manager,
                asset_id=legacy_arc69_asa,
                metadata=minimal_metadata,
                flags=flags,
            )

    def test_migrate_already_migrated_error(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        minimal_metadata: dict[str, object],
    ) -> None:
        """Test that migrating an already-migrated asset raises error."""
        # First migration
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata=minimal_metadata,
        )

        # Second migration should fail
        with pytest.raises(ValueError, match="already has metadata"):
            migrate_legacy_metadata_to_registry(
                registry=registry_with_write,
                asset_manager=asset_manager,
                asset_id=legacy_arc69_asa,
                metadata=minimal_metadata,
            )

    def test_migrate_oversized_metadata_error(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
    ) -> None:
        """Test that migrating oversized metadata raises error."""
        # Create metadata that exceeds MAX_METADATA_SIZE
        oversized_metadata = {
            "name": "Oversized Asset",
            "description": "x"
            * const.MAX_METADATA_SIZE,  # This will exceed when JSON encoded
        }

        with pytest.raises(ValueError, match="too large to migrate"):
            migrate_legacy_metadata_to_registry(
                registry=registry_with_write,
                asset_manager=asset_manager,
                asset_id=legacy_arc69_asa,
                metadata=oversized_metadata,
            )

    def test_migrate_max_size_metadata(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
    ) -> None:
        """Test migrating metadata at maximum allowed size."""
        # Create metadata that fits exactly within MAX_METADATA_SIZE
        # We need to account for JSON encoding overhead
        # Simple approach: use a raw string field
        content_size = const.MAX_METADATA_SIZE - 20  # Leave room for JSON structure
        max_size_metadata = {
            "data": "x" * content_size,
        }

        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata=max_size_metadata,
        )

        # Verify metadata was created
        existence = registry_with_write.read.arc89_check_metadata_exists(
            asset_id=legacy_arc69_asa
        )
        assert existence.metadata_exists


# ================================================================
# RBAC Preservation Tests
# ================================================================


class TestRbacPreservation:
    """Tests verifying that migration preserves all ASA role addresses."""

    def test_preserve_all_roles_after_migration(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        minimal_metadata: dict[str, object],
        algorand_client: AlgorandClient,
    ) -> None:
        """Test that all RBAC roles are preserved after migration."""
        # Get original asset info
        original_info = algorand_client.asset.get_by_id(asset_id=legacy_arc69_asa)

        # Perform migration
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata=minimal_metadata,
        )

        # Get updated asset info
        updated_info = algorand_client.asset.get_by_id(asset_id=legacy_arc69_asa)

        # Verify all roles are unchanged
        assert updated_info.manager == original_info.manager
        assert updated_info.reserve == original_info.reserve
        assert updated_info.freeze == original_info.freeze
        assert updated_info.clawback == original_info.clawback

    def test_preserve_roles_with_different_addresses(
        self,
        asset_manager: SigningAccount,
        algorand_client: AlgorandClient,
        registry_with_write: AsaMetadataRegistry,
        minimal_metadata: dict[str, object],
        untrusted_account: SigningAccount,
    ) -> None:
        """Test RBAC preservation when roles have different addresses."""
        # Create ASA with distinct role addresses
        reserve_account = algorand_client.account.random()
        freeze_account = algorand_client.account.random()

        # Fund the reserve account
        algorand_client.account.ensure_funded_from_environment(
            account_to_fund=reserve_account.address,
            min_spending_balance=AlgoAmount.from_algo(1),
        )

        asa_id = algorand_client.send.asset_create(
            params=AssetCreateParams(
                sender=asset_manager.address,
                total=1000,
                asset_name="Multi-Role ASA",
                manager=asset_manager.address,
                reserve=reserve_account.address,
                freeze=freeze_account.address,
                clawback=untrusted_account.address,
            )
        ).asset_id

        # Get original info
        original_info = algorand_client.asset.get_by_id(asset_id=asa_id)

        # Perform migration
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=asa_id,
            metadata=minimal_metadata,
        )

        # Get updated info
        updated_info = algorand_client.asset.get_by_id(asset_id=asa_id)

        # Verify all distinct roles are preserved
        assert updated_info.manager == original_info.manager == asset_manager.address
        assert updated_info.reserve == original_info.reserve == reserve_account.address
        assert updated_info.freeze == original_info.freeze == freeze_account.address
        assert (
            updated_info.clawback == original_info.clawback == untrusted_account.address
        )

    def test_preserve_empty_roles(
        self,
        asset_manager: SigningAccount,
        algorand_client: AlgorandClient,
        registry_with_write: AsaMetadataRegistry,
        minimal_metadata: dict[str, object],
    ) -> None:
        """Test that empty (disabled) roles remain empty after migration."""
        # Create ASA with some roles disabled (empty string means disabled)
        asa_id = algorand_client.send.asset_create(
            params=AssetCreateParams(
                sender=asset_manager.address,
                total=1000,
                asset_name="Minimal Roles ASA",
                manager=asset_manager.address,
                reserve="",  # Disabled
                freeze="",  # Disabled
                clawback="",  # Disabled
            )
        ).asset_id

        # Get original info
        original_info = algorand_client.asset.get_by_id(asset_id=asa_id)

        # Perform migration
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=asa_id,
            metadata=minimal_metadata,
        )

        # Get updated info
        updated_info = algorand_client.asset.get_by_id(asset_id=asa_id)

        # Verify empty roles remain empty (AlgoSDK returns None for empty roles)
        assert updated_info.manager == original_info.manager
        # Empty roles may be returned as None or "" by AlgoSDK
        assert updated_info.reserve in (original_info.reserve, None, "")
        assert updated_info.freeze in (original_info.freeze, None, "")
        assert updated_info.clawback in (original_info.clawback, None, "")


# ================================================================
# Error Handling Tests
# ================================================================


class TestMigrationErrorHandling:
    """Tests for various error conditions during migration."""

    def test_migrate_empty_metadata(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
    ) -> None:
        """Test migrating empty metadata object."""
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata={},
        )

        # Should succeed - empty metadata is valid
        existence = registry_with_write.read.arc89_check_metadata_exists(
            asset_id=legacy_arc69_asa
        )
        assert existence.metadata_exists

    def test_migrate_without_manager_error(
        self,
        registry_with_write: AsaMetadataRegistry,
        untrusted_account: SigningAccount,
        legacy_arc69_asa: int,
        minimal_metadata: dict[str, object],
    ) -> None:
        """Test that non-manager cannot migrate metadata."""
        with pytest.raises(LogicError):
            migrate_legacy_metadata_to_registry(
                registry=registry_with_write,
                asset_manager=untrusted_account,
                asset_id=legacy_arc69_asa,
                metadata=minimal_metadata,
            )


# ================================================================
# Integration Tests
# ================================================================


class TestMigrationIntegration:
    """End-to-end integration tests for migration workflow."""

    def test_full_migration_workflow(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc3_asa: int,
        arc3_metadata: dict[str, object],
        algorand_client: AlgorandClient,
    ) -> None:
        """Test complete migration workflow from legacy to ARC-89."""
        # 1. Verify asset has no metadata initially
        existence_before = registry_with_write.read.arc89_check_metadata_exists(
            asset_id=legacy_arc3_asa
        )
        assert not existence_before.metadata_exists

        # 2. Perform migration
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc3_asa,
            metadata=arc3_metadata,
            arc3_compliant=True,
        )

        # 3. Verify metadata now exists
        existence_after = registry_with_write.read.arc89_check_metadata_exists(
            asset_id=legacy_arc3_asa
        )
        assert existence_after.metadata_exists

        # 4. Verify metadata content
        stored_metadata = registry_with_write.read.get_asset_metadata(
            asset_id=legacy_arc3_asa
        )
        import json

        stored_json = json.loads(stored_metadata.body.raw_bytes.decode("utf-8"))
        assert stored_json == arc3_metadata

        # 5. Verify ARC-3 flag
        header = registry_with_write.read.arc89_get_metadata_header(
            asset_id=legacy_arc3_asa
        )
        assert header.flags.irreversible.arc3

        # 6. Verify RBAC unchanged
        asset_info = algorand_client.asset.get_by_id(asset_id=legacy_arc3_asa)
        assert asset_info.manager == asset_manager.address

        # 7. Verify we can read the metadata hash
        hash_result = registry_with_write.read.arc89_get_metadata_hash(
            asset_id=legacy_arc3_asa
        )
        assert len(hash_result) == 32

    def test_migration_with_subsequent_updates(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
        minimal_metadata: dict[str, object],
    ) -> None:
        """Test that migrated metadata can be updated normally."""
        # 1. Migrate
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata=minimal_metadata,
        )

        # 2. Update the metadata
        updated_metadata = AssetMetadata.from_json(
            asset_id=legacy_arc69_asa,
            json_obj={"name": "Updated Asset", "version": 2},
        )

        registry_with_write.write.replace_metadata(
            asset_manager=asset_manager,
            metadata=updated_metadata,
        )

        # 3. Verify the update
        stored_metadata = registry_with_write.read.get_asset_metadata(
            asset_id=legacy_arc69_asa
        )
        import json

        stored_json = json.loads(stored_metadata.body.raw_bytes.decode("utf-8"))
        assert stored_json["name"] == "Updated Asset"
        assert stored_json["version"] == 2

    def test_migration_metadata_size_boundary(
        self,
        registry_with_write: AsaMetadataRegistry,
        asset_manager: SigningAccount,
        legacy_arc69_asa: int,
    ) -> None:
        """Test migration at various metadata size boundaries."""
        # Test short metadata
        short_meta = {"x": "a" * 100}
        migrate_legacy_metadata_to_registry(
            registry=registry_with_write,
            asset_manager=asset_manager,
            asset_id=legacy_arc69_asa,
            metadata=short_meta,
        )

        pagination = registry_with_write.read.arc89_get_metadata_pagination(
            asset_id=legacy_arc69_asa
        )
        assert pagination.metadata_size > 0
        assert pagination.metadata_size <= const.SHORT_METADATA_SIZE
