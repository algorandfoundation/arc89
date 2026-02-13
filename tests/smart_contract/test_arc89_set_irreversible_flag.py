from collections.abc import Callable

import pytest
from algokit_utils import (
    AssetConfigParams,
    CommonAppCallParams,
    LogicError,
    SigningAccount,
)

from asa_metadata_registry import (
    AssetMetadata,
    bitmasks,
    flags,
)
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89GetMetadataHeaderArgs,
    Arc89SetIrreversibleFlagArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID, set_flag_and_verify


@pytest.mark.parametrize(
    "irreversible_flag,check_fn",
    [
        (flags.IRR_FLG_RESERVED_3, lambda m: m.flags.irreversible.reserved_3),
        (flags.IRR_FLG_RESERVED_4, lambda m: m.flags.irreversible.reserved_4),
        (flags.IRR_FLG_RESERVED_5, lambda m: m.flags.irreversible.reserved_5),
        (flags.IRR_FLG_RESERVED_6, lambda m: m.flags.irreversible.reserved_6),
    ],
)
def test_set_irreversible_flags(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    irreversible_flag: int,
    check_fn: Callable[[AssetMetadata], bool],
) -> None:
    # Verify initial state is False
    assert not check_fn(mutable_short_metadata)

    # Set flag to True and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        irreversible_flag,
        check_fn,
        reversible=False,
    )


def test_set_burnable_flag(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # Verify initial state is False
    assert not mutable_short_metadata.flags.irreversible.reserved_2

    asa_metadata_registry_client.algorand.send.asset_config(
        AssetConfigParams(
            sender=asset_manager.address,
            asset_id=mutable_short_metadata.asset_id,
            manager=asset_manager.address,
        )
    )
    assert not asa_metadata_registry_client.algorand.asset.get_by_id(
        mutable_short_metadata.asset_id
    ).clawback

    # Set flag to True and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        flags.IRR_FLG_RESERVED_2,
        lambda m: m.flags.irreversible.reserved_2,
        reversible=False,
    )


def test_fail_asa_not_exists(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(
                asset_id=NON_EXISTENT_ASA_ID, flag=flags.IRR_FLG_RESERVED_2
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(
                asset_id=arc_89_asa, flag=flags.IRR_FLG_RESERVED_2
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        asa_metadata_registry_client.send.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(
                asset_id=mutable_short_metadata.asset_id, flag=flags.IRR_FLG_RESERVED_2
            ),
            params=CommonAppCallParams(sender=untrusted_account.address),
        )


def test_fail_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.IMMUTABLE):
        asa_metadata_registry_client.send.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(
                asset_id=immutable_short_metadata.asset_id,
                flag=flags.IRR_FLG_RESERVED_2,
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


@pytest.mark.parametrize(
    "invalid_flag",
    [
        flags.IRR_FLG_IMMUTABLE,  # Cannot set immutable via this method
        flags.IRR_FLG_ARC89_NATIVE,  # Can only be set at creation time
        flags.IRR_FLG_RESERVED_6 + 1,  # Out of valid range
    ],
)
def test_fail_flag_idx_invalid(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    invalid_flag: int,
) -> None:
    with pytest.raises(LogicError, match=err.FLAG_IDX_INVALID):
        asa_metadata_registry_client.send.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(
                asset_id=mutable_short_metadata.asset_id, flag=invalid_flag
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_not_arc54_compliant(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    irr_flags = asa_metadata_registry_client.send.arc89_get_metadata_header(
        args=Arc89GetMetadataHeaderArgs(asset_id=mutable_short_metadata.asset_id)
    ).abi_return.irreversible_flags
    burnable = bool(irr_flags & bitmasks.MASK_IRR_RESERVED_2)
    assert not burnable

    with pytest.raises(LogicError, match=err.ASA_NOT_ARC54_COMPLIANT):
        asa_metadata_registry_client.send.arc89_set_irreversible_flag(
            args=Arc89SetIrreversibleFlagArgs(
                asset_id=mutable_short_metadata.asset_id, flag=flags.IRR_FLG_RESERVED_2
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )
