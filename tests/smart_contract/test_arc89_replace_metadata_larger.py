from algokit_utils import SigningAccount

from smart_contracts.asa_metadata_registry.enums import MBR_DELTA_POS
from src.generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from src.models import AssetMetadata
from tests.helpers.utils import replace_metadata


def _assert_metadata_replaced_with_larger(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    old_metadata: AssetMetadata,
    new_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = new_metadata.get_mbr_delta(old_size=old_metadata.body.size)
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=old_metadata.asset_id,
        new_metadata=new_metadata,
    )
    assert mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_POS
    # TODO: Verify Asset Metadata Box contents matches fixture data


def test_replace_empty_with_short_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    _assert_metadata_replaced_with_larger(
        asset_manager,
        asa_metadata_registry_client,
        mutable_empty_metadata,
        short_metadata,
    )


def test_replace_empty_with_maxed_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    _assert_metadata_replaced_with_larger(
        asset_manager,
        asa_metadata_registry_client,
        mutable_empty_metadata,
        maxed_metadata,
    )


def test_replace_short_with_maxed_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    _assert_metadata_replaced_with_larger(
        asset_manager,
        asa_metadata_registry_client,
        mutable_short_metadata,
        maxed_metadata,
    )


# TODO: Test failing conditions
