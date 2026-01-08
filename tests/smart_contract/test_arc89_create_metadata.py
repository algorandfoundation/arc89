import json
import re

import pytest
from algokit_utils import (
    AssetCreateParams,
    LogicError,
    SigningAccount,
)

from asa_metadata_registry import (
    AssetMetadata,
    AssetMetadataBox,
    IrreversibleFlags,
    MetadataBody,
    MetadataFlags,
    ReversibleFlags,
)
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.factories import (
    compute_arc3_metadata_hash,
    create_arc3_payload,
)
from tests.helpers.utils import (
    NON_EXISTENT_ASA_ID,
    build_create_metadata_composer,
    create_mbr_payment,
    create_metadata,
)


@pytest.mark.parametrize(
    "metadata_fixture",
    [
        "empty_metadata",
        "short_metadata",
        "maxed_metadata",
    ],
)
def test_create_metadata(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    metadata_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    metadata: AssetMetadata = request.getfixturevalue(metadata_fixture)

    creation_mbr_delta = metadata.get_mbr_delta(old_size=None)
    mbr_delta = create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=metadata.asset_id,
        metadata=metadata,
    )
    assert mbr_delta.amount == creation_mbr_delta.amount
    # TODO: Verify Asset Metadata Box contents matches fixture data


@pytest.mark.parametrize(
    "asset_params,arc3_compliant,arc89_native",
    [
        pytest.param(
            {"asset_name": const.ARC3_NAME.decode()},
            True,
            False,
            id="arc3_name",
        ),
        pytest.param(
            {"asset_name": "Test" + const.ARC3_NAME_SUFFIX.decode()},
            True,
            False,
            id="arc3_name_suffix",
        ),
        pytest.param(
            {"url": "URI" + const.ARC3_URL_SUFFIX.decode()},
            True,
            False,
            id="arc3_url",
        ),
    ],
)
def test_arc3_compliance(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    flags_arc3_compliant: MetadataFlags,
    asset_params: dict[str, object],
    *,
    arc3_compliant: bool,
    arc89_native: bool,
) -> None:
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            **asset_params,  # type: ignore[arg-type]
        )
    ).asset_id

    metadata = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=create_arc3_payload(name="ARC3 Compliant Test"),
        flags=flags_arc3_compliant,
    )

    assert metadata.is_arc3_compliant == arc3_compliant
    if arc89_native:
        assert metadata.is_arc89_native

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None
    created_metadata = AssetMetadataBox.parse(
        asset_id=asset_id,
        value=box_value,
    )
    assert created_metadata.header.flags.irreversible.arc3 == arc3_compliant
    if arc89_native:
        assert created_metadata.header.flags.irreversible.arc89_native


def test_arc89_native_arc3_url_compliance(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc89_partial_uri: str,
    flags_arc89_native_and_arc3_compliant: MetadataFlags,
) -> None:
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            url=arc89_partial_uri + const.ARC3_URL_SUFFIX.decode(),
        )
    ).asset_id

    metadata = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=create_arc3_payload(name="ARC3 Compliant Test"),
        flags=flags_arc89_native_and_arc3_compliant,
    )

    assert metadata.is_arc3_compliant
    assert metadata.is_arc89_native

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None
    created_metadata = AssetMetadataBox.parse(
        asset_id=asset_id,
        value=box_value,
    )
    assert created_metadata.header.flags.irreversible.arc3
    assert created_metadata.header.flags.irreversible.arc89_native


def test_arc3_metadata_hash(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    flags_immutable_arc3_compliant: MetadataFlags,
) -> None:
    arc3_payload = create_arc3_payload(name="ARC3 Compliant Test")
    arc3_metadata_hash = compute_arc3_metadata_hash(json.dumps(arc3_payload).encode())
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            asset_name=const.ARC3_NAME.decode(),
            metadata_hash=arc3_metadata_hash,
        )
    ).asset_id

    metadata = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=arc3_payload,
        flags=flags_immutable_arc3_compliant,
    )
    assert metadata.is_arc3_compliant
    assert (
        metadata.compute_metadata_hash(
            asa_am=arc3_metadata_hash, enforce_immutable_on_override=True
        )
        == arc3_metadata_hash
    )

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    box_value = asa_metadata_registry_client.state.box.asset_metadata.get_value(
        asset_id
    )
    assert box_value is not None
    created_metadata = AssetMetadataBox.parse(
        asset_id=asset_id,
        value=box_value,
    )
    assert created_metadata.header.flags.irreversible.arc3
    assert created_metadata.header.metadata_hash == arc3_metadata_hash


def test_fail_asa_not_exists(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=NON_EXISTENT_ASA_ID,
            metadata=mutable_empty_metadata,
        )


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    empty_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        create_metadata(
            asset_manager=untrusted_account,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=empty_metadata.asset_id,
            metadata=empty_metadata,
        )


def test_fail_exceeds_max_metadata_size(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody.empty(),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )

    mbr_payment = create_mbr_payment(
        asa_metadata_registry_client, asset_manager, metadata
    )
    composer = build_create_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        arc_89_asa,
        metadata,
        mbr_payment,
        metadata_size_override=const.MAX_METADATA_SIZE + 1,  # Exceeds MAX_METADATA_SIZE
    )

    with pytest.raises(LogicError, match=err.EXCEEDS_MAX_METADATA_SIZE):
        composer.send()


