import base64

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataB64BytesByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry.enums import (
    B64_STD_ENCODING,
    B64_URL_ENCODING,
)
from tests.helpers.factories import AssetMetadata


def test_get_b64_url_decoded_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    decoded_value = (
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=mutable_short_metadata.asset_id,
                key="gh_b64_url",
                b64_encoding=B64_URL_ENCODING,
            ),
        ).abi_return
    )

    assert decoded_value is not None
    b64_value = json_obj["gh_b64_url"]
    assert isinstance(b64_value, str)
    assert bytes(decoded_value) == base64.urlsafe_b64decode(b64_value)


def test_get_b64_std_decoded_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    decoded_value = (
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=mutable_short_metadata.asset_id,
                key="gh_b64_std",
                b64_encoding=B64_STD_ENCODING,
            ),
        ).abi_return
    )

    assert decoded_value is not None
    b64_value = json_obj["gh_b64_std"]
    assert isinstance(b64_value, str)
    assert bytes(decoded_value) == base64.standard_b64decode(b64_value)


# TODO: Test failing conditions
