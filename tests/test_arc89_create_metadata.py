import pytest
from algokit_utils import AssetCreateParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import constants as const
from tests.helpers.factories import AssetMetadata, create_arc3_payload
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


@pytest.mark.parametrize(
    "asset_params,arc3_compliant,arc89_native",
    [
        pytest.param(
            {"asset_name": const.ARC3_NAME.decode()},
            True,
            False,
            id="arc3_name",
        ),
        pytest.param(
            {"asset_name": "Test" + const.ARC3_NAME_SUFFIX.decode()},
            True,
            False,
            id="arc3_name_suffix",
        ),
        pytest.param(
            {"url": "URI" + const.ARC3_URL_SUFFIX.decode()},
            True,
            False,
            id="arc3_url",
        ),
    ],
)
def test_arc3_compliance(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_params: dict,
    *,
    arc3_compliant: bool,
    arc89_native: bool,
) -> None:
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            **asset_params,
        )
    ).asset_id

    metadata = AssetMetadata.create(
        asset_id=asset_id,
        metadata=create_arc3_payload(name="ARC3 Compliant Test"),
        arc3_compliant=arc3_compliant,
        arc89_native=arc89_native,
    )

    assert metadata.is_arc3 == arc3_compliant
    if arc89_native:
        assert metadata.is_arc89_native

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    created_metadata = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert created_metadata.is_arc3 == arc3_compliant
    if arc89_native:
        assert created_metadata.is_arc89_native


def test_arc89_native_arc3_url_compliance(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc90_uri: str,
) -> None:
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            url=arc90_uri + const.ARC3_URL_SUFFIX.decode(),
        )
    ).asset_id

    metadata = AssetMetadata.create(
        asset_id=asset_id,
        metadata=create_arc3_payload(name="ARC3 Compliant Test"),
        arc3_compliant=True,
        arc89_native=True,
    )

    assert metadata.is_arc3
    assert metadata.is_arc89_native

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    created_metadata = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert created_metadata.is_arc3
    assert created_metadata.is_arc89_native


# TODO: Test failing conditions
