from algokit_utils import SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry.enums import MBR_DELTA_NEG, MBR_DELTA_NULL
from tests.helpers.factories import AssetMetadata
from tests.helpers.utils import replace_metadata


def test_replace_with_empty_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = empty_metadata.get_mbr_delta(
        old_size=uploaded_short_metadata.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=uploaded_short_metadata.asset_id,
        new_metadata=empty_metadata,
    )
    assert -mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount.micro_algo
    assert mbr_delta.sign == MBR_DELTA_NEG
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_replace_with_smaller_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_maxed_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = short_metadata.get_mbr_delta(
        old_size=uploaded_maxed_metadata.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=uploaded_maxed_metadata.asset_id,
        new_metadata=short_metadata,
        extra_resources=1,
    )
    assert -mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount.micro_algo
    assert mbr_delta.sign == MBR_DELTA_NEG
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_replace_with_equal_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_maxed_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = maxed_metadata.get_mbr_delta(
        old_size=uploaded_maxed_metadata.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=uploaded_maxed_metadata.asset_id,
        new_metadata=maxed_metadata,
    )
    assert mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount.micro_algo
    assert mbr_delta.sign == MBR_DELTA_NULL
    # TODO: Verify Asset Metadata Box contents matches fixture data


# TODO: Test failing conditions
