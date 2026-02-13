import pytest
from algokit_utils import LogicError

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89GetMetadataMbrDeltaArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err


def test_get_metadata_mbr_delta_for_existing_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    to_smaller_mbr_delta = empty_metadata.get_mbr_delta(
        old_size=mutable_short_metadata.body.size
    )
    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=mutable_short_metadata.asset_id,
            new_metadata_size=empty_metadata.body.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == to_smaller_mbr_delta.sign
    assert mbr_delta.amount == to_smaller_mbr_delta.amount

    to_larger_mbr_delta = maxed_metadata.get_mbr_delta(
        old_size=mutable_short_metadata.body.size
    )
    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=mutable_short_metadata.asset_id,
            new_metadata_size=maxed_metadata.body.size,
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
            new_metadata_size=empty_metadata.body.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == empty_metadata.get_mbr_delta().sign
    assert mbr_delta.amount == empty_metadata.get_mbr_delta().amount

    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=short_metadata.asset_id,
            new_metadata_size=short_metadata.body.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == short_metadata.get_mbr_delta().sign
    assert mbr_delta.amount == short_metadata.get_mbr_delta().amount

    mbr_delta = asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
        args=Arc89GetMetadataMbrDeltaArgs(
            asset_id=maxed_metadata.asset_id,
            new_metadata_size=maxed_metadata.body.size,
        ),
    ).abi_return
    assert mbr_delta is not None
    assert mbr_delta.sign == maxed_metadata.get_mbr_delta().sign
    assert mbr_delta.amount == maxed_metadata.get_mbr_delta().amount


def test_fail_exceeds_max_metadata_size(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.EXCEEDS_MAX_METADATA_SIZE):
        asa_metadata_registry_client.send.arc89_get_metadata_mbr_delta(
            args=Arc89GetMetadataMbrDeltaArgs(
                asset_id=arc_89_asa,
                new_metadata_size=const.MAX_METADATA_SIZE + 1,
            ),
        )
