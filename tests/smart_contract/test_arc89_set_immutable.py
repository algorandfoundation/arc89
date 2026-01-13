import pytest
from algokit_utils import CommonAppCallParams, LogicError, SigningAccount

from asa_metadata_registry import (
    AssetMetadata,
)
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89SetImmutableArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID, get_metadata_from_state


def test_set_immutable_flag(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id

    # Verify initial state is False
    assert not mutable_short_metadata.flags.irreversible.immutable

    # Set metadata as immutable and verify
    asa_metadata_registry_client.send.arc89_set_immutable(
        args=Arc89SetImmutableArgs(asset_id=asset_id),
        params=CommonAppCallParams(sender=asset_manager.address),
    )

    parsed_box = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    post_set = AssetMetadata(
        asset_id=asset_id,
        body=parsed_box.body,
        flags=parsed_box.header.flags,
        deprecated_by=parsed_box.header.deprecated_by,
    )
    assert post_set.flags.irreversible.immutable


def test_fail_asa_not_exists(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_set_immutable(
            args=Arc89SetImmutableArgs(asset_id=NON_EXISTENT_ASA_ID),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_set_immutable(
            args=Arc89SetImmutableArgs(asset_id=arc_89_asa),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        asa_metadata_registry_client.send.arc89_set_immutable(
            args=Arc89SetImmutableArgs(asset_id=mutable_short_metadata.asset_id),
            params=CommonAppCallParams(sender=untrusted_account.address),
        )


def test_fail_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.IMMUTABLE):
        asa_metadata_registry_client.send.arc89_set_immutable(
            args=Arc89SetImmutableArgs(asset_id=immutable_short_metadata.asset_id),
            params=CommonAppCallParams(sender=asset_manager.address),
        )
