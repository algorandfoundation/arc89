"""
Unit tests for src.asa_metadata_registry.deployments module.

Tests cover:
- RegistryDeployment valid construction across networks
- RegistryDeployment constructor validation errors
- RegistryDeployment immutability
- DEFAULT_DEPLOYMENTS canonical values
"""

from dataclasses import FrozenInstanceError
from typing import Literal

import pytest

from asa_metadata_registry import DEFAULT_DEPLOYMENTS
from asa_metadata_registry.constants import MAINNET_GH_B64, TESTNET_GH_B64
from asa_metadata_registry.deployments import (
    MAINNET_TRUSTED_DEPLOYER_ADDR,
    TESTNET_ASA_METADATA_REGISTRY_APP_ID,
    TESTNET_TRUSTED_DEPLOYER_ADDR,
    RegistryDeployment,
)


class TestRegistryDeployment:
    """Tests for RegistryDeployment construction and validation."""

    def test_valid_initialization_for_all_networks(self) -> None:
        """Test valid initialization for localnet, testnet, and mainnet."""
        localnet = RegistryDeployment(
            network="localnet",
            genesis_hash_b64=None,
            app_id=None,
            creator_address=None,
            arc90_uri_netauth="net:localnet",
        )
        testnet = RegistryDeployment(
            network="testnet",
            genesis_hash_b64=TESTNET_GH_B64,
            app_id=123,
            creator_address=TESTNET_TRUSTED_DEPLOYER_ADDR,
            arc90_uri_netauth="net:testnet",
        )
        mainnet = RegistryDeployment(
            network="mainnet",
            genesis_hash_b64=MAINNET_GH_B64,
            app_id=None,
            creator_address=MAINNET_TRUSTED_DEPLOYER_ADDR,
            arc90_uri_netauth=None,
        )

        assert localnet.network == "localnet"
        assert testnet.network == "testnet"
        assert mainnet.network == "mainnet"

    @pytest.mark.parametrize("network", ["testnet", "mainnet"])
    def test_raises_when_genesis_hash_is_null_for_non_localnet(
        self, network: Literal["testnet", "mainnet"]
    ) -> None:
        """Test validation error when genesis_hash_b64 is missing on non-localnet."""
        with pytest.raises(ValueError, match="genesis_hash_b64"):
            RegistryDeployment(
                network=network,
                genesis_hash_b64=None,
                app_id=(
                    TESTNET_ASA_METADATA_REGISTRY_APP_ID
                    if network == "testnet"
                    else None
                ),
                creator_address=(
                    TESTNET_TRUSTED_DEPLOYER_ADDR
                    if network == "testnet"
                    else MAINNET_TRUSTED_DEPLOYER_ADDR
                ),
                arc90_uri_netauth="net:testnet" if network == "testnet" else None,
            )

    @pytest.mark.parametrize("network", ["testnet", "localnet"])
    def test_raises_when_arc90_netauth_is_null_for_non_mainnet(
        self, network: Literal["testnet", "localnet"]
    ) -> None:
        """Test validation error when arc90_uri_netauth is missing on non-mainnet."""
        with pytest.raises(ValueError, match="arc90_uri_netauth"):
            RegistryDeployment(
                network=network,
                genesis_hash_b64=TESTNET_GH_B64 if network == "testnet" else None,
                app_id=(
                    TESTNET_ASA_METADATA_REGISTRY_APP_ID
                    if network == "testnet"
                    else None
                ),
                creator_address=(
                    TESTNET_TRUSTED_DEPLOYER_ADDR if network == "testnet" else None
                ),
                arc90_uri_netauth=None,
            )

    def test_instance_is_immutable(self) -> None:
        """Test that RegistryDeployment instances are immutable."""
        deployment = RegistryDeployment(
            network="testnet",
            genesis_hash_b64=TESTNET_GH_B64,
            app_id=TESTNET_ASA_METADATA_REGISTRY_APP_ID,
            creator_address=TESTNET_TRUSTED_DEPLOYER_ADDR,
            arc90_uri_netauth="net:testnet",
        )

        with pytest.raises(FrozenInstanceError):
            deployment.app_id = 2  # type: ignore[misc]


class TestDefaultDeployments:
    """Tests for DEFAULT_DEPLOYMENTS canonical values."""

    def test_default_deployments_match_expected_values(self) -> None:
        """Test DEFAULT_DEPLOYMENTS values against expected deployments."""
        expected_testnet = RegistryDeployment(
            network="testnet",
            genesis_hash_b64=TESTNET_GH_B64,
            app_id=TESTNET_ASA_METADATA_REGISTRY_APP_ID,
            creator_address=TESTNET_TRUSTED_DEPLOYER_ADDR,
            arc90_uri_netauth="net:testnet",
        )
        expected_mainnet = RegistryDeployment(
            network="mainnet",
            genesis_hash_b64=MAINNET_GH_B64,
            app_id=None,
            creator_address=MAINNET_TRUSTED_DEPLOYER_ADDR,
            arc90_uri_netauth=None,
        )

        assert DEFAULT_DEPLOYMENTS["testnet"] == expected_testnet
        assert DEFAULT_DEPLOYMENTS["mainnet"] == expected_mainnet
