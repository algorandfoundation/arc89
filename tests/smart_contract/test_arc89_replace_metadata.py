from algokit_utils import SigningAccount

from smart_contracts.asa_metadata_registry.enums import MBR_DELTA_NEG, MBR_DELTA_NULL
from src.generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from src.models import AssetMetadata
from tests.helpers.utils import replace_metadata


def test_replace_with_empty_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = empty_metadata.get_mbr_delta(
        old_size=mutable_short_metadata.body.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_short_metadata.asset_id,
        new_metadata=empty_metadata,
    )
    assert -mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NEG
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_replace_with_smaller_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = short_metadata.get_mbr_delta(
        old_size=mutable_maxed_metadata.body.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_maxed_metadata.asset_id,
        new_metadata=short_metadata,
        extra_resources=1,
    )
    assert -mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NEG
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_replace_with_equal_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = maxed_metadata.get_mbr_delta(
        old_size=mutable_maxed_metadata.body.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_maxed_metadata.asset_id,
        new_metadata=maxed_metadata,
    )
    assert mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NULL
    # TODO: Verify Asset Metadata Box contents matches fixture data


# TODO: Test failing conditions