def test_fail_asset_metadata_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_empty_metadata: AssetMetadata,
) -> None:
    # Trying to create again should fail
    new_metadata = AssetMetadata.from_json(
        asset_id=mutable_empty_metadata.asset_id,
        json_obj=create_arc3_payload(name="Duplicate Metadata"),
    )
    with pytest.raises(LogicError, match=err.ASSET_METADATA_EXIST):
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=mutable_empty_metadata.asset_id,
            metadata=new_metadata,
        )


def test_fail_mbr_delta_receiver_invalid(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    empty_metadata: AssetMetadata,
) -> None:
    # Payment to wrong receiver (asset_manager instead of app address)
    wrong_receiver_payment = create_mbr_payment(
        asa_metadata_registry_client,
        asset_manager,
        empty_metadata,
        receiver_override=asset_manager.address,  # Wrong receiver!
    )

    composer = build_create_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        empty_metadata.asset_id,
        empty_metadata,
        wrong_receiver_payment,
    )

    with pytest.raises(LogicError, match=err.MBR_DELTA_RECEIVER_INVALID):
        composer.send()


def test_fail_mbr_delta_amount_invalid(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    short_metadata: AssetMetadata,
) -> None:
    # Payment with insufficient amount (1 microAlgo instead of required MBR)
    insufficient_payment = create_mbr_payment(
        asa_metadata_registry_client,
        asset_manager,
        short_metadata,
        amount_override=1,  # Insufficient amount!
    )

    composer = build_create_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        short_metadata.asset_id,
        short_metadata,
        insufficient_payment,
    )

    with pytest.raises(LogicError, match=err.MBR_DELTA_AMOUNT_INVALID):
        composer.send()


def test_fail_requires_immutable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    # Create ASA with non-zero metadata_hash (requires immutable flag)
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            asset_name="Test ASA with Hash",
            metadata_hash=b"12345678901234567890123456789012",  # 32 bytes non-zero hash
        )
    ).asset_id

    metadata = AssetMetadata(
        asset_id=asset_id,
        body=MetadataBody.empty(),
        flags=MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(immutable=False),  # NOT immutable!
        ),
        deprecated_by=0,
    )

    mbr_payment = create_mbr_payment(
        asa_metadata_registry_client, asset_manager, metadata
    )
    composer = build_create_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        asset_id,
        metadata,
        mbr_payment,
    )

    with pytest.raises(LogicError, match=err.REQUIRES_IMMUTABLE):
        composer.send()


def test_fail_asa_not_arc3_compliant(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    flags_arc3_compliant: MetadataFlags,
) -> None:

    # Create ASA without ARC3 compliant name or URL
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            asset_name="Non ARC3 Compliant",  # No @arc3 suffix
            url="https://example.com",  # No #arc3 suffix
        )
    ).asset_id

    # Try to create metadata with ARC3 flag set
    metadata = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=create_arc3_payload(name="Test"),
        flags=flags_arc3_compliant,
    )

    with pytest.raises(LogicError, match=re.escape(err.ASA_NOT_ARC3_COMPLIANT)):
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=asset_id,
            metadata=metadata,
        )


def test_fail_asa_not_arc89_compliant(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    flags_arc89_native_and_arc3_compliant: MetadataFlags,
) -> None:
    # Create ASA without ARC89 compliant URL (not starting with arc90 partial URI)
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            asset_name="arc3",  # ARC3 compliant name
            url="https://example.com",  # NOT ARC89 compliant URL
        )
    ).asset_id

    # Try to create metadata with ARC89 native flag set
    metadata = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=create_arc3_payload(name="Test"),
        flags=flags_arc89_native_and_arc3_compliant,
    )

    with pytest.raises(LogicError, match=err.ASA_NOT_ARC89_COMPLIANT):
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=asset_id,
            metadata=metadata,
        )


def test_fail_payload_overflow(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    # Declare small metadata size but provide larger payload
    declared_size = 10
    actual_payload = b"x" * 100  # Larger than declared size

    metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody(raw_bytes=actual_payload),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )

    mbr_payment = create_mbr_payment(
        asa_metadata_registry_client, asset_manager, metadata
    )
    composer = build_create_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        arc_89_asa,
        metadata,
        mbr_payment,
        metadata_size_override=declared_size,  # Declared smaller than actual payload
        payload_override=actual_payload,
    )

    with pytest.raises(LogicError, match=err.PAYLOAD_OVERFLOW):
        composer.send()


def test_fail_metadata_size_mismatch(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    # Declare larger metadata size but provide smaller payload
    declared_size = 100
    actual_payload = b"x" * 10  # Smaller than declared size

    # Use declared size for MBR calculation
    declared_metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody(raw_bytes=b"x" * declared_size),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )

    actual_metadata = AssetMetadata(
        asset_id=arc_89_asa,
        body=MetadataBody(raw_bytes=actual_payload),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )

    mbr_payment = create_mbr_payment(
        asa_metadata_registry_client, asset_manager, declared_metadata
    )
    composer = build_create_metadata_composer(
        asa_metadata_registry_client,
        asset_manager,
        arc_89_asa,
        actual_metadata,
        mbr_payment,
        metadata_size_override=declared_size,  # Declared larger than actual payload
        payload_override=actual_payload,
    )

    with pytest.raises(LogicError, match=err.METADATA_SIZE_MISMATCH):
        composer.send()
