import json
import logging
import os
from pathlib import Path
from typing import cast

import algokit_utils

from smart_contracts.constants import ACCOUNT_MBR, ARC3_URL_SUFFIX, UINT64_SIZE
from smart_contracts.template_vars import ARC90_NETAUTH, TRUSTED_DEPLOYER
from src.asa_metadata_registry import (
    Arc90Compliance,
    Arc90Uri,
    AssetMetadata,
    IrreversibleFlags,
    MetadataFlags,
    ReversibleFlags,
)
from src.asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryFactory,
)
from tests.helpers.factories import compute_arc3_metadata_hash
from tests.helpers.utils import create_metadata

logger = logging.getLogger(__name__)


def deploy() -> None:
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
            deploy_time_params={
                TRUSTED_DEPLOYER: deployer_.public_key,
                ARC90_NETAUTH: os.environ[ARC90_NETAUTH],
            }
        ),
        default_sender=deployer_.address,
    )

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )
    logger.info(f"ASA Metadata Registry ID: {app_client.app_id}")

    netauth = os.environ[ARC90_NETAUTH]

    arc89_partial_uri_obj = Arc90Uri(
        netauth=netauth,
        app_id=app_client.app_id,
        box_name=None,  # Partial URI has no box name yet
    )
    arc89_partial_uri = arc89_partial_uri_obj.to_uri()
    logger.info(f"ARC89 Partial URI: {arc89_partial_uri}")

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

    # Pure NFT: ARC89 Native, ARC3 Compliant, Immutable
    arc3_pure_nft_json_path = (
        Path(__file__).parent.parent
        / "artifacts"
        / "asa_example"
        / "arc3_pure_nft.json"
    )
    with open(arc3_pure_nft_json_path, encoding="utf-8") as f:
        arc3_pure_nft_payload_str = f.read()

    arc3_pure_nft_payload_dict = cast(
        dict[str, object], json.loads(arc3_pure_nft_payload_str)
    )

    arc3_pure_nft_metadata_hash = compute_arc3_metadata_hash(
        arc3_pure_nft_payload_str.encode("utf-8")
    )
    arc3_pure_nft_id = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=deployer_.address,
            total=1,  # Pure NFT: single unit
            decimals=int(
                cast(int, arc3_pure_nft_payload_dict["decimals"])
            ),  # Pure NFT: not divisible
            asset_name=str(arc3_pure_nft_payload_dict["name"]),
            unit_name=str(arc3_pure_nft_payload_dict["unitName"]),
            url=arc89_partial_uri + ARC3_URL_SUFFIX.decode(),
            metadata_hash=arc3_pure_nft_metadata_hash,
            manager=deployer_.address,
            default_frozen=False,
        )
    ).asset_id

    logger.info(f"ARC3 Pure NFT ID: {arc3_pure_nft_id}")

    arc3_pure_nft_metadata = AssetMetadata.from_json(
        asset_id=arc3_pure_nft_id,
        json_obj=arc3_pure_nft_payload_dict,
        flags=MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(
                arc3=True,
                arc89_native=True,
                immutable=True,
            ),
        ),
        arc3_compliant=True,
    )
    create_metadata(
        asset_manager=deployer_,
        asa_metadata_registry_client=app_client,
        asset_id=arc3_pure_nft_id,
        metadata=arc3_pure_nft_metadata,
    )
    arc3_pure_nft_metadata_uri_obj = Arc90Uri(
        netauth=netauth,
        app_id=app_client.app_id,
        box_name=int.to_bytes(arc3_pure_nft_id, UINT64_SIZE, "big"),
        compliance=Arc90Compliance((3,)),  # ARC-3 compliance
    )
    arc3_pure_nft_metadata_uri = arc3_pure_nft_metadata_uri_obj.to_uri()
    logger.info(f"Pure NFT Asset Metadata URI: {arc3_pure_nft_metadata_uri}")

    # Zero Coupon Bond: ARC89 Native, ARC3 Compliant, Mutable
    arc3_bond_json_path = (
        Path(__file__).parent.parent / "artifacts" / "asa_example" / "arc3_bond.json"
    )
    with open(arc3_bond_json_path, encoding="utf-8") as f:
        arc3_bond_payload_str = f.read()

    arc3_bond_payload_dict = cast(dict[str, object], json.loads(arc3_bond_payload_str))

    arc3_bond_id = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=deployer_.address,
            total=1,  # Bond: single unit
            decimals=int(
                cast(int, arc3_bond_payload_dict["decimals"])
            ),  # Bond: not divisible
            asset_name=str(arc3_bond_payload_dict["name"]),
            unit_name=str(arc3_bond_payload_dict["unitName"]),
            url=arc89_partial_uri + ARC3_URL_SUFFIX.decode(),
            manager=deployer_.address,
            default_frozen=False,
        )
    ).asset_id

    logger.info(f"ARC3 Zero Coupon Bond ID: {arc3_bond_id}")

    arc3_bond_metadata = AssetMetadata.from_json(
        asset_id=arc3_bond_id,
        json_obj=arc3_bond_payload_dict,
        flags=MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(
                arc3=True,
                arc89_native=True,
                immutable=False,
            ),
        ),
        arc3_compliant=True,
    )
    create_metadata(
        asset_manager=deployer_,
        asa_metadata_registry_client=app_client,
        asset_id=arc3_bond_id,
        metadata=arc3_bond_metadata,
    )
    arc3_bond_metadata_uri_obj = Arc90Uri(
        netauth=netauth,
        app_id=app_client.app_id,
        box_name=int.to_bytes(arc3_bond_id, UINT64_SIZE, "big"),
        compliance=Arc90Compliance((3,)),  # ARC-3 compliance
    )
    arc3_bond_metadata_uri = arc3_bond_metadata_uri_obj.to_uri()
    logger.info(f"Zero Coupon Bond Asset Metadata URI: {arc3_bond_metadata_uri}")
