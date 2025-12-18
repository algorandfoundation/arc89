from algokit_utils import CommonAppCallParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import flags
from tests.helpers import bitmasks
from tests.helpers.factories import AssetMetadata


def test_set_and_clear_reversible_flags(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_short_metadata: AssetMetadata,
) -> None:
    asset_id = uploaded_short_metadata.asset_id

    assert not uploaded_short_metadata.is_arc20
    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_ARC20,
            value=True,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert post_set.is_arc20

    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_ARC20,
            value=False,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert not post_set.is_arc20

    assert not uploaded_short_metadata.is_arc62
    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_ARC62,
            value=True,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert post_set.is_arc62

    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_ARC62,
            value=False,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert not post_set.is_arc62

    assert not uploaded_short_metadata.flags & bitmasks.MASK_RESERVED_2
    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_RESERVED_2,
            value=True,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert post_set.flags & bitmasks.MASK_RESERVED_2

    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_RESERVED_2,
            value=False,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert not post_set.flags & bitmasks.MASK_RESERVED_2

    assert not uploaded_short_metadata.flags & bitmasks.MASK_RESERVED_3
    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_RESERVED_3,
            value=True,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert post_set.flags & bitmasks.MASK_RESERVED_3

    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flags.FLG_RESERVED_3,
            value=False,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert not post_set.flags & bitmasks.MASK_RESERVED_3


# TODO: Test failing conditions
