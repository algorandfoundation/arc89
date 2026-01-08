import base64
import json
import re

import pytest
from algokit_utils import LogicError, SigningAccount

from asa_metadata_registry import AssetMetadata, MetadataBody, MetadataFlags
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89GetMetadataB64BytesByKeyArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from smart_contracts.asa_metadata_registry.enums import (
    B64_STD_ENCODING,
    B64_URL_ENCODING,
)
from tests.helpers.utils import NON_EXISTENT_ASA_ID, create_metadata


def test_get_b64_url_decoded_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    decoded_value = (
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=mutable_short_metadata.asset_id,
                key="gh_b64_url",
                b64_encoding=B64_URL_ENCODING,
            ),
        ).abi_return
    )

    assert decoded_value is not None
    b64_value = json_obj["gh_b64_url"]
    assert isinstance(b64_value, str)
    assert bytes(decoded_value) == base64.urlsafe_b64decode(b64_value)


def test_get_b64_std_decoded_value(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    json_obj: dict[str, object],
    mutable_short_metadata: AssetMetadata,
) -> None:
    decoded_value = (
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=mutable_short_metadata.asset_id,
                key="gh_b64_std",
                b64_encoding=B64_STD_ENCODING,
            ),
        ).abi_return
    )

    assert decoded_value is not None
    b64_value = json_obj["gh_b64_std"]
    assert isinstance(b64_value, str)
    assert bytes(decoded_value) == base64.standard_b64decode(b64_value)


def test_fail_asa_not_exists(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=NON_EXISTENT_ASA_ID,
                key="gh_b64_url",
                b64_encoding=B64_URL_ENCODING,
            ),
        )


def test_fail_asset_metadata_not_exist(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=arc_89_asa,
                key="gh_b64_url",
                b64_encoding=B64_URL_ENCODING,
            ),
        )


def test_fail_metadata_not_short(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_maxed_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.METADATA_NOT_SHORT):
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=mutable_maxed_metadata.asset_id,
                key="gh_b64_url",
                b64_encoding=B64_URL_ENCODING,
            ),
        )


def test_fail_b64_encoding_invalid(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    invalid_b64_encoding = 2  # Only 0 (URL) and 1 (Std) are valid
    with pytest.raises(LogicError, match=re.escape(err.B64_ENCODING_INVALID)):
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=mutable_short_metadata.asset_id,
                key="gh_b64_url",
                b64_encoding=invalid_b64_encoding,
            ),
        )


def test_fail_exceeds_page_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    # Create metadata with a base64-encoded value that, when decoded,
    # exceeds PAGE_SIZE bytes
    # The decoded data needs to be > PAGE_SIZE, so the encoded data will be ~4/3 of that
    large_data = b"x" * (const.PAGE_SIZE + 1)
    large_b64_value = base64.urlsafe_b64encode(large_data).decode("utf-8")
    json_obj = {"large_b64": large_b64_value}

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
        asa_metadata_registry_client.send.arc89_get_metadata_b64_bytes_by_key(
            args=Arc89GetMetadataB64BytesByKeyArgs(
                asset_id=arc_89_asa,
                key="large_b64",
                b64_encoding=B64_URL_ENCODING,
            ),
        )
