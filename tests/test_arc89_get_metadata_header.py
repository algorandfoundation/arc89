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


def test_mutable_short_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    header = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=mutable_short_metadata.asset_id),
    ).abi_return
    assert header.identifiers == mutable_short_metadata.identifiers
    assert header.flags == mutable_short_metadata.flags
    assert bytes(header.hash) == mutable_short_metadata.metadata_hash


def test_mutable_maxed_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    header = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=mutable_maxed_metadata.asset_id),
    ).abi_return
    assert header.identifiers == mutable_maxed_metadata.identifiers
    assert header.flags == mutable_maxed_metadata.flags
    assert bytes(header.hash) == mutable_maxed_metadata.metadata_hash


def test_immutable_empty_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_empty_metadata: AssetMetadata,
) -> None:
    header = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=immutable_empty_metadata.asset_id),
    ).abi_return
    assert header.identifiers == immutable_empty_metadata.identifiers
    assert header.flags == immutable_empty_metadata.flags
    assert bytes(header.hash) == immutable_empty_metadata.metadata_hash
    assert header.last_modified_round == immutable_empty_metadata.last_modified_round


def test_immutable_short_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    header = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=immutable_short_metadata.asset_id),
    ).abi_return
    assert header.identifiers == immutable_short_metadata.identifiers
    assert header.flags == immutable_short_metadata.flags
    assert bytes(header.hash) == immutable_short_metadata.metadata_hash
    assert header.last_modified_round == immutable_short_metadata.last_modified_round


def test_immutable_maxed_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_maxed_metadata: AssetMetadata,
) -> None:
    header = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=immutable_maxed_metadata.asset_id),
    ).abi_return
    assert header.identifiers == immutable_maxed_metadata.identifiers
    assert header.flags == immutable_maxed_metadata.flags
    assert bytes(header.hash) == immutable_maxed_metadata.metadata_hash
    assert header.last_modified_round == immutable_maxed_metadata.last_modified_round
