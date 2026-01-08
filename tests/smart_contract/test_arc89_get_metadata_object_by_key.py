import json

import pytest
from algokit_utils import LogicError, SigningAccount

from asa_metadata_registry import AssetMetadata, MetadataBody, MetadataFlags
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataObjectByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID, create_metadata


def test_get_object_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    nested_obj = asa_metadata_registry_client.send.arc89_get_metadata_object_by_key(
        args=Arc89GetMetadataObjectByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="date",
        ),
    ).abi_return

    assert nested_obj is not None
    assert json.loads(nested_obj) == json_obj["date"]


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_object_by_key(
            args=Arc89GetMetadataObjectByKeyArgs(
                asset_id=NON_EXISTENT_ASA_ID,
                key="date",
            ),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_object_by_key(
            args=Arc89GetMetadataObjectByKeyArgs(
                asset_id=arc_89_asa,
                key="date",
            ),
        )


def test_fail_metadata_not_short(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.METADATA_NOT_SHORT):
        asa_metadata_registry_client.send.arc89_get_metadata_object_by_key(
            args=Arc89GetMetadataObjectByKeyArgs(
                asset_id=mutable_maxed_metadata.asset_id,
                key="date",
            ),
        )


def test_fail_exceeds_page_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    # Create metadata with an object value that exceeds PAGE_SIZE
    # PAGE_SIZE is approximately MAX_LOG_SIZE (1024) minus some overhead
    # Create a nested object with many keys to exceed PAGE_SIZE
    large_object = {f"key_{i}": f"value_{i}" for i in range(100)}
    json_obj = {"large_obj": large_object}

    metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody(raw_bytes=json.dumps(json_obj).encode("utf-8")),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )
    # The nested object serialized should exceed PAGE_SIZE
    nested_obj_size = len(json.dumps(large_object).encode("utf-8"))
    assert nested_obj_size > const.PAGE_SIZE
    # Ensure metadata is short (within SHORT_METADATA_SIZE)
    assert metadata.body.size <= const.SHORT_METADATA_SIZE

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=arc_89_asa,
        metadata=metadata,
    )

    with pytest.raises(LogicError, match=err.EXCEEDS_PAGE_SIZE):
        asa_metadata_registry_client.send.arc89_get_metadata_object_by_key(
            args=Arc89GetMetadataObjectByKeyArgs(
                asset_id=arc_89_asa,
                key="large_obj",
            ),
        )
