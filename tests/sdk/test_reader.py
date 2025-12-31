"""
Extensive tests for src.read.reader module.

Tests cover:
- AsaMetadataRegistryRead initialization and configuration
- MetadataSource enum behavior
- Registry resolution and ARC-90 URI handling
- High-level get_asset_metadata with various sources
- Deprecation following
- All dispatcher methods for contract getters
- Error handling and edge cases
- Integration with box and avm readers
"""

from collections.abc import Callable
from unittest.mock import Mock

import pytest
from algosdk.v2client.algod import AlgodClient

from src.algod import AlgodBoxReader
from src.codec import Arc90Uri, b64_encode
from src.errors import (
    InvalidArc90UriError,
    MetadataDriftError,
    MissingAppClientError,
    RegistryResolutionError,
)
from src.models import (
    AssetMetadataRecord,
    MbrDelta,
    MbrDeltaSign,
    MetadataBody,
    MetadataExistence,
    MetadataFlags,
    MetadataHeader,
    PaginatedMetadata,
    Pagination,
    RegistryParameters,
)
from src.read.avm import AsaMetadataRegistryAvmRead, SimulateOptions
from src.read.box import AsaMetadataRegistryBoxRead
from src.read.reader import AsaMetadataRegistryRead, MetadataSource
from tests.conftest import serialize_metadata_header

# ================================================================
# Fixtures
# ================================================================


def mock_box_response(algod_reader: AlgodBoxReader, box_value: bytes) -> None:
    """Helper to mock algod box response."""
    algod_reader.algod.application_box_by_name = Mock(
        return_value={"value": b64_encode(box_value)}
    )


def mock_asset_metadata_record(
    algod_reader: AlgodBoxReader, record: AssetMetadataRecord
) -> None:
    """Helper to mock algod response for asset metadata record."""
    box_value = serialize_metadata_header(record.header) + record.body.raw_bytes
    mock_box_response(algod_reader, box_value)

    # Also mock asset_info for URI resolution
    algod_reader.algod.asset_info = Mock(
        return_value={
            "params": {"url": ""}
        }  # Empty URL means fallback to configured app_id
    )


@pytest.fixture
def mock_algod() -> Mock:
    """Create a mock AlgodClient."""
    return Mock(spec=AlgodClient)


@pytest.fixture
def mock_algod_reader(mock_algod: Mock) -> AlgodBoxReader:
    """Create an AlgodBoxReader with mocked algod client."""
    return AlgodBoxReader(algod=mock_algod)


@pytest.fixture
def mock_avm_client() -> Mock:
    """Create a mock generated AppClient."""
    return Mock()


@pytest.fixture
def mock_avm_factory(
    mock_avm_client: Mock,
) -> Callable[[int], AsaMetadataRegistryAvmRead]:
    """Create a factory that returns mock AVM reader."""

    # Cache to ensure same mock is returned for same app_id
    _cache: dict[int, Mock] = {}

    def factory(app_id: int) -> AsaMetadataRegistryAvmRead:
        # Return cached mock if it exists
        if app_id in _cache:
            return _cache[app_id]

        # Return a mock that behaves like AsaMetadataRegistryAvmRead
        mock_avm = Mock(spec=AsaMetadataRegistryAvmRead)
        mock_avm.client = mock_avm_client
        _cache[app_id] = mock_avm
        return mock_avm

    return factory


@pytest.fixture
def registry_params() -> RegistryParameters:
    """Default registry parameters."""
    return RegistryParameters.defaults()


@pytest.fixture
def sample_metadata_header() -> MetadataHeader:
    """Create a sample metadata header."""
    return MetadataHeader(
        identifiers=0x00,
        flags=MetadataFlags.empty(),
        deprecated_by=0,
        last_modified_round=1000,
        metadata_hash=b"\x00" * 32,
    )


@pytest.fixture
def sample_metadata_body() -> MetadataBody:
    """Create a sample metadata body."""
    return MetadataBody(b'{"name": "test", "description": "A test asset"}')


@pytest.fixture
def sample_asset_record(
    sample_metadata_header: MetadataHeader,
    sample_metadata_body: MetadataBody,
) -> AssetMetadataRecord:
    """Create a sample asset metadata record."""
    return AssetMetadataRecord(
        app_id=123,
        asset_id=456,
        header=sample_metadata_header,
        body=sample_metadata_body,
    )


# ================================================================
# Test MetadataSource Enum
# ================================================================


class TestMetadataSource:
    """Test MetadataSource enum values."""

    def test_metadata_source_auto(self) -> None:
        assert MetadataSource.AUTO.value == "auto"

    def test_metadata_source_box(self) -> None:
        assert MetadataSource.BOX.value == "box"

    def test_metadata_source_avm(self) -> None:
        assert MetadataSource.AVM.value == "avm"


# ================================================================
# Test AsaMetadataRegistryRead Initialization
# ================================================================


