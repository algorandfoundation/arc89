from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .codec import (
    Arc90Uri,
    asset_id_to_box_name,
    b64_decode,
    complete_partial_asset_url,
)
from .errors import AsaNotFoundError, BoxNotFoundError, InvalidArc90UriError
from .models import AssetMetadataBox, AssetMetadataRecord, RegistryParameters

if TYPE_CHECKING:  # pragma: no cover
    from algosdk.v2client.algod import AlgodClient


@dataclass(slots=True)
class AlgodBoxReader:
    """
    Read ARC-89 metadata by directly reading the registry application box via Algod.

    This avoids transactions entirely and is usually the fastest read path.

    The only required Algod methods are:
    - `application_box_by_name(app_id, box_name)` (or equivalent)
    - `asset_info(asset_id)` for URI resolution (optional)
    """

    algod: AlgodClient

    def get_box_value(self, *, app_id: int, box_name: bytes) -> bytes:
        """
        Fetch a raw box value.

        Raises:
            BoxNotFoundError: if the box doesn't exist.
        """
        try:
            resp = self.algod.application_box_by_name(app_id, box_name)
        except Exception as e:
            msg = str(e).lower()
            if "404" in msg or "not found" in msg:
                raise BoxNotFoundError("Box not found") from e
            raise

        # Common shapes:
        # - {"name": "...", "value": "<base64>"}
        # - {"box": {"name": "...", "value": "<base64>"}}
        value_b64: str | None = None
        if isinstance(resp, Mapping):
            if "value" in resp:
                value_b64 = resp.get("value")  # type: ignore[assignment]
            elif "box" in resp and isinstance(resp.get("box"), Mapping):
                value_b64 = resp["box"].get("value")  # type: ignore[index]
        if value_b64 is None:
            raise RuntimeError(
                "Unexpected algod response shape for application_box_by_name"
            )

        return b64_decode(value_b64)

    def try_get_metadata_box(
        self,
        *,
        app_id: int,
        asset_id: int,
        params: RegistryParameters | None = None,
    ) -> AssetMetadataBox | None:
        """
        Return the parsed metadata box, or None if the box doesn't exist.
        """
        try:
            value = self.get_box_value(
                app_id=app_id, box_name=asset_id_to_box_name(asset_id)
            )
        except BoxNotFoundError:
            return None
        p = params or RegistryParameters.defaults()
        return AssetMetadataBox.parse(
            asset_id=asset_id,
            value=value,
            header_size=p.header_size,
            max_metadata_size=p.max_metadata_size,
        )

    def get_metadata_box(
        self,
        *,
        app_id: int,
        asset_id: int,
        params: RegistryParameters | None = None,
    ) -> AssetMetadataBox:
        """
        Retrieve the parsed metadata box, raising if it does not exist.

        Args:
            app_id: Application ID of the ARC-89 registry.
            asset_id: ID of the ASA whose metadata box should be read.
            params: Optional registry parameters controlling header and metadata sizes.

        Returns:
            The parsed :class:`AssetMetadataBox` for the given asset.

        Raises:
            BoxNotFoundError: If the metadata box for the given asset does not exist.
        """
        box = self.try_get_metadata_box(app_id=app_id, asset_id=asset_id, params=params)
        if box is None:
            raise BoxNotFoundError("Metadata box not found")
        return box

    def get_asset_metadata_record(
        self,
        *,
        app_id: int,
        asset_id: int,
        params: RegistryParameters | None = None,
    ) -> AssetMetadataRecord:
        """
        Retrieve the ARC-89 asset metadata box and return it as an AssetMetadataRecord.

        Args:
            app_id: The application ID of the ARC-89 registry.
            asset_id: The ASA ID whose metadata should be read.
            params: Optional registry parameters; if omitted, default parameters are used.

        Returns:
            An AssetMetadataRecord containing the parsed header and body of the
            asset's metadata box.

        Raises:
            BoxNotFoundError: If the metadata box for the given asset does not exist.
        """
        box = self.get_metadata_box(app_id=app_id, asset_id=asset_id, params=params)
        return AssetMetadataRecord(
            app_id=app_id,
            asset_id=asset_id,
            header=box.header,
            body=box.body,
        )

    # ---------------------------------------------------------------------
    # ASA lookups (optional)
    # ---------------------------------------------------------------------

    def get_asset_info(self, asset_id: int) -> Mapping[str, Any]:
        try:
            resp = self.algod.asset_info(asset_id)
        except Exception as e:
            msg = str(e).lower()
            if "404" in msg or "not found" in msg or "does not exist" in msg:
                raise AsaNotFoundError(f"ASA {asset_id} not found") from e
            raise
        if not isinstance(resp, Mapping):
            raise RuntimeError("Unexpected algod response for asset_info")
        return resp

    def get_asset_url(self, asset_id: int) -> str | None:
        """
        Return the ASA's URL field as a string, or None if no URL is present.

        Args:
            asset_id: The ID of the ASA whose URL field should be retrieved.

        Returns:
            The URL from the ASA's params as a string, or None if the params
            object is missing or does not contain a non-null "url" field.
        """
        info = self.get_asset_info(asset_id)
        params = info.get("params") if isinstance(info.get("params"), Mapping) else None
        url = params.get("url") if params else None
        return str(url) if url is not None else None

    def resolve_metadata_uri_from_asset(self, *, asset_id: int) -> Arc90Uri:
        """
        Resolve an ARC-89 Asset Metadata URI from the ASA's `url` field.

        Raises:
            InvalidArc90UriError: if the URL is not an ARC-89-compatible ARC-90 partial URI.
        """
        url = self.get_asset_url(asset_id)
        if not url:
            raise InvalidArc90UriError(
                "ASA has no url field; cannot resolve ARC-89 metadata URI"
            )
        try:
            full = complete_partial_asset_url(url, asset_id)
            return Arc90Uri.parse(full)
        except Exception as e:
            raise InvalidArc90UriError(
                "Failed to resolve ARC-89 URI from ASA url"
            ) from e
