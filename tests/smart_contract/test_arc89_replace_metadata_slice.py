import pytest
from algokit_utils import CommonAppCallParams, LogicError, SigningAccount

from asa_metadata_registry import (
    AssetMetadata,
    AssetMetadataBox,
)
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89ReplaceMetadataSliceArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import (
    NON_EXISTENT_ASA_ID,
    build_replace_metadata_slice_composer,
)


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


def test_fail_asa_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    """
    Note: The contract calls _get_metadata_size before the precondition check,
    so the error is a box access error rather than ASA_NOT_EXIST.
    """
    composer = build_replace_metadata_slice_composer(
        asa_metadata_registry_client,
        asset_manager,
        NON_EXISTENT_ASA_ID,
        offset=0,
        payload=b"test",
    )

    with pytest.raises(LogicError, match="check Box exists"):
        composer.send()


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    """
    Note: The contract calls _get_metadata_size before the precondition check,
    so the error is a box access error rather than ASSET_METADATA_NOT_EXIST.
    """
    composer = build_replace_metadata_slice_composer(
        asa_metadata_registry_client,
        asset_manager,
        arc_89_asa,
        offset=0,
        payload=b"test",
    )

    with pytest.raises(LogicError, match="check Box exists"):
        composer.send()


def test_fail_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    composer = build_replace_metadata_slice_composer(
        asa_metadata_registry_client,
        asset_manager,
        immutable_short_metadata.asset_id,
        offset=0,
        payload=b"test",
    )

    with pytest.raises(LogicError, match=err.IMMUTABLE):
        composer.send()


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    composer = build_replace_metadata_slice_composer(
        asa_metadata_registry_client,
        untrusted_account,
        mutable_short_metadata.asset_id,
        offset=0,
        payload=b"test",
    )

    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        composer.send()


def test_fail_exceeds_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    metadata_size = mutable_short_metadata.body.size
    # Try to replace beyond the end of the metadata
    composer = build_replace_metadata_slice_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata.asset_id,
        offset=metadata_size,  # Start at the end
        payload=b"x",  # Even 1 byte will exceed the range
    )

    with pytest.raises(LogicError, match=err.EXCEEDS_METADATA_SIZE):
        composer.send()


def test_fail_exceeds_metadata_size_large_offset(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    metadata_size = mutable_short_metadata.body.size
    # Try to replace from middle but with payload that exceeds boundary
    payload_that_exceeds = b"x" * (metadata_size + 1)
    composer = build_replace_metadata_slice_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata.asset_id,
        offset=1,  # Start at offset 1
        payload=payload_that_exceeds,  # Will exceed boundary
    )

    with pytest.raises(LogicError, match=err.EXCEEDS_METADATA_SIZE):
        composer.send()