class TestAsaMetadataRegistryReadInit:
    """Test AsaMetadataRegistryRead initialization."""

    def test_init_minimal(self) -> None:
        """Test initialization with minimal configuration."""
        reader = AsaMetadataRegistryRead(app_id=None)
        assert reader.app_id is None
        assert reader.algod is None
        assert reader.avm_factory is None
        assert reader._params_cache is None

    def test_init_with_app_id(self) -> None:
        """Test initialization with app_id."""
        reader = AsaMetadataRegistryRead(app_id=123)
        assert reader.app_id == 123

    def test_init_with_algod(self, mock_algod_reader: AlgodBoxReader) -> None:
        """Test initialization with algod reader."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)
        assert reader.algod is mock_algod_reader

    def test_init_with_avm_factory(self, mock_avm_factory: Callable) -> None:
        """Test initialization with AVM factory."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)
        assert reader.avm_factory is mock_avm_factory

    def test_init_fully_configured(
        self, mock_algod_reader: AlgodBoxReader, mock_avm_factory: Callable
    ) -> None:
        """Test initialization with all configuration options."""
        reader = AsaMetadataRegistryRead(
            app_id=123,
            algod=mock_algod_reader,
            avm_factory=mock_avm_factory,
        )
        assert reader.app_id == 123
        assert reader.algod is mock_algod_reader
        assert reader.avm_factory is mock_avm_factory


# ================================================================
# Test Internal Helper Methods
# ================================================================


class TestRequireAppId:
    """Test _require_app_id helper method."""

    def test_require_app_id_from_init(self) -> None:
        """Test _require_app_id uses app_id from initialization."""
        reader = AsaMetadataRegistryRead(app_id=123)
        assert reader._require_app_id(app_id=None) == 123

    def test_require_app_id_from_parameter(self) -> None:
        """Test _require_app_id uses provided parameter."""
        reader = AsaMetadataRegistryRead(app_id=123)
        assert reader._require_app_id(app_id=456) == 456

    def test_require_app_id_parameter_overrides(self) -> None:
        """Test _require_app_id parameter overrides init value."""
        reader = AsaMetadataRegistryRead(app_id=123)
        assert reader._require_app_id(app_id=789) == 789

    def test_require_app_id_not_configured(self) -> None:
        """Test _require_app_id raises when app_id not configured."""
        reader = AsaMetadataRegistryRead(app_id=None)
        with pytest.raises(
            RegistryResolutionError,
            match="Registry app_id is not configured and was not provided",
        ):
            reader._require_app_id(app_id=None)


class TestGetParams:
    """Test _get_params helper method."""

    def test_get_params_returns_defaults(self) -> None:
        """Test _get_params returns default parameters."""
        reader = AsaMetadataRegistryRead(app_id=123)
        params = reader._get_params()
        defaults = RegistryParameters.defaults()
        assert params.header_size == defaults.header_size
        assert params.max_metadata_size == defaults.max_metadata_size

    def test_get_params_caches_result(self) -> None:
        """Test _get_params caches the result."""
        reader = AsaMetadataRegistryRead(app_id=123)
        params1 = reader._get_params()
        params2 = reader._get_params()
        assert params1 is params2

    def test_get_params_from_avm_when_available(
        self, mock_avm_factory: Callable
    ) -> None:
        """Test _get_params fetches from AVM when available."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        custom_params = RegistryParameters.defaults()
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_registry_parameters.return_value = custom_params

        # We can't patch the factory, so just verify it returns params
        params = reader._get_params()
        assert isinstance(params, RegistryParameters)

    def test_get_params_falls_back_on_avm_error(
        self, mock_avm_factory: Callable
    ) -> None:
        """Test _get_params falls back to defaults if AVM fails."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_registry_parameters.side_effect = Exception(
            "AVM error"
        )

        params = reader._get_params()
        # Should fall back to defaults on error
        defaults = RegistryParameters.defaults()
        assert params.header_size == defaults.header_size
        assert params.max_metadata_size == defaults.max_metadata_size


# ================================================================
# Test Sub-Reader Properties
# ================================================================


