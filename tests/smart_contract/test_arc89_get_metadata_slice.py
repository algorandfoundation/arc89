import pytest

from src.generated.asa_metadata_registry_client import (
    Arc89GetMetadataSliceArgs,
    AsaMetadataRegistryClient,
)
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

    metadata_slice = asa_metadata_registry_client.send.arc89_get_metadata_slice(
        args=Arc89GetMetadataSliceArgs(
            asset_id=metadata.asset_id,
            offset=offset,
            size=size,
        ),
    ).abi_return
    assert metadata_slice is not None
    assert bytes(metadata_slice) == metadata.metadata_bytes[offset : offset + size]


# TODO: Test failing conditions
