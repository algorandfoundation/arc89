import os
from collections.abc import Callable
from pathlib import Path

import pytest
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AppClientCompilationParams,
    AssetCreateParams,
    OnSchemaBreak,
    OnUpdate,
    PaymentParams,
    SigningAccount,
)
from algokit_utils.config import config
from dotenv import load_dotenv

from smart_contracts.template_vars import ARC90_NETAUTH, TRUSTED_DEPLOYER
from src import constants as const
from src.algod import AlgodBoxReader
from src.codec import Arc90Uri
from src._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
    AsaMetadataRegistryFactory,
)
from src.models import (
    AssetMetadata,
    AssetMetadataBox,
    IrreversibleFlags,
    MetadataBody,
    MetadataFlags,
    ReversibleFlags,
)
from src.read.avm import AsaMetadataRegistryAvmRead
from src.read.reader import AsaMetadataRegistryRead

from .helpers.utils import create_metadata, set_immutable


@pytest.fixture(autouse=True, scope="session")
def environment_fixture() -> None:
    env_path = Path(__file__).parent.parent / ".env.localnet.template"
    load_dotenv(env_path)


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
            deploy_time_params={
                TRUSTED_DEPLOYER: deployer.public_key,
                ARC90_NETAUTH: os.environ[ARC90_NETAUTH],
            }
        ),
        default_sender=deployer.address,
    )


@pytest.fixture(scope="session")
def json_obj() -> dict[str, object]:
    return {
        "name": "Silvio",
        "answer": 42,
        "date": {"day": 13, "month": 10, "year": 1954},
        "gh_b64_url": "f_________8=",  # 2^63 - 1
        "gh_b64_std": "f/////////8=",  # 2^63 - 1
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
def arc89_partial_uri(asa_metadata_registry_client: AsaMetadataRegistryClient) -> str:
    return Arc90Uri(
        netauth=os.environ[ARC90_NETAUTH],
        app_id=asa_metadata_registry_client.app_id,
        box_name=None,  # Partial URI has no box name
    ).to_uri()


@pytest.fixture(scope="function")
def arc_89_asa(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc89_partial_uri: str,
) -> int:
    return asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            total=42,
            asset_name="ARC89 Mutable",
            unit_name="ARC89",
            url=arc89_partial_uri,
            decimals=0,
            default_frozen=False,
            manager=asset_manager.address,
        )
    ).asset_id


# AssetMetadata factory fixtures
@pytest.fixture(scope="function")
def flags_arc3_compliant() -> MetadataFlags:
    return MetadataFlags(
        reversible=ReversibleFlags.empty(),
        irreversible=IrreversibleFlags(arc3=True),
    )


@pytest.fixture(scope="function")
def flags_immutable_arc3_compliant() -> MetadataFlags:
    return MetadataFlags(
        reversible=ReversibleFlags.empty(),
        irreversible=IrreversibleFlags(arc3=True, immutable=True),
    )


@pytest.fixture(scope="function")
def flags_arc89_native_and_arc3_compliant() -> MetadataFlags:
    return MetadataFlags(
        reversible=ReversibleFlags.empty(),
        irreversible=IrreversibleFlags(arc3=True, arc89_native=True),
    )


@pytest.fixture(scope="function")
def empty_metadata(arc_89_asa: int) -> AssetMetadata:
    metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody.empty(),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )
    assert metadata.body.size == 0
    assert metadata.body.total_pages() == 0
    return metadata


@pytest.fixture(scope="function")
def short_metadata(json_obj: dict[str, object], arc_89_asa: int) -> AssetMetadata:
    metadata = AssetMetadata.from_json(
        asset_id=arc_89_asa,
        json_obj=json_obj,
    )
    assert metadata.body.size <= const.SHORT_METADATA_SIZE
    assert metadata.body.is_short
    return metadata


@pytest.fixture(scope="function")
def maxed_metadata(arc_89_asa: int) -> AssetMetadata:
    max_size_content = "x" * const.MAX_METADATA_SIZE
    metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody(raw_bytes=max_size_content.encode("utf-8")),
        flags=MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc89_native=True),
        ),
        deprecated_by=0,
    )
    assert metadata.body.size == const.MAX_METADATA_SIZE
    assert not metadata.body.is_short
    return metadata


@pytest.fixture(scope="function")
def oversized_metadata(arc_89_asa: int) -> AssetMetadata:
    oversized_content = "x" * (const.MAX_METADATA_SIZE + 1)
    metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody(raw_bytes=oversized_content.encode("utf-8")),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )
    assert metadata.body.size > const.MAX_METADATA_SIZE
    return metadata


# Uploaded AssetMetadata fixtures
def _create_uploaded_metadata_fixture(
    metadata_fixture_name: str, *, immutable: bool = False
) -> Callable[
    [AlgorandClient, SigningAccount, AsaMetadataRegistryClient, pytest.FixtureRequest],
    AssetMetadata,
]:
    @pytest.fixture(scope="function")
    def uploaded_metadata(
        algorand_client: AlgorandClient,
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
            set_immutable(asa_metadata_registry_client, asset_manager, metadata)

        box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
            asset_id
        )
        assert box_value is not None
        # Parse the box value into AssetMetadataBox, then convert to AssetMetadata
        parsed_box = AssetMetadataBox.parse(asset_id=asset_id, value=box_value)
        return AssetMetadata(
            asset_id=asset_id,
            body=parsed_box.body,
            flags=parsed_box.header.flags,
            deprecated_by=parsed_box.header.deprecated_by,
        )

    return uploaded_metadata


# Mutable Metadata Fixtures
mutable_empty_metadata = _create_uploaded_metadata_fixture("empty_metadata")
mutable_short_metadata = _create_uploaded_metadata_fixture("short_metadata")
mutable_maxed_metadata = _create_uploaded_metadata_fixture("maxed_metadata")

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


# Reader-specific fixtures
@pytest.fixture(scope="function")
def reader_with_algod(
    algorand_client: AlgorandClient,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> AsaMetadataRegistryRead:
    algod_reader = AlgodBoxReader(algod=algorand_client.client.algod)
    return AsaMetadataRegistryRead(
        app_id=asa_metadata_registry_client.app_id,
        algod=algod_reader,
    )


@pytest.fixture(scope="function")
def reader_with_avm(
    algorand_client: AlgorandClient,
    asa_metadata_registry_factory: AsaMetadataRegistryFactory,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> AsaMetadataRegistryRead:
    def avm_factory(app_id: int) -> AsaMetadataRegistryAvmRead:
        client = asa_metadata_registry_factory.get_app_client_by_id(app_id)
        return AsaMetadataRegistryAvmRead(client=client)

    return AsaMetadataRegistryRead(
        app_id=asa_metadata_registry_client.app_id,
        avm_factory=avm_factory,
    )


@pytest.fixture(scope="function")
def reader_full(
    algorand_client: AlgorandClient,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asa_metadata_registry_factory: AsaMetadataRegistryFactory,
) -> "AsaMetadataRegistryRead":
    algod_reader = AlgodBoxReader(algod=algorand_client.client.algod)

    def avm_factory(app_id: int) -> AsaMetadataRegistryAvmRead:
        client = asa_metadata_registry_factory.get_app_client_by_id(app_id)
        return AsaMetadataRegistryAvmRead(client=client)

    return AsaMetadataRegistryRead(
        app_id=asa_metadata_registry_client.app_id,
        algod=algod_reader,
        avm_factory=avm_factory,
    )
