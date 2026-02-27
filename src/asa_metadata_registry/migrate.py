from __future__ import annotations

import json
from collections.abc import Mapping

from algokit_utils import AssetConfigParams, SigningAccount
from algosdk.transaction import Transaction

from . import constants as const
from .codec import Arc90Compliance, Arc90Uri
from .errors import MissingAppClientError
from .models import AssetMetadata, MetadataFlags
from .registry import AsaMetadataRegistry

# ---------------------------------------------------------------------------
# ARC-2 migration message helpers (JSON only)
# ---------------------------------------------------------------------------


def _encode_arc2_migration_message(*, uri: str) -> bytes:
    """
    Encode an ARC-2 message advertising the metadata URI for ARC-89 migration.

    This SDK encodes JSON only (j) payload (recommended by ARC-89 specs):
      b"arc89:j<payload>"

    where payload is UTF-8 JSON of: {"uri": <asset_metadata_uri>}.

    Returns:
        Bytes suitable for setting as `note` on an AssetConfig transaction.
    """

    payload = json.dumps(
        {"uri": uri}, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")

    return const.ARC2_ARC_NUMBER + const.ARC2_DATA_FORMAT_JSON + payload


def build_arc2_migration_message_txn(
    *,
    registry: AsaMetadataRegistry,
    asset_id: int,
    asset_manager: SigningAccount,
    metadata_uri: str,
) -> Transaction:
    """
    Build an AssetConfig txn that publishes the ARC-2 migration message as note.

    WARNING: Preserves all role addresses to avoid irreversibly disabling ASA RBAC.

    Returns the underlying unsigned transaction object.
    """

    try:
        write = registry.write
    except MissingAppClientError as e:
        raise ValueError(
            "Building asset config requires registry constructed with write capabilities."
        ) from e

    info = write.client.algorand.asset.get_by_id(asset_id=asset_id)
    note = _encode_arc2_migration_message(uri=metadata_uri)

    return write.client.algorand.create_transaction.asset_config(
        AssetConfigParams(
            sender=asset_manager.address,
            asset_id=asset_id,
            manager=asset_manager.address,
            reserve=info.reserve,
            freeze=info.freeze,
            clawback=info.clawback,
            note=note,
        )
    )


# ---------------------------------------------------------------------------
# High-level migration helpers
# ---------------------------------------------------------------------------


def _ensure_not_already_migrated(
    *, registry: AsaMetadataRegistry, asset_id: int
) -> None:
    existence = registry.read.arc89_check_metadata_exists(asset_id=asset_id)
    if existence.metadata_exists:
        raise ValueError(
            f"ASA {asset_id} already has metadata in this registry; migration is not allowed"
        )


def _derive_migration_uri(
    *,
    registry: AsaMetadataRegistry,
    asset_id: int,
    arc3: bool,
) -> str:
    """
    Derive the ARC-90 registry URI to be published inside the ARC-2 migration message.

    Uses the SDK's ARC-90 URI helper with the registry's configured `netauth` and `app_id`.

    Enforces ARC-90 rule that ARC-3 must be the sole compliance fragment.
    """
    base = registry.arc90_uri(asset_id=asset_id)
    return Arc90Uri(
        netauth=base.netauth,
        app_id=base.app_id,
        box_name=base.box_name,
        compliance=Arc90Compliance((3,)) if arc3 else Arc90Compliance(),
    ).to_uri()


def migrate_legacy_metadata_to_registry(
    *,
    registry: AsaMetadataRegistry,
    asset_manager: SigningAccount,
    asset_id: int,
    metadata: Mapping[str, object],
    flags: MetadataFlags | None = None,
    arc3_compliant: bool = False,
) -> None:
    """
    Migrate a legacy ASA (e.g., ARC-3 / ARC-19 / ARC-69) metadata by replicating it
    in the ASA Metadata Registry, then emitting an ARC-2 migration message.

    Flow:
    1) Error if metadata already exists in the Registry for the given ASA.
    2) Error if metadata is flagged as ARC-89 native.
    3) Validate metadata size <= MAX_METADATA_SIZE (raw bytes after JSON encoding).
    4) Create metadata on the registry and emit the ARC-2 migration message.
    """

    _ensure_not_already_migrated(registry=registry, asset_id=asset_id)

    if flags is not None and flags.irreversible.arc89_native:
        raise ValueError("Cannot flag migrated metadata as ARC-89 native")

    # Build AssetMetadata and enforce size bounds.
    asset_md = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=metadata,
        flags=flags,
        arc3_compliant=arc3_compliant,
    )
    if asset_md.size > const.MAX_METADATA_SIZE:
        raise ValueError(
            "Legacy metadata is too large to migrate into ARC-89 registry: "
            f"size={asset_md.size} bytes, MAX_METADATA_SIZE={const.MAX_METADATA_SIZE}. "
            "Consider hosting a smaller JSON document or storing a pointer in short metadata."
        )

    migration_uri = _derive_migration_uri(
        registry=registry,
        asset_id=asset_id,
        arc3=arc3_compliant,
    )

    txn = build_arc2_migration_message_txn(
        registry=registry,
        asset_id=asset_id,
        asset_manager=asset_manager,
        metadata_uri=migration_uri,
    )
    migrate_group = registry.write.build_create_metadata_group(
        asset_manager=asset_manager, metadata=asset_md
    )
    migrate_group.add_transaction(txn)
    migrate_group.send()
