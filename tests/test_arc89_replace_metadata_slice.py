from algokit_utils import CommonAppCallParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89ReplaceMetadataSliceArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_replace_metadata_slice(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id

    offset = 0
    size = 4
    current_slice = mutable_short_metadata.metadata_bytes[offset : offset + size]
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
    updated_metadata = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    replaced_slice = updated_metadata.metadata_bytes[offset : offset + size]
    assert replaced_slice == new_slice
    assert updated_metadata.size == mutable_short_metadata.size
    assert updated_metadata.identifiers == mutable_short_metadata.identifiers
    assert updated_metadata.reversible_flags == mutable_short_metadata.reversible_flags
    assert (
        updated_metadata.irreversible_flags == mutable_short_metadata.irreversible_flags
    )
    assert (
        updated_metadata.last_modified_round
        != mutable_short_metadata.last_modified_round
    )
    assert updated_metadata.deprecated_by == mutable_short_metadata.deprecated_by
    assert updated_metadata.metadata_bytes != mutable_short_metadata.metadata_bytes


# TODO: Test failing conditions
