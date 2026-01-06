from algokit_utils import CommonAppCallParams, SigningAccount

from asa_metadata_registry import (
    AssetMetadata,
    AssetMetadataBox,
)
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89SetImmutableArgs,
    AsaMetadataRegistryClient,
)


def test_set_immutable_flag(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id

    # Verify initial state is False
    assert not mutable_short_metadata.flags.irreversible.immutable

    # Set metadata as immutable and verify
    asa_metadata_registry_client.send.arc89_set_immutable(
        args=Arc89SetImmutableArgs(asset_id=asset_id),
        params=CommonAppCallParams(sender=asset_manager.address),
    )

    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None
    parsed_box = AssetMetadataBox.parse(asset_id=asset_id, value=box_value)
    post_set = AssetMetadata(
        asset_id=asset_id,
        body=parsed_box.body,
        flags=parsed_box.header.flags,
        deprecated_by=parsed_box.header.deprecated_by,
    )
    assert post_set.flags.irreversible.immutable


# TODO: Test failing conditions
