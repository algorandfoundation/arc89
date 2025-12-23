from algokit_utils import CommonAppCallParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89MigrateMetadataArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


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

    post_migration = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert post_migration.deprecated_by == 42


# TODO: Test failing conditions
