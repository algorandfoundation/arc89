import pytest
from algokit_utils import CommonAppCallParams, LogicError, SigningAccount

from asa_metadata_registry import (
    AssetMetadata,
    AssetMetadataBox,
)
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89MigrateMetadataArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


def test_migrate_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asset_id = mutable_short_metadata.asset_id
    assert not mutable_short_metadata.deprecated_by

    asa_metadata_registry_client.send.arc89_migrate_metadata(
        args=Arc89MigrateMetadataArgs(asset_id=asset_id, new_registry_id=42),
        params=CommonAppCallParams(sender=asset_manager.address),
    )

    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None
    post_migration = AssetMetadataBox.parse(
        asset_id=asset_id,
        value=box_value,
    )
    assert post_migration.header.deprecated_by == 42


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
