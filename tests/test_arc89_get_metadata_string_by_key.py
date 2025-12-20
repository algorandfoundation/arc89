from base64 import b64decode

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataStringByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata


def test_get_string_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict,
    mutable_json_obj_metadata: AssetMetadata,
) -> None:
    # FIXME: The '.abi_return' value is broken, hence we decode the raw logs
    raw_value = asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
        args=Arc89GetMetadataStringByKeyArgs(
            asset_id=mutable_json_obj_metadata.asset_id,
            key="name",
        ),
    ).confirmation["logs"][0]
    string_value = b64decode(raw_value)[const.ARC4_RETURN_PREFIX_SIZE :].decode("utf-8")
    assert string_value == json_obj["name"]


# TODO: Test failing conditions
