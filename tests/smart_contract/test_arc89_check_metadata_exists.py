from algokit_utils import AssetDestroyParams, CommonAppCallParams, SigningAccount

from src.generated.asa_metadata_registry_client import (
    Arc89CheckMetadataExistsArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def _check_metadata_existence(
    client: AsaMetadataRegistryClient,
    asset_id: int,
    *,
    expected_asa_exists: bool,
    expected_metadata_exists: bool,
    params: CommonAppCallParams | None = None,
) -> None:
    call_params = params or CommonAppCallParams()
    metadata_existence = client.send.arc89_check_metadata_exists(
        args=Arc89CheckMetadataExistsArgs(asset_id=asset_id),
        params=call_params,
    ).abi_return
    assert metadata_existence is not None
    assert metadata_existence.asa_exists == expected_asa_exists
    assert metadata_existence.metadata_exists == expected_metadata_exists


def test_asset_exists_metadata_not_uploaded(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    short_metadata: AssetMetadata,
) -> None:
    _check_metadata_existence(
        asa_metadata_registry_client,
        short_metadata.asset_id,
        expected_asa_exists=True,
        expected_metadata_exists=False,
    )


def test_asset_exists_metadata_uploaded(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    _check_metadata_existence(
        asa_metadata_registry_client,
        mutable_short_metadata.asset_id,
        expected_asa_exists=True,
        expected_metadata_exists=True,
    )


def test_asset_not_exists_metadata_uploaded(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    asa_metadata_registry_client.algorand.send.asset_destroy(
        params=AssetDestroyParams(
            asset_id=mutable_short_metadata.asset_id, sender=asset_manager.address
        )
    )

    _check_metadata_existence(
        asa_metadata_registry_client,
        mutable_short_metadata.asset_id,
        expected_asa_exists=False,
        expected_metadata_exists=True,
    )


def test_asset_not_exists_metadata_not_uploaded(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    _check_metadata_existence(
        asa_metadata_registry_client,
        asset_id=420,
        expected_asa_exists=False,
        expected_metadata_exists=False,
        params=CommonAppCallParams(asset_references=[420]),
    )
