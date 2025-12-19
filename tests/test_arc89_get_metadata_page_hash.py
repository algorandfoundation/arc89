from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataPageHashArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_maxed_metadata(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    for p in range(mutable_maxed_metadata.total_pages):
        page_hash = asa_metadata_registry_client.send.arc89_get_metadata_page_hash(
            args=Arc89GetMetadataPageHashArgs(
                asset_id=mutable_maxed_metadata.asset_id, page=p
            )
        ).abi_return
        assert bytes(page_hash) == mutable_maxed_metadata.compute_page_hash(p)


# TODO: Test failing conditions
