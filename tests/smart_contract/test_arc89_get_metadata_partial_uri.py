from src.asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)


def test_non_mainnet_partial_uri(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc89_partial_uri: str,
) -> None:
    partial_uri = (
        asa_metadata_registry_client.send.arc89_get_metadata_partial_uri().abi_return
    )

    assert partial_uri is not None
    assert partial_uri == arc89_partial_uri
