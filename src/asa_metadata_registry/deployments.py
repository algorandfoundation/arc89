from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

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
    "localnet": RegistryDeployment(
        network="localnet",
        genesis_hash_b64=None,
        app_id=None,
        creator_address=None,
        arc90_uri_netauth="net:localnet",
    ),
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