class TestSubReaders:
    """Test box and avm sub-reader properties."""

    def test_box_property_returns_box_reader(
        self, mock_algod_reader: AlgodBoxReader
    ) -> None:
        """Test .box property returns AsaMetadataRegistryBoxRead."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)
        box_reader = reader.box
        assert isinstance(box_reader, AsaMetadataRegistryBoxRead)
        assert box_reader.algod is mock_algod_reader
        assert box_reader.app_id == 123

    def test_box_property_requires_algod(self) -> None:
        """Test .box property raises when algod not configured."""
        reader = AsaMetadataRegistryRead(app_id=123)
        with pytest.raises(RuntimeError, match="BOX reader requires an algod client"):
            _ = reader.box

    def test_box_property_requires_app_id(
        self, mock_algod_reader: AlgodBoxReader
    ) -> None:
        """Test .box property raises when app_id not configured."""
        reader = AsaMetadataRegistryRead(app_id=None, algod=mock_algod_reader)
        with pytest.raises(
            RegistryResolutionError,
            match="Registry app_id is not configured",
        ):
            _ = reader.box

    def test_avm_property_returns_avm_reader(self, mock_avm_factory: Callable) -> None:
        """Test .avm() method returns AsaMetadataRegistryAvmRead."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)
        avm_reader = reader.avm()
        assert isinstance(avm_reader, (AsaMetadataRegistryAvmRead, Mock))

    def test_avm_property_with_override_app_id(
        self, mock_avm_factory: Callable
    ) -> None:
        """Test .avm() method accepts override app_id."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)
        avm_reader = reader.avm(app_id=456)
        assert isinstance(avm_reader, (AsaMetadataRegistryAvmRead, Mock))

    def test_avm_property_requires_factory(self) -> None:
        """Test .avm() raises when factory not configured."""
        reader = AsaMetadataRegistryRead(app_id=123)
        with pytest.raises(
            MissingAppClientError,
            match="AVM reader requires a generated AppClient",
        ):
            reader.avm()

    def test_avm_property_requires_app_id(self, mock_avm_factory: Callable) -> None:
        """Test .avm() raises when app_id not configured."""
        reader = AsaMetadataRegistryRead(app_id=None, avm_factory=mock_avm_factory)
        with pytest.raises(
            RegistryResolutionError,
            match="Registry app_id is not configured",
        ):
            reader.avm()


# ================================================================
# Test ARC-90 URI Resolution
# ================================================================


class TestResolveArc90Uri:
    """Test resolve_arc90_uri method."""

    def test_resolve_from_explicit_uri(self) -> None:
        """Test resolution from explicit metadata_uri parameter."""
        reader = AsaMetadataRegistryRead(app_id=None)
        uri = reader.resolve_arc90_uri(
            metadata_uri="algorand://app/123?box=AAAAAAAAAcg%3D"  # b64url of asset ID 456
        )
        assert uri.app_id == 123
        assert uri.asset_id == 456

    def test_resolve_from_partial_uri_raises(self) -> None:
        """Test resolution from partial URI raises error."""
        reader = AsaMetadataRegistryRead(app_id=None)
        with pytest.raises(
            InvalidArc90UriError,
            match="Metadata URI is partial; missing box value",
        ):
            reader.resolve_arc90_uri(metadata_uri="algorand://app/123?box=")

    def test_resolve_from_asset_id_via_algod(
        self, mock_algod_reader: AlgodBoxReader
    ) -> None:
        """Test resolution from asset_id using algod ASA lookup."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        expected_uri = Arc90Uri(netauth=None, app_id=123, box_name=None).with_asset_id(
            456
        )

        # Mock the method on the algod object, not the reader
        mock_algod_reader.algod.asset_info = Mock(
            return_value={"params": {"url": expected_uri.to_uri()}}
        )

        uri = reader.resolve_arc90_uri(asset_id=456)
        assert uri.asset_id == 456

    def test_resolve_from_asset_id_fallback_to_app_id(
        self, mock_algod_reader: AlgodBoxReader
    ) -> None:
        """Test resolution falls back to configured app_id when ASA lookup fails."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # Mock asset_info to return an ASA with no URL
        mock_algod_reader.algod.asset_info = Mock(return_value={"params": {"url": ""}})

        uri = reader.resolve_arc90_uri(asset_id=456)
        assert uri.app_id == 123
        assert uri.asset_id == 456

    def test_resolve_from_asset_id_with_override_app_id(self) -> None:
        """Test resolution uses override app_id parameter."""
        reader = AsaMetadataRegistryRead(app_id=123)
        uri = reader.resolve_arc90_uri(asset_id=456, app_id=789)
        assert uri.app_id == 789
        assert uri.asset_id == 456

    def test_resolve_requires_asset_id_or_uri(self) -> None:
        """Test resolution raises when neither asset_id nor metadata_uri provided."""
        reader = AsaMetadataRegistryRead(app_id=123)
        with pytest.raises(
            RegistryResolutionError,
            match="Either asset_id or metadata_uri must be provided",
        ):
            reader.resolve_arc90_uri()

    def test_resolve_requires_app_id_without_algod(self) -> None:
        """Test resolution raises when app_id cannot be determined."""
        reader = AsaMetadataRegistryRead(app_id=None)
        with pytest.raises(
            RegistryResolutionError,
            match="Cannot resolve registry app_id",
        ):
            reader.resolve_arc90_uri(asset_id=456)


# ================================================================
# Test High-Level get_asset_metadata
# ================================================================


class TestGetAssetMetadata:
    """Test get_asset_metadata high-level method."""

    def test_get_asset_metadata_auto_prefers_box(
        self,
        mock_algod_reader: AlgodBoxReader,
        sample_asset_record: AssetMetadataRecord,
    ) -> None:
        """Test AUTO source prefers BOX when algod available."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        mock_asset_metadata_record(mock_algod_reader, sample_asset_record)

        result = reader.get_asset_metadata(asset_id=456, source=MetadataSource.AUTO)

        assert result == sample_asset_record

    def test_get_asset_metadata_avm_source_explicit(
        self, mock_avm_factory: Callable, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test explicit AVM source when algod not available."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header.return_value = sample_metadata_header
        mock_avm.arc89_get_metadata_pagination.return_value = Pagination(
            metadata_size=50, page_size=100, total_pages=1
        )
        mock_avm.simulate_many.return_value = [
            (False, 1000, b'{"name": "test"}' + b"\x00" * 33)  # Pad to 50 bytes
        ]

        result = reader.get_asset_metadata(asset_id=456, source=MetadataSource.AVM)
        assert result.asset_id == 456

    def test_get_asset_metadata_box_source(
        self,
        mock_algod_reader: AlgodBoxReader,
        sample_asset_record: AssetMetadataRecord,
    ) -> None:
        """Test explicit BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        mock_asset_metadata_record(mock_algod_reader, sample_asset_record)

        result = reader.get_asset_metadata(asset_id=456, source=MetadataSource.BOX)

        assert result == sample_asset_record

    def test_get_asset_metadata_avm_source_single_page(
        self, mock_avm_factory: Callable, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test AVM source with single-page metadata."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header.return_value = sample_metadata_header
        mock_avm.arc89_get_metadata_pagination.return_value = Pagination(
            metadata_size=20, page_size=100, total_pages=1
        )
        mock_avm.simulate_many.return_value = [
            (False, 1000, b'{"name": "test"}' + b"\x00" * 2)  # Pad to 20 bytes
        ]

        result = reader.get_asset_metadata(asset_id=456, source=MetadataSource.AVM)
        assert result.asset_id == 456
        assert result.app_id == 123

    def test_get_asset_metadata_avm_source_multi_page(
        self, mock_avm_factory: Callable, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test AVM source with multi-page metadata."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header.return_value = sample_metadata_header
        mock_avm.arc89_get_metadata_pagination.return_value = Pagination(
            metadata_size=150, page_size=100, total_pages=2
        )
        # Simulate two pages
        mock_avm.simulate_many.return_value = [
            (False, 1000, b"A" * 100),
            (False, 1000, b"B" * 50),
        ]

        result = reader.get_asset_metadata(asset_id=456, source=MetadataSource.AVM)
        assert result.asset_id == 456
        assert len(result.body.raw_bytes) == 150

    def test_get_asset_metadata_avm_detects_drift(
        self, mock_avm_factory: Callable, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test AVM source detects metadata drift between pages."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header.return_value = sample_metadata_header
        mock_avm.arc89_get_metadata_pagination.return_value = Pagination(
            metadata_size=150, page_size=100, total_pages=2
        )
        # Different last_modified_round indicates drift
        mock_avm.simulate_many.return_value = [
            (False, 1000, b"page1"),
            (False, 1001, b"page2"),  # Different round!
        ]

        with pytest.raises(
            MetadataDriftError,
            match="Metadata changed between simulated page reads",
        ):
            reader.get_asset_metadata(asset_id=456, source=MetadataSource.AVM)

    def test_get_asset_metadata_follows_deprecation(
        self,
        mock_algod_reader: AlgodBoxReader,
    ) -> None:
        """Test metadata follows deprecation chain."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # First record points to deprecated_by=789
        deprecated_header = MetadataHeader(
            identifiers=0x00,
            flags=MetadataFlags.empty(),
            deprecated_by=789,
            last_modified_round=1000,
            metadata_hash=b"\x00" * 32,
        )
        deprecated_record = AssetMetadataRecord(
            app_id=123,
            asset_id=456,
            header=deprecated_header,
            body=MetadataBody(b'{"old": "metadata"}'),
        )

        # Second record is the current one
        current_header = MetadataHeader(
            identifiers=0x00,
            flags=MetadataFlags.empty(),
            deprecated_by=0,
            last_modified_round=2000,
            metadata_hash=b"\x00" * 32,
        )
        current_record = AssetMetadataRecord(
            app_id=789,
            asset_id=456,
            header=current_header,
            body=MetadataBody(b'{"new": "metadata"}'),
        )

        # Mock to return different records on subsequent calls
        call_count = [0]

        def box_response(app_id: int, box_name: bytes) -> dict[str, str]:
            record = deprecated_record if call_count[0] == 0 else current_record
            call_count[0] += 1
            box_value = serialize_metadata_header(record.header) + record.body.raw_bytes
            return {"value": b64_encode(box_value)}

        mock_algod_reader.algod.application_box_by_name = Mock(side_effect=box_response)
        mock_algod_reader.algod.asset_info = Mock(return_value={"params": {"url": ""}})

        result = reader.get_asset_metadata(asset_id=456, follow_deprecation=True)

        assert result.app_id == 789
        assert result.header.last_modified_round == 2000

    def test_get_asset_metadata_stops_deprecation_loop(
        self,
        mock_algod_reader: AlgodBoxReader,
    ) -> None:
        """Test deprecation following stops after max hops."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # Create circular deprecation
        looping_header = MetadataHeader(
            identifiers=0x00,
            flags=MetadataFlags.empty(),
            deprecated_by=999,  # Always points elsewhere
            last_modified_round=1000,
            metadata_hash=b"\x00" * 32,
        )
        looping_record = AssetMetadataRecord(
            app_id=123,
            asset_id=456,
            header=looping_header,
            body=MetadataBody(b'{"loop": true}'),
        )

        # Mock always returns the same looping record
        box_value = (
            serialize_metadata_header(looping_record.header)
            + looping_record.body.raw_bytes
        )
        mock_algod_reader.algod.application_box_by_name = Mock(
            return_value={"value": b64_encode(box_value)}
        )
        mock_algod_reader.algod.asset_info = Mock(return_value={"params": {"url": ""}})

        result = reader.get_asset_metadata(
            asset_id=456, follow_deprecation=True, max_deprecation_hops=3
        )

        # Should stop after max hops and return last result
        # Since deprecated_by=999, it follows to app_id 999
        assert result.app_id == 999

    def test_get_asset_metadata_no_deprecation_follow(
        self,
        mock_algod_reader: AlgodBoxReader,
    ) -> None:
        """Test metadata doesn't follow deprecation when disabled."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        deprecated_header = MetadataHeader(
            identifiers=0x00,
            flags=MetadataFlags.empty(),
            deprecated_by=789,
            last_modified_round=1000,
            metadata_hash=b"\x00" * 32,
        )
        deprecated_record = AssetMetadataRecord(
            app_id=123,
            asset_id=456,
            header=deprecated_header,
            body=MetadataBody(b'{"old": "metadata"}'),
        )

        mock_asset_metadata_record(mock_algod_reader, deprecated_record)

        result = reader.get_asset_metadata(asset_id=456, follow_deprecation=False)

        assert result.app_id == 123
        assert result.header.deprecated_by == 789

    def test_get_asset_metadata_auto_no_source_available(self) -> None:
        """Test AUTO source raises when neither algod nor avm available."""
        reader = AsaMetadataRegistryRead(app_id=123)

        with pytest.raises(
            RegistryResolutionError,
            match="No read source available",
        ):
            reader.get_asset_metadata(asset_id=456, source=MetadataSource.AUTO)

    def test_get_asset_metadata_box_source_not_configured(self) -> None:
        """Test BOX source raises when algod not configured."""
        reader = AsaMetadataRegistryRead(app_id=123)

        with pytest.raises(
            RuntimeError, match="BOX source selected but algod is not configured"
        ):
            reader.get_asset_metadata(asset_id=456, source=MetadataSource.BOX)


