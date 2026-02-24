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
    IrreversibleFlags,
    MetadataBody,
    MetadataFlags,
    ReversibleFlags,
)
from asa_metadata_registry import constants as const
from asa_metadata_registry.generated.asa_metadata_registry_client import (
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
    get_metadata_from_state,
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

    created_metadata = get_metadata_from_state(
        asa_metadata_registry_client, metadata.asset_id
    )
    assert created_metadata.body.raw_bytes == metadata.body.raw_bytes
    assert created_metadata.header.flags == metadata.flags
    assert created_metadata.header.deprecated_by == metadata.deprecated_by
    assert created_metadata.header.identifiers == metadata.identifiers_byte
    assert created_metadata.header.metadata_hash == metadata.compute_metadata_hash()


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

    created_metadata = get_metadata_from_state(asa_metadata_registry_client, asset_id)
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

    created_metadata = get_metadata_from_state(asa_metadata_registry_client, asset_id)
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

    created_metadata = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert created_metadata.header.flags.irreversible.arc3
    assert created_metadata.header.metadata_hash == arc3_metadata_hash


def test_arc54_burnable(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    flags_arc54_burnable: MetadataFlags,
) -> None:
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
        )
    ).asset_id

    metadata = AssetMetadata.from_bytes(
        asset_id=asset_id,
        metadata_bytes=b"",
        flags=flags_arc54_burnable,
    )
    assert metadata.is_arc54_burnable

    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )


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


def test_fail_not_arc54_compliant(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
    flags_arc54_burnable: MetadataFlags,
) -> None:
    metadata = AssetMetadata.from_bytes(
        asset_id=arc_89_asa,
        metadata_bytes=b"",
        flags=flags_arc54_burnable,
    )

    with pytest.raises(LogicError, match=re.escape(err.ASA_NOT_ARC54_COMPLIANT)):
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=arc_89_asa,
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


def test_fail_asa_metadata_hash_mismatch(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc89_partial_uri: str,
) -> None:
    """
    Test that metadata creation fails when:
    - ASA has a non-zero metadata hash (am)
    - Metadata is flagged as ARC89 native
    - Metadata is NOT flagged as ARC3
    - The ASA's metadata hash does NOT match the computed hash
    """
    # Create an arbitrary wrong metadata hash that won't match computed
    wrong_metadata_hash = b"WRONG_HASH_THAT_WILL_NOT_MATCH"
    assert len(wrong_metadata_hash) < 32
    wrong_metadata_hash = wrong_metadata_hash.ljust(32, b"\x00")

    # Create ASA with ARC89-compliant URL and a non-matching metadata hash
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            url=arc89_partial_uri,  # ARC89 compliant URL, NOT ARC3 (no #arc3 suffix)
            metadata_hash=wrong_metadata_hash,
        )
    ).asset_id

    # Create metadata with ARC89 native flag and immutable (required for non-zero am)
    # Note: NOT setting arc3 flag
    metadata = AssetMetadata(
        asset_id=asset_id,
        body=MetadataBody(raw_bytes=b'{"name":"Test"}'),
        flags=MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc89_native=True, immutable=True),
        ),
        deprecated_by=0,
    )

    with pytest.raises(LogicError, match=re.escape(err.ASA_METADATA_HASH_MISMATCH)):
        create_metadata(
            asset_manager=asset_manager,
            asa_metadata_registry_client=asa_metadata_registry_client,
            asset_id=asset_id,
            metadata=metadata,
        )


def test_arc89_native_with_matching_metadata_hash(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc89_partial_uri: str,
) -> None:
    """
    Test that metadata creation SUCCEEDS when:
    - ASA has a non-zero metadata hash (am)
    - Metadata is flagged as ARC89 native
    - Metadata is NOT flagged as ARC3
    - The ASA's metadata hash MATCHES the computed hash

    Note: This test demonstrates that when the ASA has no metadata hash (zero am),
    the contract computes and sets the hash correctly. We verify the computed hash
    matches what the SDK computes.
    """
    # Create ASA without metadata hash first (the contract will compute it)
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            url=arc89_partial_uri,  # ARC89 compliant URL, NOT ARC3
        )
    ).asset_id

    # Create metadata with ARC89 native flag
    metadata_body = MetadataBody(raw_bytes=b'{"name":"Test"}')
    flags = MetadataFlags(
        reversible=ReversibleFlags.empty(),
        irreversible=IrreversibleFlags(
            arc89_native=True
        ),  # No immutable needed since no am
    )
    metadata = AssetMetadata(
        asset_id=asset_id,
        body=metadata_body,
        flags=flags,
        deprecated_by=0,
    )

    # This should succeed - the contract computes the hash since am is zero
    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    # Verify the metadata was created and hash matches SDK computation
    created_metadata = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert created_metadata.header.flags.irreversible.arc89_native
    assert not created_metadata.header.flags.irreversible.arc3
    # The contract-computed hash should match what the SDK computes
    assert (
        created_metadata.header.metadata_hash == metadata.compute_arc89_metadata_hash()
    )


def test_arc89_native_with_arc3_bypasses_hash_check(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc89_partial_uri: str,
) -> None:
    """
    Test that metadata creation SUCCEEDS when:
    - ASA has a non-zero metadata hash (am)
    - Metadata is flagged as ARC89 native
    - Metadata IS flagged as ARC3
    - The hash check is bypassed because ARC3 uses its own hash convention
    """
    # Create an arbitrary hash that won't match the computed hash
    arbitrary_hash = b"ARC3_COMPUTED_HASH_EXAMPLE_OK__"
    assert len(arbitrary_hash) < 32
    arbitrary_hash = arbitrary_hash.ljust(32, b"\x00")

    # Create ASA with ARC89+ARC3 compliant URL
    arc89_arc3_url = arc89_partial_uri + const.ARC3_URL_SUFFIX.decode()
    asset_id = asa_metadata_registry_client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=asset_manager.address,
            manager=asset_manager.address,
            total=42,
            url=arc89_arc3_url,
            metadata_hash=arbitrary_hash,
        )
    ).asset_id

    # Create metadata with both ARC89 native AND ARC3 flags (and immutable for non-zero am)
    metadata = AssetMetadata.from_json(
        asset_id=asset_id,
        json_obj=create_arc3_payload(name="ARC3 + ARC89 Test"),
        flags=MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(
                arc89_native=True, arc3=True, immutable=True
            ),
        ),
    )

    # This should succeed because ARC3 flag bypasses the hash check
    create_metadata(
        asset_manager=asset_manager,
        asa_metadata_registry_client=asa_metadata_registry_client,
        asset_id=asset_id,
        metadata=metadata,
    )

    # Verify the metadata was created with the ASA's metadata hash
    created_metadata = get_metadata_from_state(asa_metadata_registry_client, asset_id)
    assert created_metadata.header.flags.irreversible.arc89_native
    assert created_metadata.header.flags.irreversible.arc3
    assert created_metadata.header.metadata_hash == arbitrary_hash
