from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from .codec import b64_decode, b64url_decode, b64url_encode
from .constants import MAINNET_GH_B64, TESTNET_GH_B64

# ---------------------------------------------------------------------------
# Deployment constants
# ---------------------------------------------------------------------------
MAINNET_TRUSTED_DEPLOYER_ADDR: Final[str] = (
    "XODGWLOMKUPTGL3ZV53H3GZZWMCTJVQ5B2BZICFD3STSLA2LPSH6V6RW3I"
)
TESTNET_TRUSTED_DEPLOYER_ADDR: Final[str] = (
    "QYK5DXJ27Y7WIWUJMP3FFOTEU56L4KTRP4CY2GAKRXZHHKLNWV6M7JLYJM"
)

TESTNET_ASA_METADATA_REGISTRY_APP_ID: Final[int] = 753_324_084


@dataclass(frozen=True, slots=True)
class RegistryDeployment:
    """
    A known deployment of the singleton ASA Metadata Registry.

    Note: ARC-89 is still a draft; deployments can change. This SDK keeps the deployment
    list data-only so it can be updated without affecting the rest of the architecture.
    """

    network: Literal["mainnet", "testnet", "localnet"]
    genesis_hash_b64: str | None
    app_id: int | None
    creator_address: str | None = None
    arc90_uri_netauth: str | None = None

    def __post_init__(self) -> None:
        if self.network != "localnet" and self.genesis_hash_b64 is None:
            raise ValueError(
                "`RegistryDeployment.genesis_hash_b64` is required for non-localnet deployments"
            )
        if self.network != "mainnet" and self.arc90_uri_netauth is None:
            raise ValueError(
                "`RegistryDeployment.arc90_uri_netauth` is required for non-mainnet deployments"
            )


DEFAULT_DEPLOYMENTS: Final[Mapping[str, RegistryDeployment]] = {
    "testnet": RegistryDeployment(
        network="testnet",
        genesis_hash_b64=TESTNET_GH_B64,
        app_id=TESTNET_ASA_METADATA_REGISTRY_APP_ID,
        creator_address=TESTNET_TRUSTED_DEPLOYER_ADDR,
        arc90_uri_netauth="net:testnet",
    ),
    "mainnet": RegistryDeployment(
        network="mainnet",
        genesis_hash_b64=MAINNET_GH_B64,
        app_id=None,  # MainNet app id is TBD.
        creator_address=MAINNET_TRUSTED_DEPLOYER_ADDR,
        arc90_uri_netauth=None,
    ),
}


def deployment_for_genesis(genesis_hash_b64: str) -> RegistryDeployment | None:
    """The trusted deployment for a network genesis hash, if any."""
    for d in DEFAULT_DEPLOYMENTS.values():
        if d.genesis_hash_b64 == genesis_hash_b64:
            return d
    return None


def netauth_for_genesis(genesis_hash_b64: str) -> str | None:
    """Canonical ARC-90 netauth for a network: the deployment label, else `gh:<base64url>`."""
    d = deployment_for_genesis(genesis_hash_b64)
    if d is not None:
        return d.arc90_uri_netauth
    return "gh:" + b64url_encode(b64_decode(genesis_hash_b64))


def netauth_matches_genesis(netauth: str | None, genesis_hash_b64: str) -> bool:
    """True if an ARC-90 netauth denotes the network with the given genesis hash."""
    if netauth is None:
        return genesis_hash_b64 == MAINNET_GH_B64
    if netauth.startswith("gh:"):
        try:
            return b64url_decode(netauth[3:]) == b64_decode(genesis_hash_b64)
        except Exception:
            return False
    d = deployment_for_genesis(genesis_hash_b64)
    if d is None:  # unknown network (e.g. LocalNet): a label cannot be verified
        return netauth.startswith("net:")
    return d.arc90_uri_netauth == netauth
