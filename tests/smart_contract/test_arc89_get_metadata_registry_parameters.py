from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)


def test_get_registry_parameters(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    params = (
        asa_metadata_registry_client.send.arc89_get_metadata_registry_parameters().abi_return
    )

    assert params.header_size == const.HEADER_SIZE
    assert params.max_metadata_size == const.MAX_METADATA_SIZE
    assert params.short_metadata_size == const.SHORT_METADATA_SIZE
    assert params.page_size == const.PAGE_SIZE
    assert params.first_payload_max_size == const.FIRST_PAYLOAD_MAX_SIZE
    assert params.extra_payload_max_size == const.EXTRA_PAYLOAD_MAX_SIZE
    assert params.replace_payload_max_size == const.REPLACE_PAYLOAD_MAX_SIZE
    assert params.flat_mbr == const.FLAT_MBR
    assert params.byte_mbr == const.BYTE_MBR
