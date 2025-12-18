from algokit_utils import CommonAppCallParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89SetImmutableArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_set_immutable_flag(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id

    # Verify initial state is False
    assert not mutable_short_metadata.is_immutable

    # Set metadata as immutable and verify
    asa_metadata_registry_client.send.arc89_set_immutable(
        args=Arc89SetImmutableArgs(asset_id=asset_id),
        params=CommonAppCallParams(sender=asset_manager.address),
    )

    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert post_set.is_immutable


# TODO: Test failing conditions
