from algokit_utils import SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata
from tests.helpers.utils import create_metadata


def test_empty_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    empty_metadata: AssetMetadata,
) -> None:
    creation_mbr_delta = empty_metadata.get_mbr_delta(old_size=None)
    mbr_delta = create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=empty_metadata.asset_id,
        metadata=empty_metadata,
    )
    assert mbr_delta.amount == creation_mbr_delta.amount.micro_algo
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_short_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    short_metadata: AssetMetadata,
) -> None:
    creation_mbr_delta = short_metadata.get_mbr_delta(old_size=None)
    mbr_delta = create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=short_metadata.asset_id,
        metadata=short_metadata,
    )
    assert mbr_delta.amount == creation_mbr_delta.amount.micro_algo
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_maxed_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    maxed_metadata: AssetMetadata,
) -> None:
    creation_mbr_delta = maxed_metadata.get_mbr_delta(old_size=None)
    mbr_delta = create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=maxed_metadata.asset_id,
        metadata=maxed_metadata,
    )
    assert mbr_delta.amount == creation_mbr_delta.amount.micro_algo
    # TODO: Verify Asset Metadata Box contents matches fixture data


# TODO: Test failing conditions
