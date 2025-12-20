from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89IsMetadataImmutableArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_immutable_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    is_immutable = asa_metadata_registry_client.send.arc89_is_metadata_immutable(
        args=Arc89IsMetadataImmutableArgs(asset_id=immutable_short_metadata.asset_id),
    ).abi_return
    assert is_immutable


def test_mutable_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    is_immutable = asa_metadata_registry_client.send.arc89_is_metadata_immutable(
        args=Arc89IsMetadataImmutableArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert not is_immutable


# TODO: Test failing conditions
