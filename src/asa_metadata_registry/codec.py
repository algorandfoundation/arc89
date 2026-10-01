from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from itertools import pairwise

from . import constants as const
from .errors import InvalidArc90UriError


def asset_id_to_box_name(asset_id: int) -> bytes:
    """
    Convert an Asset ID (uint64) into the ARC-89 box key bytes (8-byte big-endian).
    """
    if asset_id < 0 or asset_id > 2**64 - 1:
        raise ValueError("asset_id must fit in uint64")
    return int(asset_id).to_bytes(
        const.ASSET_METADATA_BOX_KEY_SIZE, "big", signed=False
    )


def box_name_to_asset_id(box_name: bytes) -> int:
    """
    Convert an ARC-89 box key (8-byte big-endian) into an Asset ID (uint64).
    """
    if len(box_name) != const.ASSET_METADATA_BOX_KEY_SIZE:
        raise ValueError(
            f"box_name must be {const.ASSET_METADATA_BOX_KEY_SIZE} bytes, got {len(box_name)}"
        )
    return int.from_bytes(box_name, "big", signed=False)


def b64_encode(data: bytes) -> str:
    """Standard base64 (with padding)."""
    return base64.b64encode(data).decode("ascii")


def b64_decode(data_b64: str) -> bytes:
    """Standard base64 decode (accepts padding)."""
    return base64.b64decode(data_b64.encode("ascii"))


