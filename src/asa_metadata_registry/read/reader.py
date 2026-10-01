from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..algod import AlgodBoxReader
from ..codec import Arc90Uri, complete_partial_asset_url
from ..deployments import (
    deployment_for_genesis,
    netauth_for_genesis,
    netauth_matches_genesis,
)
from ..errors import (
    InvalidArc90UriError,
    MetadataDriftError,
    MissingAppClientError,
    RegistryResolutionError,
)
from ..models import (
    AssetMetadataRecord,
    MbrDelta,
    MetadataBody,
    MetadataExistence,
    MetadataHeader,
    MetadataSlice,
    PaginatedMetadata,
    Pagination,
    RegistryParameters,
    get_default_registry_params,
)
from .avm import AsaMetadataRegistryAvmRead, SimulateOptions
from .box import AsaMetadataRegistryBoxRead


class MetadataSource(enum.Enum):
    """
    Where reads should come from.

    - AUTO: prefer BOX when possible (fast), otherwise AVM (simulate)
    - BOX: reconstruct from box value using Algod
    - AVM: use the generated AppClient + simulate for smart-contract parity
    """

    AUTO = "auto"
    BOX = "box"
    AVM = "avm"


@dataclass(slots=True)
class AsaMetadataRegistryRead:
    """
    Unified read API for ARC-89.

    Exposes:
    - `.box` for fast Algod box reconstruction
    - `.avm` for AVM-parity getters via simulate (if configured)
    - dispatcher methods that accept `source=...`
    """

    app_id: int | None
    algod: AlgodBoxReader | None = None
    avm_factory: Callable[[int], AsaMetadataRegistryAvmRead] | None = None
    netauth: str | None = None
    # Newer trusted ASA Metadata Registry versions, oldest first, after the trusted one
    trusted_versions: tuple[int, ...] = ()

    _params_cache: RegistryParameters | None = None

    def _require_app_id(self, *, app_id: int | None) -> int:
        resolved = app_id if app_id is not None else self.app_id
        if resolved is None:
            raise RegistryResolutionError(
                "Registry app_id is not configured and was not provided"
            )
        return int(resolved)

    def _get_params(self) -> RegistryParameters:
        if self._params_cache is not None:
            return self._params_cache

        # If we have AVM access, prefer on-chain params.
        if self.avm_factory is not None and self.app_id is not None:
            try:
                p = self.avm_factory(
                    self.app_id
                ).arc89_get_metadata_registry_parameters()
                object.__setattr__(self, "_params_cache", p)
                return p
            except Exception:
                # Fall back to the compiled defaults without caching, so later reads retry.
                return get_default_registry_params()

        p = get_default_registry_params()
        object.__setattr__(self, "_params_cache", p)
        return p

    # ------------------------------------------------------------------
    # Sub-readers
    # ------------------------------------------------------------------

    @property
    def box(self) -> AsaMetadataRegistryBoxRead:
        if self.algod is None:
            raise RuntimeError("BOX reader requires an algod client")
        return AsaMetadataRegistryBoxRead(
            algod=self.algod,
            app_id=self._require_app_id(app_id=None),
            params=self._get_params(),
        )

    def avm(self, *, app_id: int | None = None) -> AsaMetadataRegistryAvmRead:
        resolved = self._require_app_id(app_id=app_id)
        if self.avm_factory is None:
            raise MissingAppClientError(
                "AVM reader requires a generated AppClient (avm_factory)"
            )
        return self.avm_factory(resolved)

    # ------------------------------------------------------------------
    # Locator / discovery
    # ------------------------------------------------------------------

    def _genesis_hash(self) -> str | None:
        return self.algod.get_genesis_hash_b64() if self.algod is not None else None

    def _trusted_app_id(self, app_id: int | None) -> int | None:
        """Explicit app id, else the configured one, else the deployment for the network."""
        if app_id is not None:
            return int(app_id)
        if self.app_id is not None:
            return int(self.app_id)
        gh = self._genesis_hash()
        deployment = deployment_for_genesis(gh) if gh is not None else None
        return deployment.app_id if deployment is not None else None

    def _trusted_versions(self, app_id: int | None) -> tuple[int, ...]:
        """Trusted registry versions, oldest first: the trusted one, then `trusted_versions`."""
        trusted = self._trusted_app_id(app_id)
        head = () if trusted is None else (trusted,)
        return head + tuple(v for v in self.trusted_versions if v != trusted)

    def _check_trusted(self, uri: Arc90Uri, versions: tuple[int, ...]) -> None:
        """Reject a URI naming a registry or a network other than the trusted ones."""
        if not versions:
            raise RegistryResolutionError(
                "No trusted registry for this network: configure or pass app_id"
            )
        if uri.app_id not in versions:
            raise RegistryResolutionError(
                f"URI names registry {uri.app_id}, trusted registry is "
                + ", ".join(map(str, versions))
            )
        if self.netauth is not None:
            if uri.netauth != self.netauth:
                raise RegistryResolutionError(
                    f"URI netauth {uri.netauth!r} does not match {self.netauth!r}"
                )
            return
        gh = self._genesis_hash()
        if gh is not None and not netauth_matches_genesis(uri.netauth, gh):
            raise RegistryResolutionError(
                f"URI netauth {uri.netauth!r} does not denote the connected network"
            )

    def resolve_arc90_uri(
        self,
        *,
        asset_id: int | None = None,
        metadata_uri: str | None = None,
        app_id: int | None = None,
    ) -> Arc90Uri:
        """
        Resolve the ARC-90 URI for an asset, from an explicit URI or by the canonical look-up.

        The registry identity always comes from the trusted side (explicit `app_id`, the
        configured one, or the known deployment of the connected network): an explicit URI
        naming another registry or network is rejected; the ASA's Asset URL is not read.
        """
        versions = self._trusted_versions(app_id)
        trusted = versions[0] if versions else None

        if metadata_uri:
            parsed = Arc90Uri.parse(metadata_uri)
            if parsed.asset_id is None:
                raise InvalidArc90UriError(
                    "Metadata URI is partial; missing box value (asset id)"
                )
            self._check_trusted(parsed, versions)
            return parsed

        if asset_id is None:
            raise RegistryResolutionError(
                "Either asset_id or metadata_uri must be provided"
            )

        if trusted is None:
            raise RegistryResolutionError("Cannot resolve registry app_id from inputs")
        if self.algod is not None:
            # Canonical look-up: the ASA must exist; its Asset URL is informational.
            self.algod.get_asset_info(asset_id)
        netauth = self.netauth
        if netauth is None:
            gh = self._genesis_hash()
            netauth = netauth_for_genesis(gh) if gh is not None else None
        return Arc90Uri(netauth=netauth, app_id=trusted, box_name=None).with_asset_id(
            asset_id
        )

    def resolve_arc90_uri_from_asset_url(
        self, *, asset_id: int, asset_url: str, app_id: int | None = None
    ) -> Arc90Uri | None:
        """
        Resolve the ARC-90 URI from an Asset URL the client already holds, without fetching
        the ASA, or None if it is not an ARC-89 partial URI (use the canonical look-up).

        The Asset URL is informational: a URI naming another registry or network is rejected.
        """
        try:
            uri = Arc90Uri.parse(complete_partial_asset_url(asset_url, asset_id))
        except InvalidArc90UriError:
            return None
        self._check_trusted(uri, self._trusted_versions(app_id))
        return uri

    # ------------------------------------------------------------------
    # High-level read
    # ------------------------------------------------------------------

    def get_asset_metadata(
        self,
        *,
        asset_id: int | None = None,
        metadata_uri: str | None = None,
        app_id: int | None = None,
        source: MetadataSource = MetadataSource.AUTO,
        follow_deprecation: bool = True,
        max_deprecation_hops: int = 5,
        simulate: SimulateOptions | None = None,
        drift_retries: int = 2,
    ) -> AssetMetadataRecord:
        """
        Fetch a full ARC-89 metadata record (header + metadata bytes).

        When `source=AUTO`, the SDK prefers BOX reads (fast) if algod is available; otherwise AVM.
        Non-atomic reads that observe a Revision change are retried up to `drift_retries` times.
        The look-up and Deprecated By pointers stay within the trusted registry versions.
        """
        if drift_retries < 0 or max_deprecation_hops < 0:
            raise ValueError("drift_retries and max_deprecation_hops must be >= 0")
        uri = self.resolve_arc90_uri(
            asset_id=asset_id, metadata_uri=metadata_uri, app_id=app_id
        )
        if uri.asset_id is None:
            raise RegistryResolutionError("Resolved URI is partial (no asset id)")

        versions = self._trusted_versions(app_id)
        current_app_id = uri.app_id
        current_asset_id = uri.asset_id
        if metadata_uri is None and len(versions) > 1:
            # Canonical look-up: the oldest trusted version holding the record
            current_app_id = next(
                (
                    v
                    for v in versions
                    if self._holds_record(
                        app_id=v,
                        asset_id=current_asset_id,
                        source=source,
                        simulate=simulate,
                    )
                ),
                current_app_id,
            )

        for _ in range(max_deprecation_hops + 1):
            for attempt in range(drift_retries + 1):
                try:
                    record = self._get_asset_metadata_once(
                        app_id=current_app_id,
                        asset_id=current_asset_id,
                        source=source,
                        simulate=simulate,
                    )
                    break
                except MetadataDriftError:
                    if attempt == drift_retries:
                        raise
            target = int(record.header.deprecated_by)
            if follow_deprecation and target not in (0, current_app_id):
                if target not in versions:
                    raise RegistryResolutionError(
                        f"Deprecated By names untrusted registry {target}"
                    )
                current_app_id = target
                continue
            return record

        raise RegistryResolutionError(
            f"Deprecation chain exceeded {max_deprecation_hops} hops (last registry {current_app_id})"
        )

    def _holds_record(
        self,
        *,
        app_id: int,
        asset_id: int,
        source: MetadataSource,
        simulate: SimulateOptions | None,
    ) -> bool:
        if self.algod is not None and source != MetadataSource.AVM:
            box = self.algod.try_get_metadata_box(
                app_id=app_id, asset_id=asset_id, params=self._get_params()
            )
            return box is not None
        existence = self.avm(app_id=app_id).arc89_check_metadata_exists(
            asset_id=asset_id, simulate=simulate
        )
        return existence.metadata_exists

    def _get_asset_metadata_once(
        self,
        *,
        app_id: int,
        asset_id: int,
        source: MetadataSource,
        simulate: SimulateOptions | None,
    ) -> AssetMetadataRecord:
        params = self._get_params()

        if source == MetadataSource.AUTO:
            if self.algod is not None:
                source = MetadataSource.BOX
            elif self.avm_factory is not None:
                source = MetadataSource.AVM
            else:
                raise RegistryResolutionError(
                    "No read source available (need algod or avm)"
                )

        if source == MetadataSource.BOX:
            if self.algod is None:
                raise RuntimeError("BOX source selected but algod is not configured")
            return self.algod.get_asset_metadata_record(
                app_id=app_id, asset_id=asset_id, params=params
            )

        if source == MetadataSource.AVM:
            avm = self.avm(app_id=app_id)
            header = avm.arc89_get_metadata_header(asset_id=asset_id, simulate=simulate)
            pagination = avm.arc89_get_metadata_pagination(
                asset_id=asset_id, simulate=simulate
            )
            if pagination.revision != header.revision:
                raise MetadataDriftError(
                    "Metadata changed between header and pagination reads"
                )

            # Fetch pages in batches (max 16 tx/group in Algorand; keep a safe default of 10).
            total_pages = pagination.total_pages
            chunks: list[bytes] = []

            batch_size = 10
            for start in range(0, total_pages, batch_size):
                end = min(total_pages, start + batch_size)

                def build_batch(c: Any, s: int = start, e: int = end) -> None:
                    for i in range(s, e):
                        c.arc89_get_metadata(args=(asset_id, i), params=None)

                values = avm.simulate_many(
                    build_batch,
                    simulate=simulate,
                )
                for v in values:
                    paged = PaginatedMetadata.from_tuple(v)
                    if paged.revision != header.revision:
                        raise MetadataDriftError(
                            "Metadata changed between simulated page reads"
                        )
                    chunks.append(paged.page_content)

            body_raw_bytes = b"".join(chunks)
            if len(body_raw_bytes) != pagination.metadata_size:
                raise MetadataDriftError(
                    "Assembled metadata size does not match the pagination size"
                )
            body = MetadataBody(body_raw_bytes)

            return AssetMetadataRecord(
                app_id=app_id, asset_id=asset_id, header=header, body=body
            )

        raise ValueError(f"Unknown MetadataSource: {source}")

    # ------------------------------------------------------------------
    # Dispatcher versions of contract getters
    # ------------------------------------------------------------------

    def arc89_get_metadata_registry_parameters(
        self,
        *,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> RegistryParameters:
        if (
            source in (MetadataSource.AUTO, MetadataSource.AVM)
            and self.avm_factory is not None
            and self.app_id is not None
        ):
            p = self.avm(app_id=self.app_id).arc89_get_metadata_registry_parameters(
                simulate=simulate
            )
            return p
        # BOX cannot reconstruct these; fall back to cached/defaults.
        return self._get_params()

    def arc89_get_metadata_partial_uri(
        self,
        *,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> str:
        if (
            source in (MetadataSource.AUTO, MetadataSource.AVM)
            and self.avm_factory is not None
            and self.app_id is not None
        ):
            return self.avm(app_id=self.app_id).arc89_get_metadata_partial_uri(
                simulate=simulate
            )
        raise MissingAppClientError(
            "get_metadata_partial_uri requires AVM access (simulate)"
        )

    def arc89_get_metadata_mbr_delta(
        self,
        *,
        asset_id: int,
        new_size: int,
        source: MetadataSource = MetadataSource.AVM,
        simulate: SimulateOptions | None = None,
    ) -> MbrDelta:
        if source != MetadataSource.AVM:
            raise ValueError("MBR delta getter is AVM-only; use AVM source")
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_get_metadata_mbr_delta(
            asset_id=asset_id, new_size=new_size, simulate=simulate
        )

    def arc89_check_metadata_exists(
        self,
        *,
        asset_id: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> MetadataExistence:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            asa_exists, metadata_exists = self.box.arc89_check_metadata_exists(
                asset_id=asset_id
            )
            return MetadataExistence(
                asa_exists=asa_exists, metadata_exists=metadata_exists
            )
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_check_metadata_exists(asset_id=asset_id, simulate=simulate)

    def arc89_is_metadata_immutable(
        self,
        *,
        asset_id: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> bool:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_is_metadata_immutable(asset_id=asset_id)
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_is_metadata_immutable(asset_id=asset_id, simulate=simulate)

    def arc89_is_metadata_short(
        self,
        *,
        asset_id: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> tuple[bool, int]:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_is_metadata_short(asset_id=asset_id)
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_is_metadata_short(asset_id=asset_id, simulate=simulate)

    def arc89_get_metadata_header(
        self,
        *,
        asset_id: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> MetadataHeader:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_get_metadata_header(asset_id=asset_id)
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_get_metadata_header(asset_id=asset_id, simulate=simulate)

    def arc89_get_metadata_pagination(
        self,
        *,
        asset_id: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> Pagination:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_get_metadata_pagination(asset_id=asset_id)
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_get_metadata_pagination(asset_id=asset_id, simulate=simulate)

    def arc89_get_metadata(
        self,
        *,
        asset_id: int,
        page: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> PaginatedMetadata:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_get_metadata(asset_id=asset_id, page=page)
        return self.avm(app_id=self._require_app_id(app_id=None)).arc89_get_metadata(
            asset_id=asset_id, page=page, simulate=simulate
        )

    def arc89_get_metadata_slice(
        self,
        *,
        asset_id: int,
        offset: int,
        size: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> MetadataSlice:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_get_metadata_slice(
                asset_id=asset_id, offset=offset, size=size
            )
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_get_metadata_slice(
            asset_id=asset_id, offset=offset, size=size, simulate=simulate
        )

    def arc89_get_metadata_header_hash(
        self,
        *,
        asset_id: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> tuple[bytes, int]:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_get_metadata_header_hash(asset_id=asset_id)
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_get_metadata_header_hash(asset_id=asset_id, simulate=simulate)

    def arc89_get_metadata_page_hash(
        self,
        *,
        asset_id: int,
        page: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> tuple[bytes, int]:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_get_metadata_page_hash(asset_id=asset_id, page=page)
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_get_metadata_page_hash(asset_id=asset_id, page=page, simulate=simulate)

    def arc89_get_metadata_hash(
        self,
        *,
        asset_id: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> tuple[bytes, int]:
        if source == MetadataSource.BOX or (
            source == MetadataSource.AUTO and self.algod is not None
        ):
            return self.box.arc89_get_metadata_hash(asset_id=asset_id)
        return self.avm(
            app_id=self._require_app_id(app_id=None)
        ).arc89_get_metadata_hash(asset_id=asset_id, simulate=simulate)

    def arc89_get_metadata_string_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> str:
        # AUTO: prefer AVM for parity, but fall back to off-chain JSON if AVM not configured.
        if source == MetadataSource.AVM or (
            source == MetadataSource.AUTO and self.avm_factory is not None
        ):
            return self.avm(
                app_id=self._require_app_id(app_id=None)
            ).arc89_get_metadata_string_by_key(
                asset_id=asset_id, key=key, simulate=simulate
            )
        return self.box.get_string_by_key(asset_id=asset_id, key=key)

    def arc89_get_metadata_uint64_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> int:
        if source == MetadataSource.AVM or (
            source == MetadataSource.AUTO and self.avm_factory is not None
        ):
            return self.avm(
                app_id=self._require_app_id(app_id=None)
            ).arc89_get_metadata_uint64_by_key(
                asset_id=asset_id, key=key, simulate=simulate
            )
        return self.box.get_uint64_by_key(asset_id=asset_id, key=key)

    def arc89_get_metadata_object_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> str:
        if source == MetadataSource.AVM or (
            source == MetadataSource.AUTO and self.avm_factory is not None
        ):
            return self.avm(
                app_id=self._require_app_id(app_id=None)
            ).arc89_get_metadata_object_by_key(
                asset_id=asset_id, key=key, simulate=simulate
            )
        return self.box.get_object_by_key(asset_id=asset_id, key=key)

    def arc89_get_metadata_b64_bytes_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        b64_encoding: int,
        source: MetadataSource = MetadataSource.AUTO,
        simulate: SimulateOptions | None = None,
    ) -> bytes:
        if source == MetadataSource.AVM or (
            source == MetadataSource.AUTO and self.avm_factory is not None
        ):
            return self.avm(
                app_id=self._require_app_id(app_id=None)
            ).arc89_get_metadata_b64_bytes_by_key(
                asset_id=asset_id, key=key, b64_encoding=b64_encoding, simulate=simulate
            )
        return self.box.get_b64_bytes_by_key(
            asset_id=asset_id, key=key, b64_encoding=b64_encoding
        )
