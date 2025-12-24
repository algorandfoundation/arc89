from base64 import b64decode

import pytest

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89GetMetadataSliceArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "mutable_short_metadata",
        "mutable_maxed_metadata",
    ],
)
def test_get_slice(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)
    offset = 0
    size = 4

    # FIXME: The '.abi_return' value is broken, hence we decode the raw logs
    raw_value = asa_metadata_registry_client.send.arc89_get_metadata_slice(
        args=Arc89GetMetadataSliceArgs(
            asset_id=metadata.asset_id,
            offset=offset,
            size=size,
        ),
    ).confirmation["logs"][0]
    metadata_slice = b64decode(raw_value)[const.ARC4_RETURN_PREFIX_SIZE :]
    assert metadata_slice == metadata.metadata_bytes[offset : offset + size]


# TODO: Test failing conditions
