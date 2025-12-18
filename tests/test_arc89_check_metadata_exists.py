from algokit_utils import AssetDestroyParams, CommonAppCallParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89CheckMetadataExistsArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_asset_exists_metadata_not_uploaded(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    short_metadata: AssetMetadata,
) -> None:
    metadata_existence = asa_metadata_registry_client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=short_metadata.asset_id),
    ).abi_return
    assert metadata_existence.asa_exists
    assert not metadata_existence.metadata_exists


def test_asset_exists_metadata_uploaded(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    metadata_existence = asa_metadata_registry_client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert metadata_existence.asa_exists
    assert metadata_existence.metadata_exists


def test_asset_not_exists_metadata_uploaded(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asa_metadata_registry_client.algorand.send.asset_destroy(
        params=AssetDestroyParams(
            asset_id=mutable_short_metadata.asset_id, sender=asset_manager.address
        )
    )

    metadata_existence = asa_metadata_registry_client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert not metadata_existence.asa_exists
    assert metadata_existence.metadata_exists


def test_asset_not_exists_metadata_not_uploaded(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    metadata_existence = asa_metadata_registry_client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=420),
        params=CommonAppCallParams(asset_references=[420]),
    ).abi_return
    assert not metadata_existence.asa_exists
    assert not metadata_existence.metadata_exists
