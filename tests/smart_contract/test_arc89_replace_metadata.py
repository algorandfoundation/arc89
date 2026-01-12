import pytest
from algokit_utils import LogicError, SigningAccount

from asa_metadata_registry import (
    AssetMetadata,
    MetadataBody,
    MetadataFlags,
)
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from smart_contracts.asa_metadata_registry.enums import MBR_DELTA_NEG, MBR_DELTA_NULL
from tests.helpers.utils import (
    NON_EXISTENT_ASA_ID,
    build_replace_metadata_composer,
    get_metadata_from_state,
    replace_metadata,
)


def _assert_metadata_replaced(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    prev_metadata: AssetMetadata,
    new_metadata: AssetMetadata,
    prev_last_modified_round: int,
) -> None:
    """Verify that metadata was replaced correctly in the box storage."""
    updated_metadata = get_metadata_from_state(
        asa_metadata_registry_client, prev_metadata.asset_id
    )
    # Only metadata body is replaced (note identifiers and hash are automatically updated)
    assert updated_metadata.body.raw_bytes == new_metadata.body.raw_bytes
    assert updated_metadata.header.identifiers == new_metadata.identifiers_byte
    assert updated_metadata.header.flags == prev_metadata.flags
    assert updated_metadata.header.deprecated_by == prev_metadata.deprecated_by
    expected_metadata = AssetMetadata(
        asset_id=prev_metadata.asset_id,
        body=new_metadata.body,
        flags=prev_metadata.flags,
        deprecated_by=prev_metadata.deprecated_by,
    )
    assert (
        updated_metadata.header.metadata_hash
        == expected_metadata.compute_metadata_hash()
    )
    assert updated_metadata.header.last_modified_round > prev_last_modified_round


def test_replace_with_empty_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
) -> None:
    prev_metadata = get_metadata_from_state(
        asa_metadata_registry_client,
        mutable_short_metadata.asset_id,
    )
    replace_mbr_delta = empty_metadata.get_mbr_delta(
        old_size=mutable_short_metadata.body.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_short_metadata.asset_id,
        new_metadata=empty_metadata,
    )
    assert -mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NEG

    _assert_metadata_replaced(
        asa_metadata_registry_client,
        mutable_short_metadata,
        empty_metadata,
        prev_metadata.header.last_modified_round,
    )


def test_replace_with_smaller_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    prev_metadata = get_metadata_from_state(
        asa_metadata_registry_client,
        mutable_maxed_metadata.asset_id,
    )
    replace_mbr_delta = short_metadata.get_mbr_delta(
        old_size=mutable_maxed_metadata.body.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_maxed_metadata.asset_id,
        new_metadata=short_metadata,
        extra_resources=1,
    )
    assert -mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NEG

    _assert_metadata_replaced(
        asa_metadata_registry_client,
        mutable_maxed_metadata,
        short_metadata,
        prev_metadata.header.last_modified_round,
    )


def test_replace_with_equal_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    prev_metadata = get_metadata_from_state(
        asa_metadata_registry_client,
        mutable_maxed_metadata.asset_id,
    )
    replace_mbr_delta = maxed_metadata.get_mbr_delta(
        old_size=mutable_maxed_metadata.body.size
    )
    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=mutable_maxed_metadata.asset_id,
        new_metadata=maxed_metadata,
    )
    assert mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_NULL

    _assert_metadata_replaced(
        asa_metadata_registry_client,
        mutable_maxed_metadata,
        maxed_metadata,
        prev_metadata.header.last_modified_round,
    )


def test_fail_asa_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    empty_metadata: AssetMetadata,
) -> None:
    composer = build_replace_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        NON_EXISTENT_ASA_ID,
        empty_metadata,
    )

    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        composer.send()


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
    empty_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        replace_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=arc_89_asa,
            new_metadata=empty_metadata,
        )


def test_fail_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.IMMUTABLE):
        replace_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=immutable_short_metadata.asset_id,
            new_metadata=empty_metadata,
        )


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
) -> None:
    composer = build_replace_metadata_composer(
        asa_metadata_registry_client,
        untrusted_account,
        mutable_short_metadata.asset_id,
        empty_metadata,
    )

    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        composer.send()


def test_fail_larger_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    # mutable_empty_metadata has size 0, short_metadata has size > 0
    # Using arc89_replace_metadata (not larger) should fail
    composer = build_replace_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_empty_metadata.asset_id,
        short_metadata,
    )

    with pytest.raises(LogicError, match=err.LARGER_METADATA_SIZE):
        composer.send()


def test_fail_exceeds_max_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    composer = build_replace_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_maxed_metadata.asset_id,
        mutable_maxed_metadata,
        metadata_size_override=const.MAX_METADATA_SIZE + 1,
    )

    with pytest.raises(LogicError, match=err.EXCEEDS_MAX_METADATA_SIZE):
        composer.send()


def test_fail_metadata_size_mismatch(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    # Declare a size smaller than maxed but provide even smaller payload
    declared_size = 100
    actual_payload = b"x" * 10  # Smaller than declared

    actual_metadata = AssetMetadata(
        asset_id=mutable_maxed_metadata.asset_id,
        body=MetadataBody(raw_bytes=actual_payload),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )

    composer = build_replace_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_maxed_metadata.asset_id,
        actual_metadata,
        metadata_size_override=declared_size,
        payload_override=actual_payload,
    )

    with pytest.raises(LogicError, match=err.METADATA_SIZE_MISMATCH):
        composer.send()
