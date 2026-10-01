import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams, LogicError, SigningAccount

from asa_metadata_registry import AssetMetadata, flags
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89CheckMetadataExistsArgs,
    Arc89DeleteMetadataArgs,
    Arc89GetMetadataPaginationArgs,
    Arc89MigrateMetadataArgs,
    Arc89ReplaceMetadataArgs,
    Arc89ReplaceMetadataSliceArgs,
    Arc89SetImmutableArgs,
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID, get_metadata_from_state


def test_migrate_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id
    assert not mutable_short_metadata.deprecated_by
    pre_migration = get_metadata_from_state(asa_metadata_registry_client, asset_id)

    asa_metadata_registry_client.send.arc89_migrate_metadata(
        args=Arc89MigrateMetadataArgs(asset_id=asset_id, new_registry_id=42),
        params=CommonAppCallParams(sender=asset_manager.address),
    )

    post_migration = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert post_migration.header.deprecated_by == 42
    assert post_migration.header.revision == pre_migration.header.revision + 1
    assert (
        asa_metadata_registry_client.state.global_state.revision
        == post_migration.header.revision
    )

    asa_metadata_registry_client.send.arc89_migrate_metadata(
        args=Arc89MigrateMetadataArgs(asset_id=asset_id, new_registry_id=42),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    after_idempotent_migration = get_metadata_from_state(
        asa_metadata_registry_client, asset_id
    )
    assert after_idempotent_migration.header.revision == post_migration.header.revision


def test_fail_asa_not_exists(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_migrate_metadata(
            args=Arc89MigrateMetadataArgs(
                asset_id=NON_EXISTENT_ASA_ID, new_registry_id=42
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_migrate_metadata(
            args=Arc89MigrateMetadataArgs(asset_id=arc_89_asa, new_registry_id=42),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        asa_metadata_registry_client.send.arc89_migrate_metadata(
            args=Arc89MigrateMetadataArgs(
                asset_id=mutable_short_metadata.asset_id, new_registry_id=42
            ),
            params=CommonAppCallParams(sender=untrusted_account.address),
        )


def test_fail_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    immutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.IMMUTABLE):
        asa_metadata_registry_client.send.arc89_migrate_metadata(
            args=Arc89MigrateMetadataArgs(
                asset_id=immutable_short_metadata.asset_id, new_registry_id=42
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_new_registry_id_invalid(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # Cannot migrate to the same registry
    with pytest.raises(LogicError, match=err.NEW_REGISTRY_ID_INVALID):
        asa_metadata_registry_client.send.arc89_migrate_metadata(
            args=Arc89MigrateMetadataArgs(
                asset_id=mutable_short_metadata.asset_id,
                new_registry_id=asa_metadata_registry_client.app_id,
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def _migrate(
    client: AsaMetadataRegistryClient, manager: SigningAccount, asset_id: int
) -> None:
    client.send.arc89_migrate_metadata(
        args=Arc89MigrateMetadataArgs(asset_id=asset_id, new_registry_id=42),
        params=CommonAppCallParams(sender=manager.address),
    )


def test_pagination_exposes_deprecated_by(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id
    _migrate(asa_metadata_registry_client, asset_manager, asset_id)
    pagination = asa_metadata_registry_client.send.arc89_get_metadata_pagination(
        args=Arc89GetMetadataPaginationArgs(asset_id=asset_id),
    ).abi_return
    assert pagination is not None
    assert pagination.deprecated_by == 42


def test_fail_writes_while_deprecated(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    client = asa_metadata_registry_client
    asset_id = mutable_short_metadata.asset_id
    size = mutable_short_metadata.body.size
    _migrate(client, asset_manager, asset_id)
    params = CommonAppCallParams(sender=asset_manager.address)

    with pytest.raises(LogicError, match=err.ASSET_METADATA_DEPRECATED):
        client.send.arc89_replace_metadata(
            args=Arc89ReplaceMetadataArgs(
                asset_id=asset_id, metadata_size=size, payload=b"Q" * size
            ),
            params=params,
        )
    with pytest.raises(LogicError, match=err.ASSET_METADATA_DEPRECATED):
        client.send.arc89_replace_metadata_slice(
            args=Arc89ReplaceMetadataSliceArgs(
                asset_id=asset_id, offset=0, payload=b"patch"
            ),
            params=params,
        )
    with pytest.raises(LogicError, match=err.ASSET_METADATA_DEPRECATED):
        client.send.arc89_set_reversible_flag(
            args=Arc89SetReversibleFlagArgs(
                asset_id=asset_id, flag=flags.REV_FLG_RESERVED_3, value=True
            ),
            params=params,
        )
    with pytest.raises(LogicError, match=err.ASSET_METADATA_DEPRECATED):
        client.send.arc89_set_immutable(
            args=Arc89SetImmutableArgs(asset_id=asset_id), params=params
        )


def test_repoint_and_delete_while_deprecated(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    client = asa_metadata_registry_client
    asset_id = mutable_short_metadata.asset_id
    _migrate(client, asset_manager, asset_id)
    client.send.arc89_migrate_metadata(
        args=Arc89MigrateMetadataArgs(asset_id=asset_id, new_registry_id=43),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    assert get_metadata_from_state(client, asset_id).header.deprecated_by == 43
    client.send.arc89_delete_metadata(
        args=Arc89DeleteMetadataArgs(asset_id=asset_id),
        params=CommonAppCallParams(
            sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=2_000)
        ),
    )
    existence = client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=asset_id),
    ).abi_return
    assert existence is not None and not existence.metadata_exists
