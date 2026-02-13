import pytest
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    CommonAppCallParams,
    SigningAccount,
)

from asa_metadata_registry import (
    AssetMetadata,
    AssetMetadataBox,
)
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89ReplaceMetadataSliceArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.utils import (
    add_extra_resources,
    create_metadata,
    create_metadata_with_page_count,
    set_immutable,
    set_reversible_flag,
    total_extra_resources,
)


@pytest.mark.parametrize("page_count", range(0, const.MAX_PAGES + 1))
def test_per_page_count(
    algorand_client: AlgorandClient,
    arc_89_asa: int,
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    page_count: int,
) -> None:
    # Create metadata with specific page count
    metadata = create_metadata_with_page_count(arc_89_asa, page_count, b"x")
    asset_id = metadata.asset_id

    # Upload metadata to the registry
    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    # Verify initial state is not immutable
    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None
    parsed_box = AssetMetadataBox.parse(asset_id=asset_id, value=box_value)
    initial_state = AssetMetadata(
        asset_id=asset_id,
        body=parsed_box.body,
        flags=parsed_box.header.flags,
        deprecated_by=parsed_box.header.deprecated_by,
    )
    assert initial_state.body.total_pages() == page_count
    assert not initial_state.flags.irreversible.immutable

    # Set reversible flag
    set_reversible_flag(
        asa_metadata_registry_client, asset_manager, metadata, 3, value=True
    )

    # Replace slice
    if page_count > 0:
        extra_count, total_fee = total_extra_resources(algorand_client, metadata)
        replace_slice = asa_metadata_registry_client.new_group()
        replace_slice.arc89_replace_metadata_slice(
            args=Arc89ReplaceMetadataSliceArgs(
                asset_id=asset_id,
                offset=0,
                payload=b"y" * const.PAGE_SIZE,
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount.from_micro_algo(total_fee),
            ),
        )
        if extra_count > 0:
            add_extra_resources(replace_slice, extra_count)
        replace_slice.send()

    # Set immutable
    set_immutable(asa_metadata_registry_client, asset_manager, metadata)
