from src._generated.asa_metadata_registry_client import (
    Arc89GetMetadataStringByKeyArgs,
    AsaMetadataRegistryClient,
)
from src.models import AssetMetadata


def test_get_string_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    string_value = asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
        args=Arc89GetMetadataStringByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="name",
        ),
    ).abi_return

    assert string_value is not None
    assert string_value == str(json_obj["name"])


# TODO: Test failing conditions
