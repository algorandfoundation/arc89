from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from algosdk.v2client.algod import AlgodClient

from ._generated.asa_metadata_registry_client import AsaMetadataRegistryClient
from .algod import AlgodBoxReader
from .app_client import import_generated_client
from .codec import Arc90Uri
from .errors import MissingAppClientError, RegistryResolutionError
from .read.avm import AsaMetadataRegistryAvmRead
from .read.reader import AsaMetadataRegistryRead
from .write.writer import AsaMetadataRegistryWrite


@dataclass(frozen=True, slots=True)
class RegistryConfig:
    """
    Configuration for an ASA Metadata Registry singleton instance.
    """

    app_id: int | None = None
    netauth: str | None = None  # e.g. "net:testnet" or None (mainnet/unspecified)


class AsaMetadataRegistry:
    """
    Facade over the ARC-89 read/write APIs.

    Construct using one of the helpers:
    - `from_algod(...)` (read-only, fast box reads)
    - `from_app_client(...)` (simulate + writes, optionally with algod for box reads)
    """

    def __init__(
        self,
        *,
        config: RegistryConfig,
        algod: AlgodClient | None = None,
        app_client: AsaMetadataRegistryClient | None = None,
    ) -> None:
        self.config = config

        self._algod_reader: AlgodBoxReader | None = (
            AlgodBoxReader(algod) if algod is not None else None
        )

        self._base_generated_client = app_client
        self._generated_client_factory: (
            Callable[[int], AsaMetadataRegistryClient] | None
        ) = None
        self._avm_reader_factory: Callable[[int], AsaMetadataRegistryAvmRead] | None = (
            None
        )
        self._write: AsaMetadataRegistryWrite | None = None

        if app_client is not None:
            # Build a factory that can create a generated client for arbitrary registry app_id,
            # using the same AlgoKit Algorand client instance.
            self._generated_client_factory = self._make_generated_client_factory(
                base_client=app_client
            )

            self._avm_reader_factory = lambda app_id: AsaMetadataRegistryAvmRead(
                self._generated_client_factory(int(app_id))  # type: ignore[misc]
            )

            self._write = AsaMetadataRegistryWrite(app_client)

        self.read = AsaMetadataRegistryRead(
            app_id=config.app_id,
            algod=self._algod_reader,
            avm_factory=self._avm_reader_factory,
        )

    @property
    def write(self) -> AsaMetadataRegistryWrite:
        if self._write is None:
            raise MissingAppClientError(
                "Write operations require a generated AppClient"
            )
        return self._write

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_algod(
        cls, *, algod: AlgodClient, app_id: int | None
    ) -> AsaMetadataRegistry:
        return cls(config=RegistryConfig(app_id=app_id), algod=algod, app_client=None)

    @classmethod
    def from_app_client(
        cls,
        app_client: AsaMetadataRegistryClient,
        *,
        algod: AlgodClient | None = None,
        app_id: int | None = None,
        netauth: str | None = None,
    ) -> AsaMetadataRegistry:
        # If app_id isn't provided, attempt to read from the generated client's app_id.
        inferred_app_id = app_id
        if inferred_app_id is None:
            inferred_app_id = int(getattr(app_client, "app_id", 0) or 0) or None
        return cls(
            config=RegistryConfig(app_id=inferred_app_id, netauth=netauth),
            algod=algod,
            app_client=app_client,
        )

    # ------------------------------------------------------------------
    # URI helpers
    # ------------------------------------------------------------------

    def arc90_uri(self, *, asset_id: int, app_id: int | None = None) -> Arc90Uri:
        """
        Build a full ARC-90 URI for an asset_id using configured netauth + app_id.

        Note: this is an *off-chain* convenience; if you need the exact string returned by the
        on-chain method, use `read.arc89_get_metadata_partial_uri(source=MetadataSource.AVM)`.
        """
        resolved_app_id = app_id if app_id is not None else self.config.app_id
        if resolved_app_id is None:
            raise RegistryResolutionError("Cannot build ARC-90 URI without app_id")
        return Arc90Uri(
            netauth=self.config.netauth, app_id=int(resolved_app_id), box_name=None
        ).with_asset_id(asset_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _make_generated_client_factory(
        *, base_client: AsaMetadataRegistryClient
    ) -> Callable[[int], AsaMetadataRegistryClient]:
        """
        Create a function that builds a new generated client instance for a given app_id.
        """
        mod = import_generated_client()
        client_cls = getattr(mod, "AsaMetadataRegistryClient", None)
        if client_cls is None:
            raise MissingAppClientError(
                "Could not locate AsaMetadataRegistryClient in generated module"
            )

        algorand = getattr(base_client, "algorand", None)
        if algorand is None:
            # Some versions store it on the internal app_client.
            app_client = getattr(base_client, "app_client", None)
            algorand = getattr(app_client, "algorand", None)
        if algorand is None:
            raise MissingAppClientError(
                "Base generated client does not expose an AlgoKit Algorand client"
            )

        # Extract default_sender and default_signer from the base client's app_client
        app_client = getattr(base_client, "app_client", None)
        default_sender = None
        default_signer = None
        if app_client is not None:
            default_sender = getattr(app_client, "_default_sender", None)
            default_signer = getattr(app_client, "_default_signer", None)

        def factory(app_id: int) -> Any:
            return client_cls(
                algorand=algorand,
                app_id=int(app_id),
                default_sender=default_sender,
                default_signer=default_signer,
            )

        return factory
