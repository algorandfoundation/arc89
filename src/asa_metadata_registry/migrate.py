from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping

from algokit_utils import AssetConfigParams, SigningAccount
from algosdk.transaction import Transaction

from . import bitmasks
from . import constants as const
from .codec import Arc90Compliance, Arc90Uri, b64_decode
from .errors import MetadataHashMismatchError, MissingAppClientError
from .hashing import compute_arc3_metadata_hash
from .models import AssetMetadata, MetadataBody, MetadataFlags
from .registry import AsaMetadataRegistry
from .validation import decode_metadata_json

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


def _asa_metadata_hash(value: object) -> bytes:
    """Normalize the ASA `am` (AlgoKit Utils returns algod's base64 string) to bytes."""
    if isinstance(value, str):
        return b64_decode(value)
    return bytes(value) if isinstance(value, bytes | bytearray) else b""


def _ensure_exists_and_not_already_migrated(
    *, registry: AsaMetadataRegistry, asset_id: int
) -> None:
    existence = registry.read.arc89_check_metadata_exists(asset_id=asset_id)
    if not existence.asa_exists:
        raise ValueError(f"ASA {asset_id} does not exist")
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
    metadata: Mapping[str, object] | bytes,
    arc3_compliant: bool,
    flags: MetadataFlags | None = None,
    verify_am: bool = True,
    publish_arc2_message: bool = False,
) -> None:
    """
    Migrate a legacy ASA (e.g., ARC-3 / ARC-19 / ARC-69) metadata by replicating it
    in the ASA Metadata Registry, where it takes precedence over the Asset URL. The
    informational ARC-2 announcement is sent only if `publish_arc2_message` is True.

    Pass the original file `bytes` to store them verbatim (a `Mapping` is re-encoded
    compactly). When the ASA has a nonzero `am` and is ARC-3 compliant, the ARC-3 hash
    of the stored bytes MUST equal `am` (checked unless `verify_am=False`).

    Flow:
    1) Error if metadata already exists in the Registry for the given ASA; error if the ASA does not exist.
    2) Error if metadata is flagged as ARC-89 native.
    3) If the ASA has a non-zero on-chain am: auto-set immutable when no flags provided,
       or error early if flags are provided without immutable=True.
    4) Validate metadata size <= MAX_METADATA_SIZE (raw bytes after JSON encoding).
    5) Create metadata on the registry (and, on request, emit the ARC-2 message).
    """

    _ensure_exists_and_not_already_migrated(registry=registry, asset_id=asset_id)

    if flags is not None and flags.irreversible.arc89_native:
        raise ValueError("Cannot flag migrated metadata as ARC-89 native")

    # Pre-flight: fetch ASA info to check metadata hash and decide on flags
    asset_info = registry.write.client.algorand.asset.get_by_id(asset_id=asset_id)
    on_chain_am = _asa_metadata_hash(asset_info.metadata_hash)
    has_on_chain_am = on_chain_am not in (b"", bytes(32))
    if has_on_chain_am and flags is not None and not flags.irreversible.immutable:
        raise ValueError(
            f"ASA {asset_id} has a metadata hash (am) set on-chain, hence the registry requires "
            "the IMMUTABLE flag for this migration. Either omit flags to set it automatically, "
            "or pass flags with immutable=True."
        )

    # Build AssetMetadata, resolve flags if not provided and enforce size bounds.
    raw: bytes | None
    json_obj: Mapping[str, object]
    if isinstance(metadata, bytes | bytearray):
        raw = bytes(metadata)
        json_obj = decode_metadata_json(raw)
    else:
        raw, json_obj = None, metadata
    try:
        asset_md = AssetMetadata.from_json(
            asset_id=asset_id,
            json_obj=json_obj,
            flags=flags,
            arc3_compliant=arc3_compliant,
        )
        if raw is not None:
            asset_md = dataclasses.replace(asset_md, body=MetadataBody(raw))
            asset_md.body.validate_size()
    except ValueError as e:
        if type(e) is ValueError:
            raise ValueError(
                "Legacy metadata is too large to migrate into ARC-89 registry, "
                f"MAX_METADATA_SIZE={const.MAX_METADATA_SIZE}. Consider hosting a smaller "
                "JSON document or storing a pointer in short metadata."
            ) from e
        raise
    # Set immutable flag after derivation to preserve auto-detected reversible flags (e.g. ARC-20/ARC-62)
    if has_on_chain_am and flags is None:
        asset_md = dataclasses.replace(
            asset_md,
            flags=MetadataFlags.from_bytes(
                asset_md.flags.reversible_byte,
                asset_md.flags.irreversible_byte | bitmasks.MASK_IRR_IMMUTABLE,
            ),
        )

    if has_on_chain_am and verify_am and arc3_compliant:
        expected_am = compute_arc3_metadata_hash(asset_md.body.raw_bytes)
        if expected_am != on_chain_am:
            raise MetadataHashMismatchError(
                f"ASA {asset_id} am does not match the ARC-3 hash of the metadata bytes to "
                "migrate; pass the original file bytes, or verify_am=False."
            )

    migrate_group = registry.write.build_create_metadata_group(
        asset_manager=asset_manager, metadata=asset_md
    )
    if not publish_arc2_message:
        migrate_group.send()
        return

    txn = build_arc2_migration_message_txn(
        registry=registry,
        asset_id=asset_id,
        asset_manager=asset_manager,
        metadata_uri=_derive_migration_uri(
            registry=registry, asset_id=asset_id, arc3=arc3_compliant
        ),
    )
    if migrate_group.composer().count() < const.MAX_GROUP_SIZE:
        # We migrate and emit the ARC-2 message atomically.
        migrate_group.add_transaction(txn)
        migrate_group.send()
    else:
        # We migrate first, then emit the ARC-2 message.
        migrate_group.send()
        registry.write.client.algorand.new_group().add_transaction(txn).send()
