"""
Unit tests for src.asa_metadata_registry.registry module.

Tests cover:
- RegistryConfig dataclass
- AsaMetadataRegistry initialization
- from_algod constructor
- from_app_client constructor with various configurations
- arc90_uri helper method
- write property access (with/without app_client)
- _make_generated_client_factory internals
- Error handling and edge cases
"""

from unittest.mock import Mock, patch

import pytest
from algosdk.v2client.algod import AlgodClient

from src.asa_metadata_registry import (
    Arc90Uri,
    AsaMetadataRegistry,
    AsaMetadataRegistryRead,
    AsaMetadataRegistryWrite,
    MissingAppClientError,
    RegistryConfig,
    RegistryResolutionError,
)
from src.asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from src.asa_metadata_registry.read.reader import (
    AlgodBoxReader,
    AsaMetadataRegistryAvmRead,
)

# ================================================================
# Fixtures
# ================================================================


@pytest.fixture
def mock_algod() -> Mock:
    """Create a mock AlgodClient."""
    return Mock(spec=AlgodClient)


@pytest.fixture
def mock_app_client() -> Mock:
    """Create a mock AsaMetadataRegistryClient."""
    mock = Mock(spec=AsaMetadataRegistryClient)
    mock.app_id = 12345
    return mock


@pytest.fixture
def mock_algorand() -> Mock:
    """Create a mock AlgoKit Algorand client."""
    return Mock()


# ================================================================
# RegistryConfig Tests
# ================================================================


class TestRegistryConfig:
    """Tests for RegistryConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default RegistryConfig values."""
        config = RegistryConfig()
        assert config.app_id is None
        assert config.netauth is None

    def test_config_with_app_id(self) -> None:
        """Test RegistryConfig with app_id."""
        config = RegistryConfig(app_id=12345)
        assert config.app_id == 12345
        assert config.netauth is None

    def test_config_with_netauth(self) -> None:
        """Test RegistryConfig with netauth."""
        config = RegistryConfig(netauth="net:testnet")
        assert config.app_id is None
        assert config.netauth == "net:testnet"

    def test_config_with_all_params(self) -> None:
        """Test RegistryConfig with all parameters."""
        config = RegistryConfig(app_id=12345, netauth="net:testnet")
        assert config.app_id == 12345
        assert config.netauth == "net:testnet"

    def test_config_is_frozen(self) -> None:
        """Test that RegistryConfig is immutable."""
        config = RegistryConfig(app_id=12345)
        with pytest.raises(AttributeError):
            config.app_id = 54321

    def test_config_equality(self) -> None:
        """Test RegistryConfig equality."""
        config1 = RegistryConfig(app_id=12345, netauth="net:testnet")
        config2 = RegistryConfig(app_id=12345, netauth="net:testnet")
        config3 = RegistryConfig(app_id=54321, netauth="net:testnet")
        assert config1 == config2
        assert config1 != config3


# ================================================================
# AsaMetadataRegistry.__init__ Tests
# ================================================================


