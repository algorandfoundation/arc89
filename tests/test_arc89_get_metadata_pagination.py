from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataPaginationArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata


def test_arc89_empty_metadata_pagination(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_empty_metadata: AssetMetadata,
) -> None:
    pagination = asa_metadata_registry_client.send.arc89_get_metadata_pagination(
        args=Arc89GetMetadataPaginationArgs(asset_id=uploaded_empty_metadata.asset_id),
    ).abi_return
    assert pagination.metadata_size == uploaded_empty_metadata.size
    assert pagination.page_size == const.PAGE_SIZE
    assert pagination.total_pages == uploaded_empty_metadata.total_pages


def test_arc89_short_metadata_pagination(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_short_metadata: AssetMetadata,
) -> None:
    pagination = asa_metadata_registry_client.send.arc89_get_metadata_pagination(
        args=Arc89GetMetadataPaginationArgs(asset_id=uploaded_short_metadata.asset_id),
    ).abi_return
    assert pagination.metadata_size == uploaded_short_metadata.size
    assert pagination.page_size == const.PAGE_SIZE
    assert pagination.total_pages == uploaded_short_metadata.total_pages


def test_arc89_maxed_metadata_pagination(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_maxed_metadata: AssetMetadata,
) -> None:
    pagination = asa_metadata_registry_client.send.arc89_get_metadata_pagination(
        args=Arc89GetMetadataPaginationArgs(asset_id=uploaded_maxed_metadata.asset_id),
    ).abi_return
    assert pagination.metadata_size == uploaded_maxed_metadata.size
    assert pagination.page_size == const.PAGE_SIZE
    assert pagination.total_pages == uploaded_maxed_metadata.total_pages


# TODO: Test failing conditions
