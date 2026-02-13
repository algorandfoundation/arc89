import json

import pytest
from algokit_utils import LogicError, SigningAccount

from asa_metadata_registry import AssetMetadata, MetadataBody, MetadataFlags
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89GetMetadataStringByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import NON_EXISTENT_ASA_ID, create_metadata


def test_get_string_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    string_value = asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
        args=Arc89GetMetadataStringByKeyArgs(
            asset_id=mutable_short_metadata.asset_id,
            key="name",
        ),
    ).abi_return

    assert string_value is not None
    assert string_value == str(json_obj["name"])


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
            args=Arc89GetMetadataStringByKeyArgs(
                asset_id=NON_EXISTENT_ASA_ID,
                key="name",
            ),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
            args=Arc89GetMetadataStringByKeyArgs(
                asset_id=arc_89_asa,
                key="name",
            ),
        )


def test_fail_metadata_not_short(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.METADATA_NOT_SHORT):
        asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
            args=Arc89GetMetadataStringByKeyArgs(
                asset_id=mutable_maxed_metadata.asset_id,
                key="name",
            ),
        )


def test_fail_exceeds_page_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    # Create metadata with a string value that exceeds PAGE_SIZE
    # PAGE_SIZE is approximately MAX_LOG_SIZE (1024) minus some overhead
    long_string_value = "x" * (const.PAGE_SIZE + 1)
    json_obj = {"long_key": long_string_value}

    metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody(raw_bytes=json.dumps(json_obj).encode("utf-8")),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )
    # Ensure metadata is short (within SHORT_METADATA_SIZE)
    assert metadata.body.size <= const.SHORT_METADATA_SIZE

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=arc_89_asa,
        metadata=metadata,
    )

    with pytest.raises(LogicError, match=err.EXCEEDS_PAGE_SIZE):
        asa_metadata_registry_client.send.arc89_get_metadata_string_by_key(
            args=Arc89GetMetadataStringByKeyArgs(
                asset_id=arc_89_asa,
                key="long_key",
            ),
        )
