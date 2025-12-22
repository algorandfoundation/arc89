from collections.abc import Callable

import pytest
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AppClientCompilationParams,
    AssetCreateParams,
    CommonAppCallParams,
    OnSchemaBreak,
    OnUpdate,
    PaymentParams,
    SigningAccount,
)
from algokit_utils.config import config

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89SetImmutableArgs,
    AsaMetadataRegistryClient,
    AsaMetadataRegistryFactory,
)
from smart_contracts.asa_metadata_registry import constants as const
from smart_contracts.asa_metadata_registry.template_vars import TRUSTED_DEPLOYER

from .helpers.factories import AssetMetadata, create_arc3_metadata
from .helpers.utils import add_extra_resources, create_metadata, pages_min_fee

# Uncomment if you want to load network specific or generic .env file
# @pytest.fixture(autouse=True, scope="session")
# def environment_fixture() -> None:
#     env_path = Path(__file__).parent.parent / ".env"
#     load_dotenv(env_path)

config.configure(
    debug=True,
    populate_app_call_resources=True,
    # trace_all=True, # uncomment to trace all transactions
)


@pytest.fixture(scope="session")
def algorand_client() -> AlgorandClient:
    client = AlgorandClient.from_environment()
    client.set_suggested_params_cache_timeout(0)
    return client


@pytest.fixture(scope="session")
def deployer(algorand_client: AlgorandClient) -> SigningAccount:
    account = algorand_client.account.from_environment("DEPLOYER")
    algorand_client.account.ensure_funded_from_environment(
        account_to_fund=account.address, min_spending_balance=AlgoAmount.from_algo(10)
    )
    return account


@pytest.fixture(scope="session")
def untrusted_account(algorand_client: AlgorandClient) -> SigningAccount:
    account = algorand_client.account.random()
    algorand_client.account.ensure_funded_from_environment(
        account_to_fund=account.address, min_spending_balance=AlgoAmount.from_algo(10)
    )
    return account


@pytest.fixture(scope="session")
def asset_manager(algorand_client: AlgorandClient) -> SigningAccount:
    account = algorand_client.account.random()
    algorand_client.account.ensure_funded_from_environment(
        account_to_fund=account.address,
        min_spending_balance=AlgoAmount.from_algo(1_000),
    )
    return account


@pytest.fixture(scope="session")
def asa_metadata_registry_factory(
    algorand_client: AlgorandClient, deployer: SigningAccount
) -> AsaMetadataRegistryFactory:
    return algorand_client.client.get_typed_app_factory(
        AsaMetadataRegistryFactory,
        compilation_params=AppClientCompilationParams(
            deploy_time_params={TRUSTED_DEPLOYER: deployer.public_key}
        ),
        default_sender=deployer.address,
    )


@pytest.fixture(scope="session")
def json_obj() -> dict:
    return {
        "name": "Silvio",
        "answer": 42,
        "date": {"day": 13, "month": 10, "year": 1954},
    }


@pytest.fixture(scope="function")
def asa_metadata_registry_client(
    deployer: SigningAccount,
    asa_metadata_registry_factory: AsaMetadataRegistryFactory,
) -> AsaMetadataRegistryClient:
    client, _ = asa_metadata_registry_factory.deploy(
        on_schema_break=OnSchemaBreak.AppendApp,
        on_update=OnUpdate.AppendApp,
    )
    asa_metadata_registry_factory.algorand.send.payment(
        params=PaymentParams(
            sender=deployer.address,
            receiver=client.app_address,
            amount=AlgoAmount(micro_algo=const.ACCOUNT_MBR),
        )
    )
    return client


@pytest.fixture(scope="function")
def arc_89_asa(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
) -> int:
    arc89_uri = (
        const.URI_ARC_89_PREFIX.decode()
        + str(asa_metadata_registry_client.app_id)
        + const.URI_ARC_89_SUFFIX.decode()
    )
    return asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            total=42,
            asset_name="ARC89 Mutable",
            unit_name="ARC89",
            url=arc89_uri,
            decimals=0,
            default_frozen=False,
            manager=asset_manager.address,
        )
    ).asset_id


