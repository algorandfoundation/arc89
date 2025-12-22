import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89SetImmutableArgs,
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata, create_metadata_with_page_count
from tests.helpers.utils import add_extra_resources, create_metadata, pages_min_fee


@pytest.mark.parametrize("page_count", range(0, const.MAX_PAGES + 1))
def test_set_flag_with_page_count(
    arc_89_asa: int,
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    page_count: int,
) -> None:
    # Create metadata with specific page count
    metadata = create_metadata_with_page_count(arc_89_asa, page_count)
    asset_id = metadata.asset_id

    # Upload metadata to the registry
    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    # Verify initial state is not immutable
    initial_state = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert initial_state.total_pages == page_count

    # Set reversible flag
    set_reversible = asa_metadata_registry_client.new_group()
    set_reversible.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(asset_id=asset_id, flag=3, value=True),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount.from_micro_algo(pages_min_fee(metadata)),
        ),
    )
    if metadata.total_pages > 15:
        add_extra_resources(set_reversible)
    set_reversible.send()


@pytest.mark.parametrize("page_count", range(0, const.MAX_PAGES + 1))
def test_set_immutable_with_page_count(
    arc_89_asa: int,
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    page_count: int,
) -> None:
    # Create metadata with specific page count
    metadata = create_metadata_with_page_count(arc_89_asa, page_count)
    asset_id = metadata.asset_id

    # Upload metadata to the registry
    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    # Verify initial state is not immutable
    initial_state = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert initial_state.total_pages == page_count
    assert not initial_state.is_immutable

    # Set immutable
    set_immutable = asa_metadata_registry_client.new_group()
    set_immutable.arc89_set_immutable(
        args=Arc89SetImmutableArgs(asset_id=asset_id),
        params=CommonAppCallParams(
            sender=asset_manager.address,
            static_fee=AlgoAmount.from_micro_algo(pages_min_fee(metadata)),
        ),
    )
    if metadata.total_pages > 15:
        add_extra_resources(set_immutable)
    set_immutable.send()
