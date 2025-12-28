import json
from base64 import b64decode

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataObjectByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata


def test_get_object_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    # FIXME: The '.abi_return' value is broken, hence we decode the raw logs
    raw_value = asa_metadata_registry_client.send.arc89_get_metadata_object_by_key(
        args=Arc89GetMetadataObjectByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="date",
        ),
    ).confirmation["logs"][0]
    raw_value_str = (
        raw_value
        if isinstance(raw_value, str)
        else raw_value.decode() if isinstance(raw_value, bytes) else str(raw_value)
    )
    decoded_bytes = b64decode(raw_value_str)[const.ARC4_RETURN_PREFIX_SIZE :]
    nested_obj_value = json.loads(decoded_bytes.decode("utf-8"))
    assert nested_obj_value == json_obj["date"]


# TODO: Test failing conditions
