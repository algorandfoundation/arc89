from src.generated.asa_metadata_registry_client import (
    Arc89GetMetadataMbrDeltaArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_get_metadata_mbr_delta_for_existing_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    to_smaller_mbr_delta = empty_metadata.get_mbr_delta(mutable_short_metadata.size)
    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=mutable_short_metadata.asset_id,
            new_metadata_size=empty_metadata.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == to_smaller_mbr_delta.sign
    assert mbr_delta.amount == to_smaller_mbr_delta.amount

    to_larger_mbr_delta = maxed_metadata.get_mbr_delta(mutable_short_metadata.size)
    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=mutable_short_metadata.asset_id,
            new_metadata_size=maxed_metadata.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == to_larger_mbr_delta.sign
    assert mbr_delta.amount == to_larger_mbr_delta.amount


def test_get_metadata_mbr_delta_for_nonexistent_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=empty_metadata.asset_id,
            new_metadata_size=empty_metadata.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == empty_metadata.get_mbr_delta().sign
    assert mbr_delta.amount == empty_metadata.get_mbr_delta().amount

    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=short_metadata.asset_id,
            new_metadata_size=short_metadata.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == short_metadata.get_mbr_delta().sign
    assert mbr_delta.amount == short_metadata.get_mbr_delta().amount

    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=maxed_metadata.asset_id,
            new_metadata_size=maxed_metadata.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == maxed_metadata.get_mbr_delta().sign
    assert mbr_delta.amount == maxed_metadata.get_mbr_delta().amount


# TODO: Test failing conditions
