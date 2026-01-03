from __future__ import annotations

import base64
import binascii
import hashlib
import json

from src import constants as const

from .codec import asset_id_to_box_name
from .errors import InvalidPageIndexError

MAX_UINT8 = 2**8 - 1
MAX_UINT16 = 2**16 - 1


def sha512_256(data: bytes) -> bytes:
    """
    SHA-512/256 digest.

    Python exposes this as 'sha512_256' in hashlib on most modern builds.
    """
    try:
        h = hashlib.new("sha512_256")
    except ValueError as err:
        raise RuntimeError(
            "hashlib does not support sha512_256 on this Python build"
        ) from err
    h.update(data)
    return h.digest()


def sha256(data: bytes) -> bytes:
    """
    SHA-256 digest.
    """
    h = hashlib.sha256()
    h.update(data)
    return h.digest()


def compute_header_hash(
    *,
    asset_id: int,
    metadata_identifiers: int,
    reversible_flags: int,
    irreversible_flags: int,
    metadata_size: int,
) -> bytes:
    """
    Compute hh = SHA-512/256("arc0089/header" || asset_id || identifiers || rev_flags || irr_flags || metadata_size)

    Args:
        asset_id: Asset ID (uint64)
        metadata_identifiers: Metadata Identifiers (byte)
        reversible_flags: Reversible Flags (byte)
        irreversible_flags: Irreversible Flags (byte)
        metadata_size: Metadata byte size (uint16)

    Returns:
        32-byte header hash
    """
    if not (0 <= metadata_identifiers <= MAX_UINT8):
        raise ValueError("metadata_identifiers must fit in byte")
    if not (0 <= reversible_flags <= MAX_UINT8):
        raise ValueError("reversible_flags must fit in byte")
    if not (0 <= irreversible_flags <= MAX_UINT8):
        raise ValueError("irreversible_flags must fit in byte")
    if not (0 <= metadata_size <= MAX_UINT16):
        raise ValueError("metadata_size must fit in uint16")

    data = (
        const.HASH_DOMAIN_HEADER
        + asset_id_to_box_name(asset_id)
        + bytes([metadata_identifiers])
        + bytes([reversible_flags])
        + bytes([irreversible_flags])
        + int(metadata_size).to_bytes(const.UINT16_SIZE, "big", signed=False)
    )
    return sha512_256(data)


def paginate(metadata: bytes, page_size: int) -> list[bytes]:
    """Split metadata bytes into ARC-89 pages."""
    if page_size <= 0:
        raise ValueError("page_size must be > 0")
    if not metadata:
        return []
    return [metadata[i : i + page_size] for i in range(0, len(metadata), page_size)]


def compute_page_hash(
    *,
    asset_id: int,
    page_index: int,
    page_content: bytes,
) -> bytes:
    """
    Compute ph[i] = SHA-512/256("arc0089/page" || asset_id || page_index || page_size || page_content)

    Args:
        asset_id: Asset ID (uint64)
        page_index: 0-based page index (uint8)
        page_content: Page content raw bytes

    Returns:
        32-byte page hash
    """
    if not (0 <= page_index <= MAX_UINT8):
        raise InvalidPageIndexError("page_index must fit in uint8")
    if page_index < 0:
        raise InvalidPageIndexError("page_index must be non-negative")
    if not (0 <= len(page_content) <= MAX_UINT16):
        raise ValueError("page_content length must fit in uint16")

    data = (
        const.HASH_DOMAIN_PAGE
        + asset_id_to_box_name(asset_id)
        + bytes([page_index])
        + len(page_content).to_bytes(const.UINT16_SIZE, "big", signed=False)
        + page_content
    )
    return sha512_256(data)


def compute_metadata_hash(
    *,
    asset_id: int,
    metadata_identifiers: int,
    reversible_flags: int,
    irreversible_flags: int,
    metadata: bytes,
    page_size: int,
) -> bytes:
    """
    Compute the ARC-89 Metadata Hash.

    am = SHA-512/256("arc0089/am" || hh || ph[0] || ...)

    If metadata is empty, there are no pages and:
        am = SHA-512/256("arc0089/am" || hh)

    Returns:
        32-byte metadata hash
    """
    hh = compute_header_hash(
        asset_id=asset_id,
        metadata_identifiers=metadata_identifiers,
        reversible_flags=reversible_flags,
        irreversible_flags=irreversible_flags,
        metadata_size=len(metadata),
    )
    pages = paginate(metadata, page_size=page_size)

    data = const.HASH_DOMAIN_METADATA + hh
    for i, p in enumerate(pages):
        data += compute_page_hash(asset_id=asset_id, page_index=i, page_content=p)

    return sha512_256(data)


def compute_arc3_metadata_hash(json_bytes: bytes) -> bytes:
    try:
        obj: object = json.loads(json_bytes.decode("utf-8"))
    except UnicodeDecodeError as e:
        raise ValueError("Metadata file must be UTF-8 encoded JSON.") from e
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON metadata file.") from e

    if isinstance(obj, dict) and "extra_metadata" in obj:
        extra_b64: object = obj.get("extra_metadata")
        if not isinstance(extra_b64, str):
            raise ValueError('"extra_metadata" must be a base64 string when present.')

        try:
            extra = base64.b64decode(extra_b64, validate=True)
        except binascii.Error as e:
            raise ValueError('Could not base64-decode "extra_metadata".') from e

        json_h = sha512_256(const.ARC3_HASH_AMJ_PREFIX + json_bytes)
        am = sha512_256(const.ARC3_HASH_AM_PREFIX + json_h + extra)
        return am
    else:
        return sha256(json_bytes)
