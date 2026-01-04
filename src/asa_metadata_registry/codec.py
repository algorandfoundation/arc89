from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from src.asa_metadata_registry import constants as const

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
    """URL-safe base64, per ARC-90 examples."""
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64url_decode(data_b64url: str) -> bytes:
    """URL-safe base64 decode."""
    return base64.urlsafe_b64decode(data_b64url.encode("ascii"))


@dataclass(frozen=True, slots=True)
class Arc90Compliance:
    """
    Represents the ARC-90 compliance fragment '#arc<A>+<B>+...'.

    Per ARC-90:
    - Format: #arc<A>+<B>+<C> where A, B, C are decimal numbers
    - First entry has 'arc' prefix, subsequent entries are bare numbers
    - No leading zeros allowed
    - Special case: ARC-3 must be sole entry (#arc3)
    - Order is not enforced (clients MUST accept any order)
    """

    arcs: tuple[int, ...] = ()

    @classmethod
    def parse(cls, fragment: str | None) -> Arc90Compliance:
        if not fragment:
            return cls(())

        frag = fragment.lstrip("#")
        if not frag:
            return cls(())

        # Validate format: arc<number>+<number>+...
        # First must have 'arc' prefix, rest are bare numbers
        if not frag.startswith("arc"):
            return cls(())  # Invalid, ignore per spec

        # Remove 'arc' prefix
        remainder = frag[3:]
        if not remainder:
            return cls(())

        # Split by '+'
        parts = remainder.split("+")
        arcs: list[int] = []

        for p in parts:
            # No leading zeros allowed (except single digit)
            if len(p) > 1 and p[0] == "0":
                return cls(())  # Invalid format

            try:
                arc_num = int(p)
                arcs.append(arc_num)
            except ValueError:
                return cls(())  # Invalid number

        # Validate ARC-3 special case
        if 3 in arcs and len(arcs) > 1:
            return cls(())  # ARC-3 must be sole entry

        return cls(tuple(arcs))

    def to_fragment(self) -> str | None:
        if not self.arcs:
            return None

        # Validate ARC-3 special case before serializing
        if 3 in self.arcs and len(self.arcs) > 1:
            raise ValueError("ARC-3 must be the sole entry in compliance fragment")

        # First entry with 'arc', rest are bare numbers
        parts = [f"arc{self.arcs[0]}"]
        parts.extend(str(n) for n in self.arcs[1:])

        return "#" + "+".join(parts)


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
        """
        Render the URI using ARC-89 conventions (base64url for box query parameter).
        """
        box = ""
        if self.box_name is not None:
            box = b64url_encode(self.box_name)

        fragment = self.compliance.to_fragment() or ""

        if self.netauth:
            netloc = self.netauth
            path = f"{const.ARC90_URI_APP_PATH_NAME.decode()}/{self.app_id}"  # No leading slash - urlunparse adds it
        else:
            # ARC-89 draft mainnet examples
            netloc = const.ARC90_URI_APP_PATH_NAME.decode()
            path = f"{self.app_id}"  # No leading slash - urlunparse adds it

        query = urlencode({const.ARC90_URI_BOX_QUERY_NAME.decode(): box})
        return urlunparse(
            (
                const.ARC90_URI_SCHEME_NAME.decode(),
                netloc,
                path,
                "",
                query,
                fragment.lstrip("#"),
            )
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
        Parse an ARC-90 URI used by ARC-89.

        Supports common serializations:
        - algorand://net:testnet/app/<app_id>?box=<b64url>#arc89
        - algorand://net:localnet/app/<app_id>?box=<b64url>#arc3
        - algorand://app/<app_id>?box=<b64url>#arc89   (mainnet)
        """
        u = urlparse(uri)
        if u.scheme != const.ARC90_URI_SCHEME_NAME.decode():
            raise InvalidArc90UriError(
                f"Not an {const.ARC90_URI_SCHEME_NAME.decode()}:// URI"
            )

        compliance = Arc90Compliance.parse("#" + u.fragment if u.fragment else None)

        # Parse query
        qs = parse_qs(u.query, keep_blank_values=True)
        if const.ARC90_URI_BOX_QUERY_NAME.decode() not in qs:
            raise InvalidArc90UriError(
                f"Missing '{const.ARC90_URI_BOX_QUERY_NAME.decode()}' query parameter"
            )
        box_values = qs.get(const.ARC90_URI_BOX_QUERY_NAME.decode(), [""])
        box_value = box_values[0] if box_values else ""

        # Identify app_id & netauth based on authority / path conventions.
        netloc = u.netloc or ""
        path_segs = [s for s in u.path.split("/") if s]

        netauth: str | None = None
        app_id: int | None = None

        if netloc.startswith("net:"):
            netauth = netloc
            if (
                len(path_segs) < 2
                or path_segs[0] != const.ARC90_URI_APP_PATH_NAME.decode()
            ):
                raise InvalidArc90UriError(
                    f"Expected path '/{const.ARC90_URI_APP_PATH_NAME.decode()}/<app_id>' for net: URIs"
                )
            try:
                app_id = int(path_segs[1])
            except ValueError as e:
                raise InvalidArc90UriError("Invalid app id in path") from e
        elif netloc == const.ARC90_URI_APP_PATH_NAME.decode() and len(path_segs) >= 1:
            # MainNet example: algorand://app/<app_id>?box=...
            try:
                app_id = int(path_segs[0])
            except ValueError as e:
                raise InvalidArc90UriError("Invalid app id in path") from e
        else:
            raise InvalidArc90UriError("Unrecognized ARC-90 app URI shape")

        # Parse box name (optional/partial)
        box_name: bytes | None
        if box_value == "":
            box_name = None
        else:
            try:
                box_name = b64url_decode(box_value)
            except (binascii.Error, ValueError, UnicodeDecodeError) as e:
                raise InvalidArc90UriError("Invalid base64url box name") from e
            if len(box_name) != const.ASSET_METADATA_BOX_KEY_SIZE:
                raise InvalidArc90UriError(
                    "ARC-89 expects an 8-byte box name (asset id)"
                )

        return Arc90Uri(
            netauth=netauth, app_id=app_id, box_name=box_name, compliance=compliance
        )


def complete_partial_asset_url(asset_url: str, asset_id: int) -> str:
    """
    Complete an ARC-89 partial Asset URL (Asset Params `url`) into a full Asset Metadata URI.

    The partial URL is expected to include the registry app reference and `box=` query key, but
    not the box value itself.

    Example (partial):
        algorand://net:testnet/app/752790676?box=#arc89

    Output (complete):
        algorand://net:testnet/app/752790676?box=<base64url(asset_id_bytes)>#arc89
    """
    parsed = Arc90Uri.parse(asset_url)
    if not parsed.is_partial:
        # Already complete
        return parsed.to_uri()
    return parsed.with_asset_id(asset_id).to_uri()
