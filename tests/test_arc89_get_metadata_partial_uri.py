from base64 import b64decode

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const


def test_non_mainnet_partial_uri(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc89_partial_uri: str,
) -> None:
    # FIXME: The '.abi_return' value is broken, hence we decode the raw logs
    raw_value = (
        asa_metadata_registry_client.send.arc89_get_metadata_partial_uri().confirmation[
            "logs"
        ][0]
    )
    raw_value_str = (
        raw_value
        if isinstance(raw_value, str)
        else raw_value.decode() if isinstance(raw_value, bytes) else str(raw_value)
    )
    partial_uri = b64decode(raw_value_str)[const.ARC4_RETURN_PREFIX_SIZE :].decode(
        "utf-8"
    )
    assert partial_uri == arc89_partial_uri
