from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import \
    AsaMetadataRegistryClient, Arc89GetMetadataHeaderArgs
from tests.helpers.factories import AssetMetadata


def test_mutable_empty_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
) -> None:
    header = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=mutable_empty_metadata.asset_id),
    ).abi_return
    assert header.identifiers == mutable_empty_metadata.identifiers
    assert header.flags == mutable_empty_metadata.flags
    assert bytes(header.hash) == mutable_empty_metadata.metadata_hash
    assert header.last_modified_round == mutable_empty_metadata.last_modified_round
