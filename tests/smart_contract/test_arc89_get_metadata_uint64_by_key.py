from src.generated.asa_metadata_registry_client import (
    Arc89GetMetadataUint64ByKeyArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_get_uint64_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    uint64_value = asa_metadata_registry_client.send.arc89_get_metadata_uint64_by_key(
        args=Arc89GetMetadataUint64ByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="answer",
        ),
    ).abi_return
    assert uint64_value == json_obj["answer"]


# TODO: Test failing conditions