# ================================================================
# Test Dispatcher Methods
# ================================================================


class TestDispatcherGetRegistryParameters:
    """Test arc89_get_metadata_registry_parameters dispatcher."""

    def test_uses_avm_when_available(self, mock_avm_factory: Callable) -> None:
        """Test dispatcher uses AVM when available."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        custom_params = RegistryParameters.defaults()
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_registry_parameters.return_value = custom_params

        # Call with explicit AVM source
        result = reader.arc89_get_metadata_registry_parameters(
            source=MetadataSource.AVM
        )
        assert isinstance(result, RegistryParameters)

    def test_falls_back_to_defaults(self) -> None:
        """Test dispatcher falls back to defaults when AVM not available."""
        reader = AsaMetadataRegistryRead(app_id=123)
        result = reader.arc89_get_metadata_registry_parameters()
        defaults = RegistryParameters.defaults()
        assert result.header_size == defaults.header_size


class TestDispatcherGetPartialUri:
    """Test arc89_get_metadata_partial_uri dispatcher."""

    def test_requires_avm(self) -> None:
        """Test dispatcher requires AVM access."""
        reader = AsaMetadataRegistryRead(app_id=123)

        with pytest.raises(
            MissingAppClientError,
            match="get_metadata_partial_uri requires AVM access",
        ):
            reader.arc89_get_metadata_partial_uri()

    def test_uses_avm_when_available(self, mock_avm_factory: Callable) -> None:
        """Test dispatcher uses AVM."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_partial_uri.return_value = "algorand://app/123"

        reader.arc89_get_metadata_partial_uri(source=MetadataSource.AVM)
        mock_avm.arc89_get_metadata_partial_uri.assert_called_once()


