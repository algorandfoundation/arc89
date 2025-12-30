from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from smart_contracts.constants import (
    MAINNET_GH_B64,
    TESTNET_GH_B64,
)

# ---------------------------------------------------------------------------
# Deployment constants
# ---------------------------------------------------------------------------
MAINNET_TRUSTED_DEPLOYER_ADDR: Final[str] = (
    "XODGWLOMKUPTGL3ZV53H3GZZWMCTJVQ5B2BZICFD3STSLA2LPSH6V6RW3I"
)
TESTNET_TRUSTED_DEPLOYER_ADDR: Final[str] = (
    "QYK5DXJ27Y7WIWUJMP3FFOTEU56L4KTRP4CY2GAKRXZHHKLNWV6M7JLYJM"
)

TESTNET_ASA_METADATA_REGISTRY_APP_ID: Final[int] = 752_901_780


@dataclass(frozen=True, slots=True)
class RegistryDeployment:
    """
    A known deployment of the singleton ASA Metadata Registry.

    Note: ARC-89 is still a draft; deployments can change. This SDK keeps the deployment
    list data-only so it can be updated without affecting the rest of the architecture.
    """

    network: Literal["mainnet", "testnet"]
    genesis_hash_b64: str
    app_id: int | None
    creator_address: str | None = None


DEFAULT_DEPLOYMENTS: Final[Mapping[str, RegistryDeployment]] = {
    "testnet": RegistryDeployment(
        network="testnet",
        genesis_hash_b64=TESTNET_GH_B64,
        app_id=TESTNET_ASA_METADATA_REGISTRY_APP_ID,
        creator_address=TESTNET_TRUSTED_DEPLOYER_ADDR,
    ),
    "mainnet": RegistryDeployment(
        network="mainnet",
        genesis_hash_b64=MAINNET_GH_B64,
        app_id=None,  # MainNet app id was TBD in the draft spec snapshot used to build this SDK.
        creator_address=MAINNET_TRUSTED_DEPLOYER_ADDR,
    ),
}