def b64url_encode(data: bytes) -> str:
    """Canonical unpadded URL-safe base64."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(data_b64url: str) -> bytes:
    """Decode canonical unpadded URL-safe base64."""
    encoded = data_b64url.encode("ascii")
    decoded = base64.b64decode(
        encoded + b"=" * (-len(encoded) % 4), altchars=b"-_", validate=True
    )
    if b64url_encode(decoded) != data_b64url:
        raise binascii.Error("Non-canonical base64url")
    return decoded


_FRAGMENT_RE = re.compile(r"^arc(0|[1-9][0-9]*)(\+(0|[1-9][0-9]*))*$")
_NETAUTH_RE = re.compile(r"^(net:[A-Za-z0-9._-]+|gh:[A-Za-z0-9_-]+)$")
_APP_ID_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_BOX_VALUE_RE = re.compile(r"^[A-Za-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class Arc90Compliance:
    """
    The ARC-90 compliance fragment '#arc<A>+<B>+...': unpadded decimal ARC numbers in
    strictly ascending order, 'arc' literal on the first entry only, ARC-3 sole entry.
    Non-compliant fragments parse as empty (ignored), as ARC-90 requires.
    """

    arcs: tuple[int, ...] = ()

    @classmethod
    def parse(cls, fragment: str | None) -> Arc90Compliance:
        if not fragment:
            return cls(())
        frag = fragment[1:] if fragment.startswith("#") else fragment
        if not _FRAGMENT_RE.match(frag):
            return cls(())
        arcs = tuple(int(p) for p in frag[3:].split("+"))
        if any(b <= a for a, b in pairwise(arcs)):
            return cls(())
        if 3 in arcs and len(arcs) > 1:
            return cls(())
        return cls(arcs)

    def to_fragment(self) -> str | None:
        if not self.arcs:
            return None
        arcs = tuple(sorted(set(self.arcs)))
        if 3 in arcs and len(arcs) > 1:
            raise ValueError("ARC-3 must be the sole entry in compliance fragment")
        return "#arc" + "+".join(str(n) for n in arcs)


@dataclass(frozen=True, slots=True)
class Arc90Uri:
    """
    Parsed ARC-90 URI referencing an application box.

    ARC-89 uses URIs of the form:

        algorand://<netauth>/app/<app_id>?box=<base64url_box_name>#arc<A>+<B>...

    The URI can be *partial* (Asset URL field), where the `box` query parameter exists
    but has an empty value; the SDK can complete it given an Asset ID.
    """

    # Network authority; examples: "net:testnet", "" (mainnet / unspecified).
    netauth: str | None
    app_id: int
    box_name: bytes | None
    compliance: Arc90Compliance = Arc90Compliance(())

    @property
    def asset_id(self) -> int | None:
        if self.box_name is None:
            return None
        return box_name_to_asset_id(self.box_name)

    @property
    def is_partial(self) -> bool:
        return self.box_name is None

    def with_asset_id(self, asset_id: int) -> Arc90Uri:
        return Arc90Uri(
            netauth=self.netauth,
            app_id=self.app_id,
            box_name=asset_id_to_box_name(asset_id),
            compliance=self.compliance,
        )

    def to_uri(self) -> str:
        """Render the URI (canonical unpadded base64url box value)."""
        box = b64url_encode(self.box_name) if self.box_name is not None else ""
        fragment = self.compliance.to_fragment() or ""
        authority = f"{self.netauth}/" if self.netauth else ""
        return (
            f"{const.ARC90_URI_SCHEME.decode()}{authority}"
            f"{const.ARC90_URI_APP_PATH.decode()}{self.app_id}"
            f"{const.ARC90_URI_BOX_QUERY.decode()}{box}{fragment}"
        )

    def to_algod_box_name_b64(self) -> str:
        """
        The Algod `/box?name=` query parameter expects standard base64 (with padding).
        """
        if self.box_name is None:
            raise ValueError("Cannot produce algod box name for a partial URI")
        return b64_encode(self.box_name)

    @staticmethod
    def parse(uri: str) -> Arc90Uri:
        """
        Parse an ARC-89 Asset Metadata URI, with the exact shape the registry enforces:

            algorand://[<netauth>/]app/<app_id>?box=<base64url>[#arc<A>+<B>...]

        where <netauth> is `net:<label>` or `gh:<base64url>` (absent on MainNet), <app_id>
        is an unpadded decimal, `box` is the only query parameter and its value is empty
        (partial URI) or the canonical unpadded base64url of the 8-byte Asset ID.
        """
        scheme = const.ARC90_URI_SCHEME.decode()
        if not uri.startswith(scheme):
            raise InvalidArc90UriError(f"Not an {scheme} URI")
        rest = uri[len(scheme) :]

        rest, _, fragment = rest.partition("#")
        if "#" in fragment:
            raise InvalidArc90UriError("Unexpected '#' in fragment")
        compliance = Arc90Compliance.parse("#" + fragment if fragment else None)

        path, sep, query = rest.partition("?")
        box_prefix = f"{const.ARC90_URI_BOX_QUERY_NAME.decode()}="
        if not sep or not query.startswith(box_prefix):
            raise InvalidArc90UriError(
                f"Missing '{const.ARC90_URI_BOX_QUERY_NAME.decode()}' query parameter"
            )
        box_value = query[len(box_prefix) :]
        if "&" in box_value:
            raise InvalidArc90UriError("Unexpected query parameter")
        if not _BOX_VALUE_RE.match(box_value):
            raise InvalidArc90UriError("Invalid base64url box name")

        app_path = const.ARC90_URI_APP_PATH.decode()  # "app/"
        netauth: str | None = None
        if not path.startswith(app_path):
            authority, slash, path = path.partition("/")
            if not slash or not _NETAUTH_RE.match(authority):
                raise InvalidArc90UriError("Unrecognized ARC-90 app URI shape")
            if not path.startswith(app_path):
                raise InvalidArc90UriError(f"Expected path '/{app_path}<app_id>'")
            netauth = authority
        app_id_str = path[len(app_path) :]
        if not _APP_ID_RE.match(app_id_str) or int(app_id_str) >= 2**64:
            raise InvalidArc90UriError("Invalid app id in path")

        box_name: bytes | None = None
        if box_value:
            try:
                box_name = b64url_decode(box_value)
            except (binascii.Error, UnicodeError, ValueError) as e:
                raise InvalidArc90UriError("Invalid base64url box name") from e
            if len(box_name) != const.ASSET_METADATA_BOX_KEY_SIZE:
                raise InvalidArc90UriError(
                    "ARC-89 expects an 8-byte box name (asset id)"
                )

        return Arc90Uri(
            netauth=netauth,
            app_id=int(app_id_str),
            box_name=box_name,
            compliance=compliance,
        )


def complete_partial_asset_url(asset_url: str, asset_id: int) -> str:
    """
    Complete an ARC-89 partial Asset URL (Asset Params `url`) into a full Asset Metadata URI.

    The partial URL is expected to include the registry app reference and `box=` query key, but
    not the box value itself.

    Example (partial):
        algorand://net:testnet/app/772968354?box=#arc89

    Output (complete):
        algorand://net:testnet/app/772968354?box=<base64url(asset_id_bytes)>#arc89
    """
    parsed = Arc90Uri.parse(asset_url)
    if not parsed.is_partial:
        raise InvalidArc90UriError("Asset URL MUST have an empty box value")
    return parsed.with_asset_id(asset_id).to_uri()
