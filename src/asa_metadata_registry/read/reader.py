from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..algod import AlgodBoxReader
from ..codec import Arc90Uri
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
                pass

        # Fall back to spec defaults.
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

    def resolve_arc90_uri(
        self,
        *,
        asset_id: int | None = None,
        metadata_uri: str | None = None,
        app_id: int | None = None,
    ) -> Arc90Uri:
        """
        Resolve the ARC-90 URI for an asset, from either an explicit URI or the ASA's `url` field.

        If `metadata_uri` is provided, it's parsed and returned.

        If only `asset_id` is provided, the SDK attempts:
        1) ASA url -> ARC-89 partial URI completion (requires algod)
        2) configured `app_id` (if present)
        """
        if metadata_uri:
            parsed = Arc90Uri.parse(metadata_uri)
            if parsed.asset_id is None:
                raise InvalidArc90UriError(
                    "Metadata URI is partial; missing box value (asset id)"
                )
            return parsed

        if asset_id is None:
            raise RegistryResolutionError(
                "Either asset_id or metadata_uri must be provided"
            )

        # Try ASA url resolution first (best UX).
        if self.algod is not None:
            try:
                return self.algod.resolve_metadata_uri_from_asset(asset_id=asset_id)
            except InvalidArc90UriError:
                # Fall through to configured app id.
                pass

        resolved_app_id = app_id if app_id is not None else self.app_id
        if resolved_app_id is None:
            raise RegistryResolutionError(
                "Cannot resolve registry app_id from inputs or ASA url"
            )

        return Arc90Uri(
            netauth=None, app_id=int(resolved_app_id), box_name=None
        ).with_asset_id(asset_id)

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
    ) -> AssetMetadataRecord:
        """
        Fetch a full ARC-89 metadata record (header + metadata bytes).

        When `source=AUTO`, the SDK prefers BOX reads (fast) if algod is available; otherwise AVM.
        """
        uri = self.resolve_arc90_uri(
            asset_id=asset_id, metadata_uri=metadata_uri, app_id=app_id
        )
        if uri.asset_id is None:
            raise RegistryResolutionError("Resolved URI is partial (no asset id)")

        current_app_id = uri.app_id
        current_asset_id = uri.asset_id

        for _ in range(max_deprecation_hops + 1):
            record = self._get_asset_metadata_once(
                app_id=current_app_id,
                asset_id=current_asset_id,
                source=source,
                simulate=simulate,
            )
            if follow_deprecation and record.header.deprecated_by not in (
                0,
                current_app_id,
            ):
                current_app_id = int(record.header.deprecated_by)
                continue
            return record

        # exceeded
        return record

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

            # Fetch pages in batches (max 16 tx/group in Algorand; keep a safe default of 10).
            total_pages = pagination.total_pages
            last_round: int | None = None
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
                    if last_round is None:
                        last_round = paged.last_modified_round
                    elif paged.last_modified_round != last_round:
                        raise MetadataDriftError(
                            "Metadata changed between simulated page reads"
                        )
                    chunks.append(paged.page_content)

            body_raw_bytes = b"".join(chunks)
            # pagination.metadata_size is uint16; metadata bytes should match size.
            body = MetadataBody(body_raw_bytes[: pagination.metadata_size])

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
    ) -> bytes:
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
    ) -> bytes:
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
    ) -> bytes:
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
    ) -> bytes:
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