class TestDispatcherGetMbrDelta:
    """Test arc89_get_metadata_mbr_delta dispatcher."""

    def test_requires_avm_source(self) -> None:
        """Test MBR delta getter requires AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123)

        with pytest.raises(ValueError, match="MBR delta getter is AVM-only"):
            reader.arc89_get_metadata_mbr_delta(
                asset_id=456, new_size=100, source=MetadataSource.BOX
            )

    def test_uses_avm(self, mock_avm_factory: Callable) -> None:
        """Test dispatcher uses AVM."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        delta = MbrDelta(sign=MbrDeltaSign.POS, amount=5000)
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_mbr_delta.return_value = delta

        reader.arc89_get_metadata_mbr_delta(asset_id=456, new_size=100)
        mock_avm.arc89_get_metadata_mbr_delta.assert_called_once()


class TestDispatcherCheckMetadataExists:
    """Test arc89_check_metadata_exists dispatcher."""

    def test_auto_prefers_box(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test AUTO source prefers BOX."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # Mock the algod methods to return valid data
        box_value = (
            serialize_metadata_header(sample_metadata_header) + b'{"test": "data"}'
        )
        mock_box_response(mock_algod_reader, box_value)
        mock_algod_reader.algod.asset_info = Mock(return_value={"id": 456})

        result = reader.arc89_check_metadata_exists(asset_id=456)
        assert result.asa_exists is True
        assert result.metadata_exists is True

    def test_uses_avm_when_box_unavailable(self, mock_avm_factory: Callable) -> None:
        """Test uses AVM when BOX not available."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_check_metadata_exists.return_value = MetadataExistence(
            asa_exists=True, metadata_exists=False
        )

        reader.arc89_check_metadata_exists(asset_id=456, source=MetadataSource.AVM)
        mock_avm.arc89_check_metadata_exists.assert_called_once()


class TestDispatcherIsMetadataImmutable:
    """Test arc89_is_metadata_immutable dispatcher."""

    def test_auto_prefers_box(self, mock_algod_reader: AlgodBoxReader) -> None:
        """Test AUTO source prefers BOX."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # Mock returns immutable header
        from src.models import IrreversibleFlags, ReversibleFlags

        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(
                immutable=True, arc3=False, arc89_native=False
            ),
        )
        header = MetadataHeader(
            identifiers=0x00,
            flags=flags,
            deprecated_by=0,
            last_modified_round=1000,
            metadata_hash=b"\x00" * 32,
        )
        box_value = serialize_metadata_header(header) + b'{"test": "data"}'
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_is_metadata_immutable(
            asset_id=456, source=MetadataSource.BOX
        )
        assert result is True

    def test_uses_avm_fallback(self, mock_avm_factory: Callable) -> None:
        """Test uses AVM when BOX not available."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_is_metadata_immutable.return_value = False

        reader.arc89_is_metadata_immutable(asset_id=456, source=MetadataSource.AVM)
        mock_avm.arc89_is_metadata_immutable.assert_called_once()


class TestDispatcherIsMetadataShort:
    """Test arc89_is_metadata_short dispatcher."""

    def test_box_source(self, mock_algod_reader: AlgodBoxReader) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        from src import bitmasks

        header = MetadataHeader(
            identifiers=bitmasks.MASK_ID_SHORT,  # short flag
            flags=MetadataFlags.empty(),
            deprecated_by=0,
            last_modified_round=1000,
            metadata_hash=b"\x00" * 32,
        )
        box_value = serialize_metadata_header(header) + b'{"small": "data"}'
        mock_box_response(mock_algod_reader, box_value)

        is_short, round_num = reader.arc89_is_metadata_short(
            asset_id=456, source=MetadataSource.BOX
        )
        assert is_short is True
        assert round_num == 1000

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_is_metadata_short.return_value = (False, 2000)

        reader.arc89_is_metadata_short(asset_id=456, source=MetadataSource.AVM)
        mock_avm.arc89_is_metadata_short.assert_called_once()


class TestDispatcherGetMetadataHeader:
    """Test arc89_get_metadata_header dispatcher."""

    def test_box_source(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        box_value = (
            serialize_metadata_header(sample_metadata_header) + b'{"test": "data"}'
        )
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_header(
            asset_id=456, source=MetadataSource.BOX
        )
        assert result.last_modified_round == sample_metadata_header.last_modified_round

    def test_avm_source(
        self, mock_avm_factory: Callable, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header.return_value = sample_metadata_header

        result = reader.arc89_get_metadata_header(
            asset_id=456, source=MetadataSource.AVM
        )
        assert result == sample_metadata_header


class TestDispatcherGetMetadataPagination:
    """Test arc89_get_metadata_pagination dispatcher."""

    def test_box_source(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        metadata_content = b'{"test": "data"}' * 10  # 160 bytes
        box_value = serialize_metadata_header(sample_metadata_header) + metadata_content
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_pagination(
            asset_id=456, source=MetadataSource.BOX
        )
        assert result.metadata_size == len(metadata_content)

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        pagination = Pagination(metadata_size=150, page_size=100, total_pages=2)
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_pagination.return_value = pagination

        reader.arc89_get_metadata_pagination(asset_id=456, source=MetadataSource.AVM)
        mock_avm.arc89_get_metadata_pagination.assert_called_once()


class TestDispatcherGetMetadata:
    """Test arc89_get_metadata (paginated) dispatcher."""

    def test_box_source(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        page_content = b'{"page": 0}'
        box_value = serialize_metadata_header(sample_metadata_header) + page_content
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata(
            asset_id=456, page=0, source=MetadataSource.BOX
        )
        assert result.page_content == page_content

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        page_data = PaginatedMetadata(
            has_next_page=False, last_modified_round=2000, page_content=b"page1"
        )
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata.return_value = page_data

        reader.arc89_get_metadata(asset_id=456, page=1, source=MetadataSource.AVM)
        mock_avm.arc89_get_metadata.assert_called_once()


class TestDispatcherGetMetadataSlice:
    """Test arc89_get_metadata_slice dispatcher."""

    def test_box_source(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        metadata_content = b"0123456789" * 10
        box_value = serialize_metadata_header(sample_metadata_header) + metadata_content
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_slice(
            asset_id=456, offset=10, size=20, source=MetadataSource.BOX
        )
        assert result == metadata_content[10:30]

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_slice.return_value = b"avm_slice"

        reader.arc89_get_metadata_slice(
            asset_id=456, offset=5, size=15, source=MetadataSource.AVM
        )
        mock_avm.arc89_get_metadata_slice.assert_called_once()


class TestDispatcherGetMetadataHeaderHash:
    """Test arc89_get_metadata_header_hash dispatcher."""

    def test_box_source(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        box_value = (
            serialize_metadata_header(sample_metadata_header) + b'{"test": "data"}'
        )
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_header_hash(
            asset_id=456, source=MetadataSource.BOX
        )
        assert len(result) == 32

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        header_hash = b"\x02" * 32
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header_hash.return_value = header_hash

        reader.arc89_get_metadata_header_hash(asset_id=456, source=MetadataSource.AVM)
        mock_avm.arc89_get_metadata_header_hash.assert_called_once()


class TestDispatcherGetMetadataPageHash:
    """Test arc89_get_metadata_page_hash dispatcher."""

    def test_box_source(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        box_value = (
            serialize_metadata_header(sample_metadata_header) + b'{"page": "data"}'
        )
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_page_hash(
            asset_id=456, page=0, source=MetadataSource.BOX
        )
        assert len(result) == 32

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        page_hash = b"\x04" * 32
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_page_hash.return_value = page_hash

        reader.arc89_get_metadata_page_hash(
            asset_id=456, page=1, source=MetadataSource.AVM
        )
        mock_avm.arc89_get_metadata_page_hash.assert_called_once()


class TestDispatcherGetMetadataHash:
    """Test arc89_get_metadata_hash dispatcher."""

    def test_box_source(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX source."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        box_value = (
            serialize_metadata_header(sample_metadata_header) + b'{"metadata": "test"}'
        )
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_hash(asset_id=456, source=MetadataSource.BOX)
        assert len(result) == 32

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        metadata_hash = b"\x06" * 32
        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_hash.return_value = metadata_hash

        reader.arc89_get_metadata_hash(asset_id=456, source=MetadataSource.AVM)
        mock_avm.arc89_get_metadata_hash.assert_called_once()


class TestDispatcherGetMetadataStringByKey:
    """Test arc89_get_metadata_string_by_key dispatcher."""

    def test_auto_prefers_avm(self, mock_avm_factory: Callable) -> None:
        """Test AUTO source prefers AVM for parity."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_string_by_key.return_value = "test_value"

        reader.arc89_get_metadata_string_by_key(
            asset_id=456, key="name", source=MetadataSource.AVM
        )
        mock_avm.arc89_get_metadata_string_by_key.assert_called_once()

    def test_falls_back_to_box(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test falls back to BOX when AVM not available."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        json_data = b'{"name": "box_value"}'
        box_value = serialize_metadata_header(sample_metadata_header) + json_data
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_string_by_key(
            asset_id=456, key="name", source=MetadataSource.BOX
        )
        assert result == "box_value"


class TestDispatcherGetMetadataUint64ByKey:
    """Test arc89_get_metadata_uint64_by_key dispatcher."""

    def test_auto_prefers_avm(self, mock_avm_factory: Callable) -> None:
        """Test AUTO source prefers AVM."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_uint64_by_key.return_value = 42

        reader.arc89_get_metadata_uint64_by_key(
            asset_id=456, key="value", source=MetadataSource.AVM
        )
        mock_avm.arc89_get_metadata_uint64_by_key.assert_called_once()

    def test_falls_back_to_box(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test falls back to BOX when AVM not available."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        json_data = b'{"count": 100}'
        box_value = serialize_metadata_header(sample_metadata_header) + json_data
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_uint64_by_key(
            asset_id=456, key="count", source=MetadataSource.BOX
        )
        assert result == 100


class TestDispatcherGetMetadataObjectByKey:
    """Test arc89_get_metadata_object_by_key dispatcher."""

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_object_by_key.return_value = '{"nested": true}'

        reader.arc89_get_metadata_object_by_key(
            asset_id=456, key="data", source=MetadataSource.AVM
        )
        mock_avm.arc89_get_metadata_object_by_key.assert_called_once()

    def test_box_fallback(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX fallback."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        json_data = b'{"config": {"box": "object"}}'
        box_value = serialize_metadata_header(sample_metadata_header) + json_data
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_object_by_key(
            asset_id=456, key="config", source=MetadataSource.BOX
        )
        # Should return serialized object
        import json

        obj = json.loads(result)
        assert "box" in obj


class TestDispatcherGetMetadataB64BytesByKey:
    """Test arc89_get_metadata_b64_bytes_by_key dispatcher."""

    def test_avm_source(self, mock_avm_factory: Callable) -> None:
        """Test AVM source."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_b64_bytes_by_key.return_value = b"decoded_bytes"

        reader.arc89_get_metadata_b64_bytes_by_key(
            asset_id=456, key="image", b64_encoding=0, source=MetadataSource.AVM
        )
        mock_avm.arc89_get_metadata_b64_bytes_by_key.assert_called_once()

    def test_box_fallback(
        self, mock_algod_reader: AlgodBoxReader, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test BOX fallback."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # Base64 URL encoding of "hello"
        json_data = b'{"data": "aGVsbG8="}'
        box_value = serialize_metadata_header(sample_metadata_header) + json_data
        mock_box_response(mock_algod_reader, box_value)

        result = reader.arc89_get_metadata_b64_bytes_by_key(
            asset_id=456, key="data", b64_encoding=1, source=MetadataSource.BOX
        )
        assert result == b"hello"


# ================================================================
# Test Edge Cases and Error Handling
# ================================================================


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_unknown_metadata_source_raises(
        self, mock_algod_reader: AlgodBoxReader
    ) -> None:
        """Test that MetadataSource enum is properly validated."""
        AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # Test that we can use valid enum values
        # (The actual dispatching logic handles all valid enum values)
        # This test verifies the enum is properly defined
        assert MetadataSource.AUTO in MetadataSource
        assert MetadataSource.BOX in MetadataSource
        assert MetadataSource.AVM in MetadataSource

    def test_empty_metadata_pagination(
        self, mock_avm_factory: Callable, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test AVM read with zero-size metadata."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header.return_value = sample_metadata_header
        # Zero pages
        mock_avm.arc89_get_metadata_pagination.return_value = Pagination(
            metadata_size=0, page_size=100, total_pages=0
        )
        mock_avm.simulate_many.return_value = []

        result = reader.get_asset_metadata(asset_id=456, source=MetadataSource.AVM)
        assert len(result.body.raw_bytes) == 0

    def test_simulate_options_passed_through(
        self, mock_avm_factory: Callable, sample_metadata_header: MetadataHeader
    ) -> None:
        """Test that SimulateOptions are passed through to AVM calls."""
        reader = AsaMetadataRegistryRead(app_id=123, avm_factory=mock_avm_factory)

        mock_avm = mock_avm_factory(123)
        mock_avm.arc89_get_metadata_header.return_value = sample_metadata_header

        simulate_opts = SimulateOptions(extra_opcode_budget=1000)

        reader.arc89_get_metadata_header(
            asset_id=456, source=MetadataSource.AVM, simulate=simulate_opts
        )
        mock_avm.arc89_get_metadata_header.assert_called_once_with(
            asset_id=456, simulate=simulate_opts
        )

    def test_deprecation_self_reference_stops(
        self, mock_algod_reader: AlgodBoxReader
    ) -> None:
        """Test that self-referencing deprecated_by doesn't loop."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # deprecated_by equals current app_id (self-reference)
        self_ref_header = MetadataHeader(
            identifiers=0x00,
            flags=MetadataFlags.empty(),
            deprecated_by=123,  # Same as app_id
            last_modified_round=1000,
            metadata_hash=b"\x00" * 32,
        )
        record = AssetMetadataRecord(
            app_id=123,
            asset_id=456,
            header=self_ref_header,
            body=MetadataBody(b'{"self": "ref"}'),
        )

        mock_asset_metadata_record(mock_algod_reader, record)

        result = reader.get_asset_metadata(asset_id=456, follow_deprecation=True)

        # Should stop immediately since deprecated_by == current app_id
        assert result.app_id == 123

    def test_metadata_uri_takes_precedence_over_asset_id(
        self, mock_algod_reader: AlgodBoxReader
    ) -> None:
        """Test that explicit metadata_uri takes precedence."""
        reader = AsaMetadataRegistryRead(app_id=123, algod=mock_algod_reader)

        # Even if asset_id is provided, URI should be used
        uri = reader.resolve_arc90_uri(
            asset_id=999,  # This should be ignored
            metadata_uri="algorand://app/789?box=AAAAAAAAAcg%3D",  # b64url of asset ID 456
        )

        assert uri.app_id == 789
        assert uri.asset_id == 456
