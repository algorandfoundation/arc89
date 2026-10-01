from collections.abc import Callable

import pytest
from algokit_utils import (
    AssetCreateParams,
    CommonAppCallParams,
    LogicError,
    SigningAccount,
)
from algosdk.logic import get_application_address

from asa_metadata_registry import (
    AssetMetadata,
    IrreversibleFlags,
    MetadataBody,
    MetadataFlags,
    ReversibleFlags,
    flags,
)
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.factories import create_arc3_payload
from tests.helpers.utils import (
    NON_EXISTENT_ASA_ID,
    create_metadata,
    get_metadata_from_state,
    set_flag_and_verify,
)


@pytest.mark.parametrize(
    "reversible_flag,check_fn",
    [
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


def _set_flag(
    client: AsaMetadataRegistryClient,
    manager: SigningAccount,
    asset_id: int,
    flag: int,
    *,
    value: bool,
) -> None:
    client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(asset_id=asset_id, flag=flag, value=value),
        params=CommonAppCallParams(sender=manager.address),
    )


def _create_arc3_record(
    client: AsaMetadataRegistryClient,
    manager: SigningAccount,
    *,
    properties: dict[str, object] | None,
    reversible: ReversibleFlags | None = None,
    clawback: str | None = None,
) -> int:
    asset_id = client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=manager.address,
            manager=manager.address,
            total=42,
            asset_name="Test" + const.ARC3_NAME_SUFFIX.decode(),
            default_frozen=clawback is not None,
            clawback=clawback,
        )
    ).asset_id
    metadata = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=create_arc3_payload(name="Test", properties=properties),
        flags=MetadataFlags(
            reversible=reversible or ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc3=True),
        ),
    )
    create_metadata(
        asset_manager=manager,
        asa_metadata_registry_client=client,
        asset_id=asset_id,
        metadata=metadata,
    )
    return asset_id


def test_set_arc20_flag_non_arc3(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    # ASA level only: DefaultFrozen with a Clawback Address
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            default_frozen=True,
            clawback=asset_manager.address,
        )
    ).asset_id
    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=AssetMetadata(
            asset_id=asset_id,
            body=MetadataBody(raw_bytes=b'{"name":"Smart"}'),
            flags=MetadataFlags.empty(),
            deprecated_by=0,
        ),
    )

    _set_flag(
        asa_metadata_registry_client,
        asset_manager,
        asset_id,
        flags.REV_FLG_ARC20,
        value=True,
    )
    record = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert record.header.flags.reversible.arc20


def test_fail_set_arc20_flag_asa_not_compliant(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # Not DefaultFrozen, no Clawback Address
    with pytest.raises(LogicError, match=err.ASA_NOT_ARC20_COMPLIANT):
        _set_flag(
            asa_metadata_registry_client,
            asset_manager,
            mutable_short_metadata.asset_id,
            flags.REV_FLG_ARC20,
            value=True,
        )


def test_arc20_flag_arc3_at_creation(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    app_id = 123
    asset_id = _create_arc3_record(
        asa_metadata_registry_client,
        asset_manager,
        properties={"arc-20": {"application-id": app_id}},
        reversible=ReversibleFlags(arc20=True),
        clawback=get_application_address(app_id),
    )
    record = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert record.header.flags.reversible.arc20


def test_set_arc62_flag_arc3(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    asset_id = _create_arc3_record(
        asa_metadata_registry_client,
        asset_manager,
        properties={"arc-62": {"application-id": 77}},
    )
    _set_flag(
        asa_metadata_registry_client,
        asset_manager,
        asset_id,
        flags.REV_FLG_ARC62,
        value=True,
    )
    record = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert record.header.flags.reversible.arc62
