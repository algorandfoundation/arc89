import pytest
from algokit_utils import AlgoAmount, LogicError, SigningAccount

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from smart_contracts.asa_metadata_registry.enums import MBR_DELTA_POS
from tests.helpers.utils import (
    NON_EXISTENT_ASA_ID,
    build_replace_metadata_larger_composer,
    get_mbr_delta_payment,
    get_metadata_from_state,
    replace_metadata,
)


def _assert_metadata_replaced_with_larger(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    old_metadata: AssetMetadata,
    new_metadata: AssetMetadata,
) -> None:
    replace_mbr_delta = new_metadata.get_mbr_delta(old_size=old_metadata.body.size)

    # Fetch the last updated round before replacement
    metadata_before = get_metadata_from_state(
        asa_metadata_registry_client, old_metadata.asset_id
    )
    last_modified_round_before = metadata_before.header.last_modified_round

    mbr_delta = replace_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=old_metadata.asset_id,
        new_metadata=new_metadata,
    )
    assert mbr_delta.amount == replace_mbr_delta.signed_amount
    assert mbr_delta.amount == replace_mbr_delta.amount
    assert mbr_delta.sign == MBR_DELTA_POS

    updated_metadata = get_metadata_from_state(
        asa_metadata_registry_client, old_metadata.asset_id
    )
    # Only metadata body is replaced (note identifiers and hash are automatically updated)
    assert updated_metadata.body.raw_bytes == new_metadata.body.raw_bytes
    assert updated_metadata.header.identifiers == new_metadata.identifiers_byte
    assert updated_metadata.header.flags == old_metadata.flags
    assert updated_metadata.header.deprecated_by == old_metadata.deprecated_by
    expected_metadata = AssetMetadata(
        asset_id=old_metadata.asset_id,
        body=new_metadata.body,
        flags=old_metadata.flags,
        deprecated_by=old_metadata.deprecated_by,
    )
    assert (
        updated_metadata.header.metadata_hash
        == expected_metadata.compute_metadata_hash()
    )
    assert updated_metadata.header.last_modified_round > last_modified_round_before


def test_replace_empty_with_short_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    _assert_metadata_replaced_with_larger(
        asset_manager,
        asa_metadata_registry_client,
        mutable_empty_metadata,
        short_metadata,
    )


def test_replace_empty_with_maxed_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    _assert_metadata_replaced_with_larger(
        asset_manager,
        asa_metadata_registry_client,
        mutable_empty_metadata,
        maxed_metadata,
    )


def test_replace_short_with_maxed_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    _assert_metadata_replaced_with_larger(
        asset_manager,
        asa_metadata_registry_client,
        mutable_short_metadata,
        maxed_metadata,
    )


def test_fail_asa_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    short_metadata: AssetMetadata,
) -> None:
    mbr_delta = short_metadata.get_mbr_delta(old_size=0)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=mbr_delta.amount),
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        NON_EXISTENT_ASA_ID,
        short_metadata,
        mbr_payment,
    )

    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        composer.send()


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
    short_metadata: AssetMetadata,
) -> None:
    mbr_delta = short_metadata.get_mbr_delta(old_size=0)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=mbr_delta.amount),
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        arc_89_asa,
        short_metadata,
        mbr_payment,
    )

    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        composer.send()


def test_fail_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    mbr_delta = short_metadata.get_mbr_delta(old_size=0)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=mbr_delta.amount),
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        immutable_empty_metadata.asset_id,
        short_metadata,
        mbr_payment,
    )

    with pytest.raises(LogicError, match=err.IMMUTABLE):
        composer.send()


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    mbr_delta = short_metadata.get_mbr_delta(old_size=0)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        untrusted_account,
        AlgoAmount(micro_algo=mbr_delta.amount),
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        untrusted_account,
        mutable_empty_metadata.asset_id,
        short_metadata,
        mbr_payment,
    )

    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        composer.send()


def test_fail_smaller_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    empty_metadata: AssetMetadata,
) -> None:
    # mutable_short_metadata has size > 0, empty_metadata has size 0
    # Using arc89_replace_metadata_larger should fail because size is not larger
    mbr_delta = empty_metadata.get_mbr_delta(old_size=mutable_short_metadata.body.size)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=mbr_delta.amount),
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata.asset_id,
        empty_metadata,
        mbr_payment,
    )

    with pytest.raises(LogicError, match=err.SMALLER_METADATA_SIZE):
        composer.send()


def test_fail_mbr_delta_receiver_invalid(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    mbr_delta = short_metadata.get_mbr_delta(old_size=0)
    # Payment to wrong receiver (asset_manager instead of app address)
    wrong_receiver_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=mbr_delta.amount),
        receiver_override=asset_manager.address,  # Wrong receiver!
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_empty_metadata.asset_id,
        short_metadata,
        wrong_receiver_payment,
    )

    with pytest.raises(LogicError, match=err.MBR_DELTA_RECEIVER_INVALID):
        composer.send()


def test_fail_mbr_delta_amount_invalid(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    mbr_delta = short_metadata.get_mbr_delta(old_size=0)
    # Payment with insufficient amount (1 microAlgo instead of required MBR)
    insufficient_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=mbr_delta.amount),
        amount_override=1,  # Insufficient amount!
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_empty_metadata.asset_id,
        short_metadata,
        insufficient_payment,
    )

    with pytest.raises(LogicError, match=err.MBR_DELTA_AMOUNT_INVALID):
        composer.send()


def test_fail_exceeds_max_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    maxed_metadata: AssetMetadata,
) -> None:
    mbr_delta = maxed_metadata.get_mbr_delta(old_size=mutable_short_metadata.body.size)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(micro_algo=mbr_delta.amount),
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata.asset_id,
        maxed_metadata,
        mbr_payment,
        metadata_size_override=const.MAX_METADATA_SIZE + 1,
    )

    with pytest.raises(LogicError, match=err.EXCEEDS_MAX_METADATA_SIZE):
        composer.send()


def test_fail_metadata_size_mismatch(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
    short_metadata: AssetMetadata,
) -> None:
    # Declare a larger size but provide smaller payload
    declared_size = short_metadata.body.size + 100
    actual_payload = short_metadata.body.raw_bytes  # Smaller than declared

    mbr_delta = short_metadata.get_mbr_delta(old_size=mutable_empty_metadata.body.size)
    mbr_payment = get_mbr_delta_payment(
        asa_metadata_registry_client,
        asset_manager,
        AlgoAmount(
            micro_algo=mbr_delta.amount + 100 * const.BYTE_MBR
        ),  # Extra MBR for declared size
    )

    composer = build_replace_metadata_larger_composer(
        asa_metadata_registry_client,
        asset_manager,
        mutable_empty_metadata.asset_id,
        short_metadata,
        mbr_payment,
        metadata_size_override=declared_size,
        payload_override=actual_payload,
    )

    with pytest.raises(LogicError, match=err.METADATA_SIZE_MISMATCH):
        composer.send()
