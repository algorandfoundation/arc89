import logging

import algokit_utils

from .constants import ACCOUNT_MBR
from .template_vars import TRUSTED_DEPLOYER

logger = logging.getLogger(__name__)


def deploy() -> None:
    from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
        AsaMetadataRegistryFactory,
    )

    algorand = algokit_utils.AlgorandClient.from_environment()
    algorand.set_default_validity_window(100)
    deployer_ = algorand.account.from_environment("DEPLOYER")
    algorand.account.ensure_funded_from_environment(
        account_to_fund=deployer_,
        min_spending_balance=algokit_utils.AlgoAmount(algo=1),
    )

    factory = algorand.client.get_typed_app_factory(
        AsaMetadataRegistryFactory,
        compilation_params=algokit_utils.AppClientCompilationParams(
            deploy_time_params={TRUSTED_DEPLOYER: deployer_.public_key}
        ),
        default_sender=deployer_.address,
    )

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        algorand.send.payment(
            algokit_utils.PaymentParams(
                amount=algokit_utils.AlgoAmount(micro_algo=ACCOUNT_MBR),
                sender=deployer_.address,
                receiver=app_client.app_address,
            )
        )
