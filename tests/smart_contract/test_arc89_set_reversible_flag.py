from collections.abc import Callable

import pytest
from algokit_utils import CommonAppCallParams, LogicError, SigningAccount

from asa_metadata_registry import (
    AssetMetadata,
    flags,
)
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID, set_flag_and_verify


@pytest.mark.parametrize(
    "reversible_flag,check_fn",
    [
        (flags.REV_FLG_ARC20, lambda m: m.flags.reversible.arc20),
        (flags.REV_FLG_ARC62, lambda m: m.flags.reversible.arc62),
        (flags.REV_FLG_NTT, lambda m: m.flags.reversible.ntt),
        (flags.REV_FLG_RESERVED_3, lambda m: m.flags.reversible.reserved_3),
        (flags.REV_FLG_RESERVED_4, lambda m: m.flags.reversible.reserved_4),
        (flags.REV_FLG_RESERVED_5, lambda m: m.flags.reversible.reserved_5),
        (flags.REV_FLG_RESERVED_6, lambda m: m.flags.reversible.reserved_6),
        (flags.REV_FLG_RESERVED_7, lambda m: m.flags.reversible.reserved_7),
    ],
)
def test_set_and_clear_reversible_flags(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    reversible_flag: int,
    check_fn: Callable[[AssetMetadata], bool],
) -> None:
    # Verify initial state is False
    assert not check_fn(mutable_short_metadata)

    # Set flag to True and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        reversible_flag,
        check_fn,
        value=True,
    )

    # Set flag to False and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        reversible_flag,
        check_fn,
        value=False,
    )


def test_fail_asa_not_exists(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=NON_EXISTENT_ASA_ID, flag=flags.REV_FLG_ARC20, value=True
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=arc_89_asa, flag=flags.REV_FLG_ARC20, value=True
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        asa_metadata_registry_client.send.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=mutable_short_metadata.asset_id,
                flag=flags.REV_FLG_ARC20,
                value=True,
            ),
            params=CommonAppCallParams(sender=untrusted_account.address),
        )


def test_fail_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.IMMUTABLE):
        asa_metadata_registry_client.send.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=immutable_short_metadata.asset_id,
                flag=flags.REV_FLG_ARC20,
                value=True,
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_flag_idx_invalid(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    invalid_flag_index = flags.REV_FLG_RESERVED_7 + 1  # Out of range
    with pytest.raises(LogicError, match=err.FLAG_IDX_INVALID):
        asa_metadata_registry_client.send.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=mutable_short_metadata.asset_id,
                flag=invalid_flag_index,
                value=True,
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )
