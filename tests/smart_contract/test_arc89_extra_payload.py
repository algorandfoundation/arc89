import pytest
from algokit_utils import (
    AlgoAmount,
    AssetCreateParams,
    CommonAppCallParams,
    LogicError,
    SigningAccount,
)

from asa_metadata_registry import AssetMetadata, MetadataBody, MetadataFlags
from asa_metadata_registry import constants as const
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    Arc89CreateMetadataArgs,
    Arc89ExtraPayloadArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import (
    NON_EXISTENT_ASA_ID,
    create_mbr_payment,
    get_create_metadata_fee,
)


def create_test_asa(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    name: str,
    unit_name: str,
    url: str,
) -> int:
    """Create a test ASA and return its asset ID."""
    return client.algorand.send.asset_create(
        params=AssetCreateParams(
            sender=sender.address,
            total=1,
            asset_name=name,
            unit_name=unit_name,
            url=url,
            decimals=0,
            default_frozen=False,
            manager=sender.address,
        )
    ).asset_id


def create_metadata_for_asset(
    asset_id: int,
    payload: bytes,
) -> AssetMetadata:
    """Create an AssetMetadata object for a given asset and payload."""
    return AssetMetadata(
        asset_id=asset_id,
        body=MetadataBody(raw_bytes=payload),
        flags=MetadataFlags.empty(),
        deprecated_by=0,
    )


def send_create_metadata_with_chunks(
    client: AsaMetadataRegistryClient,
    sender: SigningAccount,
    metadata: AssetMetadata,
    note: bytes | None = None,
) -> None:
    """Create metadata entry with all required extra_payload chunks."""
    chunks = list(metadata.body.chunked_payload())
    mbr_payment = create_mbr_payment(client, sender, metadata)
    fee = get_create_metadata_fee(client, metadata)

    composer = client.new_group()
    composer.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=metadata.asset_id,
            reversible_flags=metadata.flags.reversible_byte,
            irreversible_flags=metadata.flags.irreversible_byte,
            metadata_size=metadata.body.size,
            payload=chunks[0],
            mbr_delta_payment=mbr_payment,
        ),
        params=CommonAppCallParams(
            sender=sender.address,
            static_fee=AlgoAmount(micro_algo=fee),
        ),
    )

    for chunk in chunks[1:]:
        composer.arc89_extra_payload(
            args=Arc89ExtraPayloadArgs(
                asset_id=metadata.asset_id,
                payload=chunk,
            ),
            params=CommonAppCallParams(
                sender=sender.address,
                static_fee=AlgoAmount(micro_algo=0),
                note=note,
            ),
        )

    composer.send()


def verify_metadata_box(
    client: AsaMetadataRegistryClient,
    asset_id: int,
    expected_payload: bytes,
    expected_pattern_byte: bytes,
) -> None:
    """Verify that a metadata box exists with the expected content."""
    box_value = client.state.box.asset_metadata.get_value(asset_id)
    assert box_value is not None, f"Metadata for asset {asset_id} should exist"
    assert (
        box_value[const.HEADER_SIZE : const.HEADER_SIZE + 10]
        == expected_pattern_byte * 10
    )
    assert len(box_value) == const.HEADER_SIZE + len(expected_payload)


def test_fail_no_payload_head_call(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    with pytest.raises(LogicError, match=err.NO_PAYLOAD_HEAD_CALL):
        asa_metadata_registry_client.send.arc89_extra_payload(
            args=Arc89ExtraPayloadArgs(
                asset_id=mutable_short_metadata.asset_id,
                payload=b"extra payload",
            ),
            params=CommonAppCallParams(sender=asset_manager.address),
        )


def test_fail_asa_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
) -> None:
    # Create a group with 2 transactions to bypass NO_PAYLOAD_HEAD_CALL check
    composer = asa_metadata_registry_client.new_group()
    # First transaction - extra_resources as a dummy head call
    composer.extra_resources(
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    # Second transaction - the actual extra_payload call with non-existent ASA
    composer.arc89_extra_payload(
        args=Arc89ExtraPayloadArgs(
            asset_id=NON_EXISTENT_ASA_ID,
            payload=b"extra payload",
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )

    with pytest.raises(LogicError, match=err.ASA_NOT_EXIST):
        composer.send()


def test_fail_asset_metadata_not_exist(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    arc_89_asa: int,
) -> None:
    # Create a group with 2 transactions to bypass NO_PAYLOAD_HEAD_CALL check
    composer = asa_metadata_registry_client.new_group()
    composer.extra_resources(
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    composer.arc89_extra_payload(
        args=Arc89ExtraPayloadArgs(
            asset_id=arc_89_asa,
            payload=b"extra payload",
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )

    with pytest.raises(LogicError, match=err.ASSET_METADATA_NOT_EXIST):
        composer.send()


def test_fail_unauthorized(
    untrusted_account: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # Create a group with 2 transactions to bypass NO_PAYLOAD_HEAD_CALL check
    composer = asa_metadata_registry_client.new_group()
    composer.extra_resources(
        params=CommonAppCallParams(sender=untrusted_account.address),
    )
    composer.arc89_extra_payload(
        args=Arc89ExtraPayloadArgs(
            asset_id=mutable_short_metadata.asset_id,
            payload=b"extra payload",
        ),
        params=CommonAppCallParams(sender=untrusted_account.address),
    )

    with pytest.raises(LogicError, match=err.UNAUTHORIZED):
        composer.send()


class TestInterleavedExtraPayload:
    """Test extra_payload calls with multiple chunks for different assets."""

    def test_create_metadata_with_multiple_extra_payloads(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """Test creating metadata entries that require multiple extra_payload calls.

        This test verifies that extra_payload calls correctly append payload data
        to metadata for assets that require multiple chunks.
        """
        # Create two test ASAs
        asset_1 = create_test_asa(
            asa_metadata_registry_client,
            asset_manager,
            "Multi-chunk Test ASA 1",
            "MCT1",
            arc89_partial_uri,
        )
        asset_2 = create_test_asa(
            asa_metadata_registry_client,
            asset_manager,
            "Multi-chunk Test ASA 2",
            "MCT2",
            arc89_partial_uri,
        )

        # Create metadata that requires extra_payload calls (larger than FIRST_PAYLOAD_MAX_SIZE)
        # Each metadata needs 2 extra_payload chunks
        payload_1 = b"A" * (
            const.FIRST_PAYLOAD_MAX_SIZE + const.EXTRA_PAYLOAD_MAX_SIZE + 100
        )
        payload_2 = b"B" * (
            const.FIRST_PAYLOAD_MAX_SIZE + const.EXTRA_PAYLOAD_MAX_SIZE + 100
        )

        metadata_1 = create_metadata_for_asset(asset_1, payload_1)
        metadata_2 = create_metadata_for_asset(asset_2, payload_2)

        # Get chunked payloads
        chunks_1 = list(metadata_1.body.chunked_payload())
        chunks_2 = list(metadata_2.body.chunked_payload())

        assert len(chunks_1) >= 2, "Metadata 1 should require at least 2 chunks"
        assert len(chunks_2) >= 2, "Metadata 2 should require at least 2 chunks"

        # Create metadata for both assets with all their extra_payload chunks
        send_create_metadata_with_chunks(
            asa_metadata_registry_client, asset_manager, metadata_1
        )
        send_create_metadata_with_chunks(
            asa_metadata_registry_client, asset_manager, metadata_2
        )

        # Verify that both metadata entries were created correctly
        verify_metadata_box(asa_metadata_registry_client, asset_1, payload_1, b"A")
        verify_metadata_box(asa_metadata_registry_client, asset_2, payload_2, b"B")

    def test_interleaved_extra_payloads_wrong_order_still_works(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """Test that extra_payload calls work even when completely out of order.

        Group structure (maximally interleaved):
        - [0] MBR Payment for asset_1
        - [1] create_metadata for asset_1
        - [2] MBR Payment for asset_2
        - [3] create_metadata for asset_2
        - [4] extra_payload for asset_2 (first chunk for asset_2)
        - [5] extra_payload for asset_1 (first chunk for asset_1)
        """
        # Create two test ASAs
        asset_1 = create_test_asa(
            asa_metadata_registry_client,
            asset_manager,
            "Reverse Order ASA 1",
            "REV1",
            arc89_partial_uri,
        )
        asset_2 = create_test_asa(
            asa_metadata_registry_client,
            asset_manager,
            "Reverse Order ASA 2",
            "REV2",
            arc89_partial_uri,
        )

        # Create metadata that requires exactly one extra_payload call
        payload_1 = b"X" * (const.FIRST_PAYLOAD_MAX_SIZE + 50)
        payload_2 = b"Y" * (const.FIRST_PAYLOAD_MAX_SIZE + 100)

        metadata_1 = create_metadata_for_asset(asset_1, payload_1)
        metadata_2 = create_metadata_for_asset(asset_2, payload_2)

        chunks_1 = list(metadata_1.body.chunked_payload())
        chunks_2 = list(metadata_2.body.chunked_payload())

        assert len(chunks_1) == 2, "Metadata 1 should require exactly 2 chunks"
        assert len(chunks_2) == 2, "Metadata 2 should require exactly 2 chunks"

        # Create MBR payments
        mbr_payment_1 = create_mbr_payment(
            asa_metadata_registry_client, asset_manager, metadata_1
        )
        mbr_payment_2 = create_mbr_payment(
            asa_metadata_registry_client, asset_manager, metadata_2
        )

        # Calculate fees - create_metadata needs to cover its extra_payload calls
        fee_1 = get_create_metadata_fee(asa_metadata_registry_client, metadata_1)
        fee_2 = get_create_metadata_fee(asa_metadata_registry_client, metadata_2)

        composer = asa_metadata_registry_client.new_group()

        # Add create_metadata for asset_1
        composer.arc89_create_metadata(
            args=Arc89CreateMetadataArgs(
                asset_id=asset_1,
                reversible_flags=metadata_1.flags.reversible_byte,
                irreversible_flags=metadata_1.flags.irreversible_byte,
                metadata_size=metadata_1.body.size,
                payload=chunks_1[0],
                mbr_delta_payment=mbr_payment_1,
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=fee_1),
            ),
        )

        # Add create_metadata for asset_2
        composer.arc89_create_metadata(
            args=Arc89CreateMetadataArgs(
                asset_id=asset_2,
                reversible_flags=metadata_2.flags.reversible_byte,
                irreversible_flags=metadata_2.flags.irreversible_byte,
                metadata_size=metadata_2.body.size,
                payload=chunks_2[0],
                mbr_delta_payment=mbr_payment_2,
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=fee_2),
            ),
        )

        # Add extra_payload for asset_2 FIRST (reverse order!)
        composer.arc89_extra_payload(
            args=Arc89ExtraPayloadArgs(
                asset_id=asset_2,
                payload=chunks_2[1],
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=0),
                note=b"extra_payload_asset_2",
            ),
        )

        # Add extra_payload for asset_1 SECOND (reverse order!)
        composer.arc89_extra_payload(
            args=Arc89ExtraPayloadArgs(
                asset_id=asset_1,
                payload=chunks_1[1],
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address,
                static_fee=AlgoAmount(micro_algo=0),
                note=b"extra_payload_asset_1",
            ),
        )

        # Send the group
        composer.send()

        # Verify both metadata entries were created correctly
        verify_metadata_box(asa_metadata_registry_client, asset_1, payload_1, b"X")
        verify_metadata_box(asa_metadata_registry_client, asset_2, payload_2, b"Y")