# AssetMetadata factory fixtures
@pytest.fixture(scope="function")
def empty_metadata(arc_89_asa: int) -> AssetMetadata:
    metadata = AssetMetadata.create(
        asset_id=arc_89_asa, metadata=b"", arc89_native=True  # Empty body
    )
    assert metadata.size == 0
    assert metadata.total_pages == 0
    return metadata


@pytest.fixture(scope="function")
def short_metadata(arc_89_asa: int) -> AssetMetadata:
    # Create small ARC-3 metadata
    arc3_data = create_arc3_metadata(
        name="Short Metadata Test",
        description="This is small enough to fit in AVM stack",
        image="ipfs://QmShort",
    )

    metadata = AssetMetadata.create(
        asset_id=arc_89_asa, metadata=arc3_data, arc3_compliant=True, arc89_native=True
    )
    assert metadata.size <= const.SHORT_METADATA_SIZE
    assert metadata.is_short
    return metadata


@pytest.fixture(scope="function")
def maxed_metadata(arc_89_asa: int) -> AssetMetadata:
    max_size_content = "x" * const.MAX_METADATA_SIZE
    metadata = AssetMetadata.create(
        asset_id=arc_89_asa, metadata=max_size_content, arc89_native=True
    )
    assert metadata.size == const.MAX_METADATA_SIZE
    assert metadata.validate_size()
    assert not metadata.is_short
    return metadata


@pytest.fixture(scope="function")
def oversized_metadata(arc_89_asa: int) -> AssetMetadata:
    oversized_content = "x" * (const.MAX_METADATA_SIZE + 1)
    metadata = AssetMetadata(
        asset_id=arc_89_asa, metadata_bytes=oversized_content.encode("utf-8")
    )
    assert metadata.size > const.MAX_METADATA_SIZE
    assert not metadata.validate_size()
    return metadata


@pytest.fixture(scope="function")
def json_obj_metadata(arc_89_asa: int, json_obj: dict) -> AssetMetadata:
    metadata = AssetMetadata.create(
        asset_id=arc_89_asa,
        metadata=json_obj,
    )
    assert metadata.validate_json()
    assert metadata.is_short
    return metadata


# Uploaded AssetMetadata fixtures
def _create_uploaded_metadata_fixture(
    metadata_fixture_name: str, *, immutable: bool = False
) -> Callable[..., AssetMetadata]:
    @pytest.fixture(scope="function")
    def uploaded_metadata(
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        request: pytest.FixtureRequest,
    ) -> AssetMetadata:
        metadata = request.getfixturevalue(metadata_fixture_name)
        asset_id = metadata.asset_id
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=asset_id,
            metadata=metadata,
        )

        if immutable:
            set_immutable = asa_metadata_registry_client.new_group()
            set_immutable.arc89_set_immutable(
                args=Arc89SetImmutableArgs(asset_id=asset_id),
                params=CommonAppCallParams(
                    sender=asset_manager.address,
                    static_fee=AlgoAmount.from_micro_algo(pages_min_fee(metadata)),
                ),
            )
            if metadata.total_pages > 15:
                add_extra_resources(set_immutable)
            set_immutable.send()

        return AssetMetadata.from_box_value(
            asset_id,
            asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
        )

    return uploaded_metadata


# Mutable Metadata Fixtures
mutable_empty_metadata = _create_uploaded_metadata_fixture("empty_metadata")
mutable_short_metadata = _create_uploaded_metadata_fixture("short_metadata")
mutable_maxed_metadata = _create_uploaded_metadata_fixture("maxed_metadata")
mutable_json_obj_metadata = _create_uploaded_metadata_fixture("json_obj_metadata")

# Immutable Metadata Fixtures
immutable_empty_metadata = _create_uploaded_metadata_fixture(
    "empty_metadata", immutable=True
)
immutable_short_metadata = _create_uploaded_metadata_fixture(
    "short_metadata", immutable=True
)
immutable_maxed_metadata = _create_uploaded_metadata_fixture(
    "maxed_metadata", immutable=True
)
immutable_json_obj_metadata = _create_uploaded_metadata_fixture(
    "json_obj_metadata", immutable=True
)
