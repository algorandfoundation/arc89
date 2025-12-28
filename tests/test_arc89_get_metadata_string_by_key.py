from base64 import b64decode

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataStringByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata


def test_get_string_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    # FIXME: The '.abi_return' value is broken, hence we decode the raw logs
    raw_value = asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
        args=Arc89GetMetadataStringByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="name",
        ),
    ).confirmation["logs"][0]
    raw_value_str = (
        raw_value
        if isinstance(raw_value, str)
        else raw_value.decode() if isinstance(raw_value, bytes) else str(raw_value)
    )
    string_value = b64decode(raw_value_str)[const.ARC4_RETURN_PREFIX_SIZE :].decode(
        "utf-8"
    )
    assert string_value == str(json_obj["name"])


# TODO: Test failing conditions
