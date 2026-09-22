from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from .. import enums
from ..algod import AlgodBoxReader
from ..codec import b64url_decode
from ..errors import (
    AsaNotFoundError,
    BoxNotFoundError,
    InvalidPageIndexError,
    InvalidSliceError,
    MetadataEncodingError,
    MetadataKeyError,
)
from ..hashing import compute_header_hash, compute_page_hash, paginate
from ..models import (
    AssetMetadataBox,
    AssetMetadataRecord,
    MetadataHeader,
    MetadataSlice,
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
        try:
            self._box(asset_id)
            metadata_exists = True
        except BoxNotFoundError:
            metadata_exists = False
        try:
            self.algod.get_asset_info(asset_id)
            asa_exists = True
        except AsaNotFoundError:
            asa_exists = False
        return asa_exists, metadata_exists

    def arc89_is_metadata_immutable(self, *, asset_id: int) -> bool:
        return self._box(asset_id).header.is_immutable

    def arc89_is_metadata_short(self, *, asset_id: int) -> tuple[bool, int]:
        h = self._box(asset_id).header
        return h.is_short, h.revision

    def arc89_get_metadata_header(self, *, asset_id: int) -> MetadataHeader:
        return self._box(asset_id).header

    def arc89_get_metadata_pagination(self, *, asset_id: int) -> Pagination:
        b = self._box(asset_id)
        size = b.body.size
        page_size = self.params.page_size
        total_pages = 0 if size == 0 else (size + page_size - 1) // page_size
        return Pagination(
            metadata_size=size,
            page_size=page_size,
            total_pages=total_pages,
            revision=b.header.revision,
        )

    def arc89_get_metadata(self, *, asset_id: int, page: int) -> PaginatedMetadata:
        b = self._box(asset_id)
        pages = paginate(b.body.raw_bytes, self.params.page_size)
        if page < 0 or page >= max(1, len(pages)):
            raise InvalidPageIndexError(
                f"Page {page} out of range ({len(pages)} pages)"
            )
        content = pages[page] if pages else b""
        return PaginatedMetadata((page + 1) < len(pages), b.header.revision, content)

    def arc89_get_metadata_slice(
        self, *, asset_id: int, offset: int, size: int
    ) -> MetadataSlice:
        b = self._box(asset_id)
        if offset < 0 or size < 0 or size > self.params.page_size:
            raise InvalidSliceError("Slice size must be within [0, PAGE_SIZE]")
        if offset + size > b.body.size:
            raise InvalidSliceError("Slice exceeds the Metadata size")
        return MetadataSlice(
            revision=b.header.revision,
            content=b.body.raw_bytes[offset : offset + size],
        )

    def arc89_get_metadata_header_hash(self, *, asset_id: int) -> bytes:
        b = self._box(asset_id)
        return compute_header_hash(
            metadata_identifiers=b.header.identifiers,
            reversible_flags=b.header.flags.reversible_byte,
            irreversible_flags=b.header.flags.irreversible_byte,
            metadata_size=b.body.size,
        )

    def arc89_get_metadata_page_hash(self, *, asset_id: int, page: int) -> bytes:
        b = self._box(asset_id)
        pages = paginate(b.body.raw_bytes, self.params.page_size)
        if page < 0 or page >= len(pages):
            raise InvalidPageIndexError(
                f"Page {page} out of range ({len(pages)} pages)"
            )
        return compute_page_hash(page_index=page, page_content=pages[page])

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

    def get_metadata_json(self, *, asset_id: int) -> dict[str, object]:
        return self.get_asset_metadata_record(asset_id=asset_id).json

    def _short_json_value(self, *, asset_id: int, key: str) -> object:
        # Same constraints as the AVM JSON getters: short Metadata, existing key.
        b = self._box(asset_id)
        if b.body.size > self.params.short_metadata_size:
            raise MetadataEncodingError("JSON getters require short Metadata")
        obj = b.body.json
        if key not in obj:
            raise MetadataKeyError(key)
        return obj[key]

    def _check_value_size(self, value: bytes) -> None:
        if len(value) > self.params.page_size:
            raise MetadataEncodingError("JSON value exceeds PAGE_SIZE")

    def get_string_by_key(self, *, asset_id: int, key: str) -> str:
        v = self._short_json_value(asset_id=asset_id, key=key)
        if not isinstance(v, str):
            raise MetadataKeyError(f"{key}: not a JSON String")
        self._check_value_size(v.encode("utf-8"))
        return v

    def get_uint64_by_key(self, *, asset_id: int, key: str) -> int:
        v = self._short_json_value(asset_id=asset_id, key=key)
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 2**64 - 1:
            raise MetadataKeyError(f"{key}: not a JSON Uint64")
        return v

    def get_object_by_key(self, *, asset_id: int, key: str) -> str:
        v = self._short_json_value(asset_id=asset_id, key=key)
        if not isinstance(v, dict):
            raise MetadataKeyError(f"{key}: not a JSON Object")
        out = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        self._check_value_size(out.encode("utf-8"))
        return out

    def get_b64_bytes_by_key(
        self, *, asset_id: int, key: str, b64_encoding: int
    ) -> bytes:
        if b64_encoding not in (enums.B64_STD_ENCODING, enums.B64_URL_ENCODING):
            raise ValueError(
                "b64_encoding must be B64_STD_ENCODING or B64_URL_ENCODING"
            )
        v = self._short_json_value(asset_id=asset_id, key=key)
        if not isinstance(v, str):
            raise MetadataKeyError(f"{key}: not a JSON String")
        self._check_value_size(v.encode("utf-8"))
        try:
            if b64_encoding == enums.B64_URL_ENCODING:
                return b64url_decode(v.rstrip("="))
            return base64.b64decode(v, validate=True)
        except Exception as e:
            raise MetadataEncodingError(f"{key}: invalid base64 value") from e
