import pytest
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AppClientCompilationParams,
    OnSchemaBreak,
    OnUpdate,
    SigningAccount,
)
from algokit_utils.config import config

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
    AsaMetadataRegistryFactory,
)
from smart_contracts.asa_metadata_registry.template_vars import TRUSTED_DEPLOYER

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
    return AlgorandClient.from_environment()


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


@pytest.fixture(scope="function")
def asa_metadata_registry_client(
    asa_metadata_registry_factory: AsaMetadataRegistryFactory,
) -> AsaMetadataRegistryClient:
    client, _ = asa_metadata_registry_factory.deploy(
        on_schema_break=OnSchemaBreak.AppendApp,
        on_update=OnUpdate.AppendApp,
    )
    return client
