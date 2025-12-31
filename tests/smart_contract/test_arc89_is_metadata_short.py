from src.generated.asa_metadata_registry_client import (
    Arc89IsMetadataShortArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_short_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    is_short = asa_metadata_registry_client.send.arc89_is_metadata_short(
        args=Arc89IsMetadataShortArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert is_short is not None
    assert is_short.flag


def test_long_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    is_short = asa_metadata_registry_client.send.arc89_is_metadata_short(
        args=Arc89IsMetadataShortArgs(asset_id=mutable_maxed_metadata.asset_id),
    ).abi_return
    assert is_short is not None
    assert not is_short.flag


# TODO: Test failing conditions
