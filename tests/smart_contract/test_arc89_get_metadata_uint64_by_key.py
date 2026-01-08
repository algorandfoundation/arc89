import pytest
from algokit_utils import LogicError

from asa_metadata_registry import (
    AssetMetadata,
)
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataUint64ByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID


def test_get_uint64_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    uint64_value = asa_metadata_registry_client.send.arc89_get_metadata_uint64_by_key(
        args=Arc89GetMetadataUint64ByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="answer",
        ),
    ).abi_return
    assert uint64_value == json_obj["answer"]


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_uint64_by_key(
            args=Arc89GetMetadataUint64ByKeyArgs(
                asset_id=NON_EXISTENT_ASA_ID,
                key="answer",
            ),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_uint64_by_key(
            args=Arc89GetMetadataUint64ByKeyArgs(
                asset_id=arc_89_asa,
                key="answer",
            ),
        )


def test_fail_metadata_not_short(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.METADATA_NOT_SHORT):
        asa_metadata_registry_client.send.arc89_get_metadata_uint64_by_key(
            args=Arc89GetMetadataUint64ByKeyArgs(
                asset_id=mutable_maxed_metadata.asset_id,
                key="answer",
            ),
        )