class TestAsaMetadataRegistryInit:
    """Tests for AsaMetadataRegistry.__init__."""

    def test_init_minimal(self) -> None:
        """Test initialization with minimal config."""
        config = RegistryConfig()
        registry = AsaMetadataRegistry(config=config)
        assert registry.config == config
        assert registry._algod_reader is None
        assert registry._base_generated_client is None
        assert registry._generated_client_factory is None
        assert registry._avm_reader_factory is None
        assert registry._write is None
        assert isinstance(registry.read, AsaMetadataRegistryRead)

    def test_init_with_algod(self, mock_algod: Mock) -> None:
        """Test initialization with algod client."""
        config = RegistryConfig(app_id=12345)
        registry = AsaMetadataRegistry(config=config, algod=mock_algod)
        assert registry.config == config
        assert registry._algod_reader is not None
        assert isinstance(registry._algod_reader, AlgodBoxReader)
        assert registry._algod_reader.algod == mock_algod

    def test_init_with_app_client(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test initialization with app_client."""
        # Set up mock app_client with algorand attribute
        mock_app_client.algorand = mock_algorand

        config = RegistryConfig(app_id=12345)
        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry(config=config, app_client=mock_app_client)

            assert registry._base_generated_client == mock_app_client
            assert registry._generated_client_factory is not None
            assert registry._avm_reader_factory is not None
            assert registry._write is not None
            assert isinstance(registry._write, AsaMetadataRegistryWrite)

    def test_init_with_algod_and_app_client(
        self, mock_algod: Mock, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test initialization with both algod and app_client."""
        mock_app_client.algorand = mock_algorand

        config = RegistryConfig(app_id=12345, netauth="net:testnet")
        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry(
                config=config, algod=mock_algod, app_client=mock_app_client
            )

            assert registry._algod_reader is not None
            assert registry._base_generated_client == mock_app_client
            assert registry._write is not None

    def test_avm_reader_factory_creates_avm_read(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test that avm_reader_factory creates AsaMetadataRegistryAvmRead instances."""
        mock_app_client.algorand = mock_algorand

        config = RegistryConfig(app_id=12345)
        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_client_class = Mock(return_value=Mock())
            mock_module.AsaMetadataRegistryClient = mock_client_class
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry(config=config, app_client=mock_app_client)

            assert registry._avm_reader_factory is not None
            avm_reader = registry._avm_reader_factory(67890)
            assert isinstance(avm_reader, AsaMetadataRegistryAvmRead)
            mock_client_class.assert_called_once_with(
                algorand=mock_algorand,
                app_id=67890,
                default_sender=None,
                default_signer=None,
            )


# ================================================================
# AsaMetadataRegistry.write Property Tests
# ================================================================


class TestAsaMetadataRegistryWriteProperty:
    """Tests for AsaMetadataRegistry.write property."""

    def test_write_property_without_app_client_raises(self) -> None:
        """Test that accessing write without app_client raises MissingAppClientError."""
        config = RegistryConfig()
        registry = AsaMetadataRegistry(config=config)

        with pytest.raises(MissingAppClientError, match="Write operations require"):
            _ = registry.write

    def test_write_property_with_app_client_returns_writer(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test that accessing write with app_client returns AsaMetadataRegistryWrite."""
        mock_app_client.algorand = mock_algorand

        config = RegistryConfig(app_id=12345)
        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry(config=config, app_client=mock_app_client)

            writer = registry.write
            assert isinstance(writer, AsaMetadataRegistryWrite)
            # Subsequent calls should return the same instance
            assert registry.write is writer


# ================================================================
# AsaMetadataRegistry.from_algod Tests
# ================================================================


class TestAsaMetadataRegistryFromAlgod:
    """Tests for AsaMetadataRegistry.from_algod constructor."""

    def test_from_algod_with_app_id(self, mock_algod: Mock) -> None:
        """Test from_algod with app_id."""
        registry = AsaMetadataRegistry.from_algod(algod=mock_algod, app_id=12345)

        assert registry.config.app_id == 12345
        assert registry.config.netauth is None
        assert registry._algod_reader is not None
        assert registry._base_generated_client is None
        assert registry._write is None

    def test_from_algod_without_app_id(self, mock_algod: Mock) -> None:
        """Test from_algod without app_id."""
        registry = AsaMetadataRegistry.from_algod(algod=mock_algod, app_id=None)

        assert registry.config.app_id is None
        assert registry._algod_reader is not None

    def test_from_algod_creates_algod_reader(self, mock_algod: Mock) -> None:
        """Test that from_algod creates AlgodBoxReader."""
        registry = AsaMetadataRegistry.from_algod(algod=mock_algod, app_id=12345)

        assert isinstance(registry._algod_reader, AlgodBoxReader)
        assert registry._algod_reader.algod == mock_algod


# ================================================================
# AsaMetadataRegistry.from_app_client Tests
# ================================================================


class TestAsaMetadataRegistryFromAppClient:
    """Tests for AsaMetadataRegistry.from_app_client constructor."""

    def test_from_app_client_minimal(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test from_app_client with minimal arguments."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 12345

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(mock_app_client)

            assert registry.config.app_id == 12345
            assert registry.config.netauth is None
            assert registry._algod_reader is None
            assert registry._base_generated_client == mock_app_client

    def test_from_app_client_with_explicit_app_id(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test from_app_client with explicit app_id overrides client's app_id."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 12345

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(
                mock_app_client, app_id=67890
            )

            assert registry.config.app_id == 67890

    def test_from_app_client_with_netauth(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test from_app_client with netauth."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 12345

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(
                mock_app_client, netauth="net:testnet"
            )

            assert registry.config.netauth == "net:testnet"

    def test_from_app_client_with_algod(
        self, mock_app_client: Mock, mock_algod: Mock, mock_algorand: Mock
    ) -> None:
        """Test from_app_client with optional algod client."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 12345

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(
                mock_app_client, algod=mock_algod
            )

            assert registry._algod_reader is not None
            assert isinstance(registry._algod_reader, AlgodBoxReader)

    def test_from_app_client_infers_app_id_from_client(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test that app_id is inferred from client if not provided."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 99999

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(mock_app_client)

            assert registry.config.app_id == 99999

    def test_from_app_client_with_zero_app_id_becomes_none(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test that app_id of 0 from client becomes None."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 0

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(mock_app_client)

            assert registry.config.app_id is None

    def test_from_app_client_with_missing_app_id_attribute(
        self, mock_algorand: Mock
    ) -> None:
        """Test from_app_client when client lacks app_id attribute."""
        mock_client_no_app_id = Mock(spec=[])  # No attributes
        mock_client_no_app_id.algorand = mock_algorand

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(mock_client_no_app_id)

            assert registry.config.app_id is None

    def test_from_app_client_all_params(
        self, mock_app_client: Mock, mock_algod: Mock, mock_algorand: Mock
    ) -> None:
        """Test from_app_client with all parameters."""
        mock_app_client.algorand = mock_algorand

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(
                mock_app_client,
                algod=mock_algod,
                app_id=12345,
                netauth="net:testnet",
            )

            assert registry.config.app_id == 12345
            assert registry.config.netauth == "net:testnet"
            assert registry._algod_reader is not None
            assert registry._base_generated_client == mock_app_client


# ================================================================
# AsaMetadataRegistry.arc90_uri Tests
# ================================================================


class TestAsaMetadataRegistryArc90Uri:
    """Tests for AsaMetadataRegistry.arc90_uri method."""

    def test_arc90_uri_with_config_app_id(self) -> None:
        """Test arc90_uri using app_id from config."""
        config = RegistryConfig(app_id=12345, netauth="net:testnet")
        registry = AsaMetadataRegistry(config=config)

        uri = registry.arc90_uri(asset_id=999)

        assert isinstance(uri, Arc90Uri)
        assert uri.app_id == 12345
        assert uri.netauth == "net:testnet"
        # Verify the asset_id was applied to box_name
        assert uri.box_name is not None

    def test_arc90_uri_with_explicit_app_id(self) -> None:
        """Test arc90_uri with explicit app_id parameter."""
        config = RegistryConfig(app_id=12345)
        registry = AsaMetadataRegistry(config=config)

        uri = registry.arc90_uri(asset_id=999, app_id=67890)

        assert uri.app_id == 67890

    def test_arc90_uri_without_app_id_raises(self) -> None:
        """Test arc90_uri raises RegistryResolutionError when no app_id available."""
        config = RegistryConfig()  # No app_id
        registry = AsaMetadataRegistry(config=config)

        with pytest.raises(RegistryResolutionError, match="Cannot build ARC-90 URI"):
            registry.arc90_uri(asset_id=999)

    def test_arc90_uri_with_no_config_app_id_but_explicit(self) -> None:
        """Test arc90_uri works with explicit app_id even if config has none."""
        config = RegistryConfig()
        registry = AsaMetadataRegistry(config=config)

        uri = registry.arc90_uri(asset_id=999, app_id=12345)

        assert uri.app_id == 12345

    def test_arc90_uri_preserves_netauth(self) -> None:
        """Test arc90_uri preserves netauth from config."""
        config = RegistryConfig(app_id=12345, netauth="net:betanet")
        registry = AsaMetadataRegistry(config=config)

        uri = registry.arc90_uri(asset_id=777)

        assert uri.netauth == "net:betanet"

    def test_arc90_uri_with_none_netauth(self) -> None:
        """Test arc90_uri with None netauth (mainnet)."""
        config = RegistryConfig(app_id=12345)
        registry = AsaMetadataRegistry(config=config)

        uri = registry.arc90_uri(asset_id=777)

        assert uri.netauth is None


# ================================================================
# AsaMetadataRegistry._make_generated_client_factory Tests
# ================================================================


class TestMakeGeneratedClientFactory:
    """Tests for AsaMetadataRegistry._make_generated_client_factory."""

    def test_factory_creates_client_with_correct_params(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test that factory creates clients with correct parameters."""
        mock_app_client.algorand = mock_algorand

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_client_class = Mock(return_value=Mock())
            mock_module.AsaMetadataRegistryClient = mock_client_class
            mock_import.return_value = mock_module

            factory = AsaMetadataRegistry._make_generated_client_factory(
                base_client=mock_app_client
            )

            # Call factory with different app_ids
            _ = factory(12345)
            _ = factory(67890)

            assert mock_client_class.call_count == 2
            mock_client_class.assert_any_call(
                algorand=mock_algorand,
                app_id=12345,
                default_sender=None,
                default_signer=None,
            )
            mock_client_class.assert_any_call(
                algorand=mock_algorand,
                app_id=67890,
                default_sender=None,
                default_signer=None,
            )

    def test_factory_extracts_algorand_from_app_client(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test factory extracts algorand from base_client.app_client if needed."""
        # Mock base_client without direct algorand attribute
        mock_base = Mock(spec=[])
        mock_inner_app_client = Mock()
        mock_inner_app_client.algorand = mock_algorand
        mock_inner_app_client._default_sender = Mock()
        mock_inner_app_client._default_signer = Mock()
        mock_base.app_client = mock_inner_app_client

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_client_class = Mock(return_value=Mock())
            mock_module.AsaMetadataRegistryClient = mock_client_class
            mock_import.return_value = mock_module

            factory = AsaMetadataRegistry._make_generated_client_factory(
                base_client=mock_base
            )

            factory(12345)

            mock_client_class.assert_called_once_with(
                algorand=mock_algorand,
                app_id=12345,
                default_sender=mock_inner_app_client._default_sender,
                default_signer=mock_inner_app_client._default_signer,
            )

    def test_factory_raises_on_missing_client_class(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test factory raises MissingAppClientError if client class not found."""
        mock_app_client.algorand = mock_algorand

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock(spec=[])  # No AsaMetadataRegistryClient attribute
            mock_import.return_value = mock_module

            with pytest.raises(
                MissingAppClientError,
                match="Could not locate AsaMetadataRegistryClient",
            ):
                AsaMetadataRegistry._make_generated_client_factory(
                    base_client=mock_app_client
                )

    def test_factory_raises_on_missing_algorand(self) -> None:
        """Test factory raises MissingAppClientError if algorand client not found."""
        mock_base = Mock(spec=[])  # No algorand or app_client attributes

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            with pytest.raises(
                MissingAppClientError,
                match="does not expose an AlgoKit Algorand client",
            ):
                AsaMetadataRegistry._make_generated_client_factory(
                    base_client=mock_base
                )

    def test_factory_converts_app_id_to_int(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test that factory converts app_id to int."""
        mock_app_client.algorand = mock_algorand

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_client_class = Mock(return_value=Mock())
            mock_module.AsaMetadataRegistryClient = mock_client_class
            mock_import.return_value = mock_module

            factory = AsaMetadataRegistry._make_generated_client_factory(
                base_client=mock_app_client
            )

            # Call with various numeric types
            factory(12345)

            # Verify int() was called properly (app_id passed as int)
            mock_client_class.assert_called_with(
                algorand=mock_algorand,
                app_id=12345,
                default_sender=None,
                default_signer=None,
            )


# ================================================================
# Integration Tests
# ================================================================


class TestAsaMetadataRegistryIntegration:
    """Integration tests combining multiple components."""

    def test_read_only_workflow(self, mock_algod: Mock) -> None:
        """Test read-only workflow using from_algod."""
        registry = AsaMetadataRegistry.from_algod(algod=mock_algod, app_id=12345)

        # Should have read access
        assert isinstance(registry.read, AsaMetadataRegistryRead)

        # Should not have write access
        with pytest.raises(MissingAppClientError):
            _ = registry.write

        # Should be able to create URIs
        uri = registry.arc90_uri(asset_id=999)
        assert uri.app_id == 12345

    def test_read_write_workflow(
        self, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test read-write workflow using from_app_client."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 12345

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(mock_app_client)

            # Should have both read and write access
            assert isinstance(registry.read, AsaMetadataRegistryRead)
            assert isinstance(registry.write, AsaMetadataRegistryWrite)

            # Should be able to create URIs
            uri = registry.arc90_uri(asset_id=999)
            assert uri.app_id == 12345

    def test_hybrid_workflow_with_algod_and_app_client(
        self, mock_algod: Mock, mock_app_client: Mock, mock_algorand: Mock
    ) -> None:
        """Test workflow with both algod (for fast reads) and app_client (for writes)."""
        mock_app_client.algorand = mock_algorand
        mock_app_client.app_id = 12345

        with patch(
            "src.asa_metadata_registry.registry.import_generated_client"
        ) as mock_import:
            mock_module = Mock()
            mock_module.AsaMetadataRegistryClient = Mock
            mock_import.return_value = mock_module

            registry = AsaMetadataRegistry.from_app_client(
                mock_app_client, algod=mock_algod
            )

            # Should have algod reader for fast box reads
            assert registry._algod_reader is not None

            # Should have write access
            assert isinstance(registry.write, AsaMetadataRegistryWrite)

            # Should have read access that can use both algod and avm
            assert isinstance(registry.read, AsaMetadataRegistryRead)
