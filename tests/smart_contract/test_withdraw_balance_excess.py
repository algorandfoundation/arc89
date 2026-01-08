from algokit_utils import (
    AlgoAmount,
    CommonAppCallParams,
    PaymentParams,
    SigningAccount,
)

from asa_metadata_registry import AssetMetadata
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)


def test_withdraw_balance_excess(
    deployer: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,  # Not used but needed to have a registry with metadata
) -> None:
    excess_balance = AlgoAmount(algo=42)
    asa_metadata_registry_client.algorand.send.payment(
        PaymentParams(
            sender=deployer.address,
            receiver=asa_metadata_registry_client.app_address,
            amount=excess_balance,
        )
    )
    deployer_pre_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            deployer.address
        ).amount_without_pending_rewards.micro_algo
    )
    registry_pre_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).amount_without_pending_rewards.micro_algo
    )
    registry_pre_withdraw_min_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).min_balance.micro_algo
    )
    assert (
        registry_pre_withdraw_balance
        == registry_pre_withdraw_min_balance + excess_balance.micro_algo
    )

    min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee
    withdraw_fee = AlgoAmount(micro_algo=min_fee * 2)
    asa_metadata_registry_client.send.withdraw_balance_excess(
        params=CommonAppCallParams(sender=deployer.address, static_fee=withdraw_fee)
    )
    deployer_post_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            deployer.address
        ).amount.micro_algo
    )
    registry_post_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).amount.micro_algo
    )
    registry_post_withdraw_min_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).min_balance.micro_algo
    )
    assert registry_post_withdraw_balance == registry_post_withdraw_min_balance
    assert (
        deployer_post_withdraw_balance
        == deployer_pre_withdraw_balance
        + excess_balance.micro_algo
        - withdraw_fee.micro_algo
    )


def test_no_excess(
    deployer: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    deployer_pre_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            deployer.address
        ).amount_without_pending_rewards.micro_algo
    )
    registry_pre_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).amount_without_pending_rewards.micro_algo
    )
    registry_pre_withdraw_min_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).min_balance.micro_algo
    )
    assert registry_pre_withdraw_balance == registry_pre_withdraw_min_balance

    min_fee = asa_metadata_registry_client.algorand.get_suggested_params().min_fee
    withdraw_fee = AlgoAmount(micro_algo=min_fee * 2)
    asa_metadata_registry_client.send.withdraw_balance_excess(
        params=CommonAppCallParams(sender=deployer.address, static_fee=withdraw_fee)
    )
    deployer_post_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            deployer.address
        ).amount.micro_algo
    )
    registry_post_withdraw_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).amount.micro_algo
    )
    registry_post_withdraw_min_balance = (
        asa_metadata_registry_client.algorand.account.get_information(
            asa_metadata_registry_client.app_address
        ).min_balance.micro_algo
    )
    assert registry_post_withdraw_balance == registry_post_withdraw_min_balance
    assert (
        deployer_post_withdraw_balance
        == deployer_pre_withdraw_balance - withdraw_fee.micro_algo
    )
