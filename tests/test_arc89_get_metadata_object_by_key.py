import json

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataObjectByKeyArgs,
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata


def test_get_object_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    nested_obj = asa_metadata_registry_client.send.arc89_get_metadata_object_by_key(
        args=Arc89GetMetadataObjectByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="date",
        ),
    ).abi_return

    assert nested_obj is not None
    assert json.loads(nested_obj) == json_obj["date"]


# TODO: Test failing conditions
