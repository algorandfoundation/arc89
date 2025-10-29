import pytest
from algokit_utils import (
    LogicError,
    SigningAccount,
)
from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryBareCallCreateParams,
    AsaMetadataRegistryClient,
    AsaMetadataRegistryFactory,
)

from smart_contracts.asa_metadata_registry import errors as err


def test_create_asa_metadata_registry(
    deployer: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    assert asa_metadata_registry_client.app_id is not None
    assert asa_metadata_registry_client.app_address is not None


@pytest.mark.skip(reason="Unexpected error from deployment simulation step")
def test_fail_untrusted_deployer(
    untrusted_account: SigningAccount,
    asa_metadata_registry_factory: AsaMetadataRegistryFactory,
) -> None:
    with pytest.raises(LogicError, match=err.UNTRUSTED_DEPLOYER):
        asa_metadata_registry_factory.deploy(
            create_params=AsaMetadataRegistryBareCallCreateParams(
                sender=untrusted_account.address,
            )
        )
