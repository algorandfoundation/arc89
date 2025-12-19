import pytest
from algokit_utils import SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata
from tests.helpers.utils import create_metadata


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "empty_metadata",
        "short_metadata",
        "maxed_metadata",
    ],
)
def test_create_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)

    creation_mbr_delta = metadata.get_mbr_delta(old_size=None)
    mbr_delta = create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=metadata.asset_id,
        metadata=metadata,
    )
    assert mbr_delta.amount == creation_mbr_delta.amount.micro_algo
    # TODO: Verify Asset Metadata Box contents matches fixture data


# TODO: Test failing conditions
