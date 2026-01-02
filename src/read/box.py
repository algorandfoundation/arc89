from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src import enums

from ..algod import AlgodBoxReader
from ..hashing import compute_header_hash, compute_page_hash, paginate
from ..models import (
    AssetMetadataBox,
    AssetMetadataRecord,
    MetadataHeader,
    PaginatedMetadata,
    Pagination,
    RegistryParameters,
)


@dataclass(slots=True)
class AsaMetadataRegistryBoxRead:
    """
    Reconstruct ARC-89 getter outputs from box contents (Algod).

    This reader is *fast* (direct state read) and does not require transactions.
    """

    algod: AlgodBoxReader
    app_id: int
    params: RegistryParameters

    def _box(self, asset_id: int) -> AssetMetadataBox:
        return self.algod.get_metadata_box(
            app_id=self.app_id, asset_id=asset_id, params=self.params
        )

    # ------------------------------------------------------------------
    # Contract-equivalent getters (reconstructed)
    # ------------------------------------------------------------------

    def arc89_check_metadata_exists(self, *, asset_id: int) -> tuple[bool, bool]:
        # Off-chain, we can check only metadata existence by box lookup; ASA existence requires asset_info.
        try:
            self._box(asset_id)
            metadata_exists = True
        except Exception:
            metadata_exists = False

        try:
            self.algod.get_asset_info(asset_id)
            asa_exists = True
        except Exception:
            asa_exists = False

        return asa_exists, metadata_exists

    def arc89_is_metadata_immutable(self, *, asset_id: int) -> bool:
        return self._box(asset_id).header.is_immutable

    def arc89_is_metadata_short(self, *, asset_id: int) -> tuple[bool, int]:
        h = self._box(asset_id).header
        return h.is_short, h.last_modified_round

    def arc89_get_metadata_header(self, *, asset_id: int) -> MetadataHeader:
        return self._box(asset_id).header

    def arc89_get_metadata_pagination(self, *, asset_id: int) -> Pagination:
        b = self._box(asset_id)
        size = b.body.size
        page_size = self.params.page_size
        total_pages = 0 if size == 0 else (size + page_size - 1) // page_size
        return Pagination(
            metadata_size=size, page_size=page_size, total_pages=total_pages
        )

    def arc89_get_metadata(self, *, asset_id: int, page: int) -> PaginatedMetadata:
        b = self._box(asset_id)
        pages = paginate(b.body.raw_bytes, self.params.page_size)
        if page < 0 or page >= max(1, len(pages)):
            # Contract would likely error; off-chain we return empty page
            return PaginatedMetadata(
                has_next_page=False,
                last_modified_round=b.header.last_modified_round,
                page_content=b"",
            )
        content = pages[page] if pages else b""
        has_next = (page + 1) < len(pages)
        return PaginatedMetadata(has_next, b.header.last_modified_round, content)

    def arc89_get_metadata_slice(
        self, *, asset_id: int, offset: int, size: int
    ) -> bytes:
        b = self._box(asset_id)
        if offset < 0 or size < 0:
            return b""
        return b.body.raw_bytes[offset : offset + size]

    def arc89_get_metadata_header_hash(self, *, asset_id: int) -> bytes:
        b = self._box(asset_id)
        return compute_header_hash(
            asset_id=asset_id,
            metadata_identifiers=b.header.identifiers,
            reversible_flags=b.header.flags.reversible_byte,
            irreversible_flags=b.header.flags.irreversible_byte,
            metadata_size=b.body.size,
        )

    def arc89_get_metadata_page_hash(self, *, asset_id: int, page: int) -> bytes:
        b = self._box(asset_id)
        pages = paginate(b.body.raw_bytes, self.params.page_size)
        if page < 0 or page >= len(pages):
            return b""
        return compute_page_hash(
            asset_id=asset_id, page_index=page, page_content=pages[page]
        )

    def arc89_get_metadata_hash(self, *, asset_id: int) -> bytes:
        # On-chain method returns the header's stored metadata_hash.
        return self._box(asset_id).header.metadata_hash

    # ------------------------------------------------------------------
    # Practical off-chain helpers
    # ------------------------------------------------------------------

    def get_asset_metadata_record(self, *, asset_id: int) -> AssetMetadataRecord:
        return self.algod.get_asset_metadata_record(
            app_id=self.app_id, asset_id=asset_id, params=self.params
        )

    def get_metadata_json(self, *, asset_id: int) -> dict[str, Any]:
        return self.get_asset_metadata_record(asset_id=asset_id).json

    def get_string_by_key(self, *, asset_id: int, key: str) -> str:
        obj = self.get_metadata_json(asset_id=asset_id)
        v = obj.get(key)
        return v if isinstance(v, str) else ""

    def get_uint64_by_key(self, *, asset_id: int, key: str) -> int:
        obj = self.get_metadata_json(asset_id=asset_id)
        v = obj.get(key)
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int) and v >= 0:
            return v
        return 0

    def get_object_by_key(self, *, asset_id: int, key: str) -> str:
        obj = self.get_metadata_json(asset_id=asset_id)
        v = obj.get(key)
        # Contract returns JSON string for objects (limited by page size); here we just dump.
        try:
            import json

            return (
                json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                if isinstance(v, dict)
                else ""
            )
        except Exception:
            return ""

    def get_b64_bytes_by_key(
        self, *, asset_id: int, key: str, b64_encoding: int
    ) -> bytes:
        assert b64_encoding in (enums.B64_STD_ENCODING, enums.B64_URL_ENCODING)
        obj = self.get_metadata_json(asset_id=asset_id)
        v = obj.get(key)
        import base64

        if isinstance(v, str):
            try:
                if b64_encoding == enums.B64_URL_ENCODING:
                    return base64.urlsafe_b64decode(v)
                else:
                    return base64.standard_b64decode(v)
            except Exception:
                return b""
        else:
            return b""
