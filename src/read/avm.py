from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..errors import MissingAppClientError
from ..generated.asa_metadata_registry_client import AsaMetadataRegistryClient
from ..models import (
    MbrDelta,
    MetadataExistence,
    MetadataHeader,
    PaginatedMetadata,
    Pagination,
    RegistryParameters,
)


@dataclass(frozen=True, slots=True)
class SimulateOptions:
    """
    Options passed through to AlgoKit's `AtomicTransactionComposer.simulate()`.

    The generated client's composer has a signature like:

        simulate(
            allow_more_logs: bool | None = None,
            allow_empty_signatures: bool | None = None,
            allow_unnamed_resources: bool | None = None,
            extra_opcode_budget: int | None = None,
            exec_trace_config: SimulateTraceConfig | None = None,
            simulation_round: int | None = None,
            skip_signatures: bool | None = None,
        )

    `exec_trace_config` is intentionally typed as `Any` so this SDK stays light and portable.
    """

    allow_more_logs: bool | None = None
    allow_empty_signatures: bool | None = True
    allow_unnamed_resources: bool | None = None
    extra_opcode_budget: int | None = None
    exec_trace_config: Any | None = None
    simulation_round: int | None = None
    skip_signatures: bool | None = True


def _return_values(results: Any) -> list[Any]:
    """
    Extract `.returns[*].value` from AlgoKit ATC results, tolerating minor shape differences.
    """
    if results is None:
        return []
    returns = getattr(results, "returns", None)
    if not returns:
        return []
    out: list[Any] = []
    for r in returns:
        out.append(getattr(r, "value", r))
    return out


@dataclass(slots=True)
class AsaMetadataRegistryAvmRead:
    """
    AVM-parity ARC-89 getters via the AlgoKit-generated AppClient.

    All methods here are intended to mirror the smart-contract behavior. They use `simulate()`
    rather than sending transactions.
    """

    client: AsaMetadataRegistryClient

    def __post_init__(self) -> None:
        if self.client is None:
            raise MissingAppClientError(
                "AVM reader requires a generated AsaMetadataRegistryClient"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def simulate_many(
        self,
        build_group: Callable[[Any], None],
        *,
        simulate: SimulateOptions | None = None,
    ) -> list[Any]:
        composer = self.client.new_group()
        build_group(composer)

        s = simulate or SimulateOptions()
        results = composer.simulate(
            allow_more_logs=s.allow_more_logs,
            allow_empty_signatures=s.allow_empty_signatures,
            allow_unnamed_resources=s.allow_unnamed_resources,
            extra_opcode_budget=s.extra_opcode_budget,
            exec_trace_config=s.exec_trace_config,
            simulation_round=s.simulation_round,
            skip_signatures=s.skip_signatures,
        )
        return _return_values(results)

    def simulate_one(
        self,
        build_group: Callable[[Any], None],
        *,
        simulate: SimulateOptions | None = None,
    ) -> Any:
        values = self.simulate_many(build_group, simulate=simulate)
        return values[0] if values else None

    # ------------------------------------------------------------------
    # ARC-89 getters
    # ------------------------------------------------------------------

    def arc89_get_metadata_registry_parameters(
        self,
        *,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> RegistryParameters:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_registry_parameters(params=params),
            simulate=simulate,
        )
        return RegistryParameters.from_tuple(value)

    def arc89_get_metadata_partial_uri(
        self, *, simulate: SimulateOptions | None = None, params: Any | None = None
    ) -> str:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_partial_uri(params=params), simulate=simulate
        )
        return str(value)

    def arc89_get_metadata_mbr_delta(
        self,
        *,
        asset_id: int,
        new_size: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> MbrDelta:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_mbr_delta(
                args=(asset_id, new_size), params=params
            ),
            simulate=simulate,
        )
        return MbrDelta.from_tuple(value)

    def arc89_check_metadata_exists(
        self,
        *,
        asset_id: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> MetadataExistence:
        value = self.simulate_one(
            lambda c: c.arc89_check_metadata_exists(args=(asset_id,), params=params),
            simulate=simulate,
        )
        return MetadataExistence.from_tuple(value)

    def arc89_is_metadata_immutable(
        self,
        *,
        asset_id: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> bool:
        value = self.simulate_one(
            lambda c: c.arc89_is_metadata_immutable(args=(asset_id,), params=params),
            simulate=simulate,
        )
        return bool(value)

    def arc89_is_metadata_short(
        self,
        *,
        asset_id: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> tuple[bool, int]:
        value = self.simulate_one(
            lambda c: c.arc89_is_metadata_short(args=(asset_id,), params=params),
            simulate=simulate,
        )
        return bool(value[0]), int(value[1])

    def arc89_get_metadata_header(
        self,
        *,
        asset_id: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> MetadataHeader:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_header(args=(asset_id,), params=params),
            simulate=simulate,
        )
        return MetadataHeader.from_tuple(value)

    def arc89_get_metadata_pagination(
        self,
        *,
        asset_id: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> Pagination:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_pagination(args=(asset_id,), params=params),
            simulate=simulate,
        )
        return Pagination.from_tuple(value)

    def arc89_get_metadata(
        self,
        *,
        asset_id: int,
        page: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> PaginatedMetadata:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata(args=(asset_id, page), params=params),
            simulate=simulate,
        )
        return PaginatedMetadata.from_tuple(value)

    def arc89_get_metadata_slice(
        self,
        *,
        asset_id: int,
        offset: int,
        size: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> bytes:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_slice(
                args=(asset_id, offset, size), params=params
            ),
            simulate=simulate,
        )
        return bytes(value)

    def arc89_get_metadata_header_hash(
        self,
        *,
        asset_id: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> bytes:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_header_hash(args=(asset_id,), params=params),
            simulate=simulate,
        )
        return bytes(value)

    def arc89_get_metadata_page_hash(
        self,
        *,
        asset_id: int,
        page: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> bytes:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_page_hash(
                args=(asset_id, page), params=params
            ),
            simulate=simulate,
        )
        return bytes(value)

    def arc89_get_metadata_hash(
        self,
        *,
        asset_id: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> bytes:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_hash(args=(asset_id,), params=params),
            simulate=simulate,
        )
        return bytes(value)

    def arc89_get_metadata_string_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> str:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_string_by_key(
                args=(asset_id, key), params=params
            ),
            simulate=simulate,
        )
        return str(value)

    def arc89_get_metadata_uint64_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> int:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_uint64_by_key(
                args=(asset_id, key), params=params
            ),
            simulate=simulate,
        )
        return int(value)

    def arc89_get_metadata_object_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> str:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_object_by_key(
                args=(asset_id, key), params=params
            ),
            simulate=simulate,
        )
        return str(value)

    def arc89_get_metadata_b64_bytes_by_key(
        self,
        *,
        asset_id: int,
        key: str,
        b64_encoding: int,
        simulate: SimulateOptions | None = None,
        params: Any | None = None,
    ) -> bytes:
        value = self.simulate_one(
            lambda c: c.arc89_get_metadata_b64_bytes_by_key(
                args=(asset_id, key, b64_encoding), params=params
            ),
            simulate=simulate,
        )
        return bytes(value)
