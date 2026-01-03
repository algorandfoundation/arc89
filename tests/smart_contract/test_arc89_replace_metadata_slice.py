from algokit_utils import CommonAppCallParams, SigningAccount

from src._generated.asa_metadata_registry_client import (
    Arc89ReplaceMetadataSliceArgs,
    AsaMetadataRegistryClient,
)
from src.models import AssetMetadata, AssetMetadataBox


def test_replace_metadata_slice(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id

    offset = 0
    size = 4
    current_slice = mutable_short_metadata.body.raw_bytes[offset : offset + size]
    new_slice = size * b"\x00"
    assert current_slice != new_slice

    asa_metadata_registry_client.send.arc89_replace_metadata_slice(
        args=Arc89ReplaceMetadataSliceArgs(
            asset_id=asset_id,
            offset=offset,
            payload=new_slice,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None
    parsed_box = AssetMetadataBox.parse(asset_id=asset_id, value=box_value)
    updated_metadata = AssetMetadata(
        asset_id=asset_id,
        body=parsed_box.body,
        flags=parsed_box.header.flags,
        deprecated_by=parsed_box.header.deprecated_by,
    )
    replaced_slice = updated_metadata.body.raw_bytes[offset : offset + size]
    assert replaced_slice == new_slice
    assert updated_metadata.body.size == mutable_short_metadata.body.size
    # Note: identifiers are computed by the registry, not stored in AssetMetadata
    assert (
        updated_metadata.flags.reversible_byte
        == mutable_short_metadata.flags.reversible_byte
    )
    assert (
        updated_metadata.flags.irreversible_byte
        == mutable_short_metadata.flags.irreversible_byte
    )
    # Note: last_modified_round is in the header, not in AssetMetadata
    assert updated_metadata.deprecated_by == mutable_short_metadata.deprecated_by
    assert updated_metadata.body.raw_bytes != mutable_short_metadata.body.raw_bytes


# TODO: Test failing conditions
