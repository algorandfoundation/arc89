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
from asa_metadata_registry.generated.asa_metadata_registry_client import (
    Arc89CreateMetadataArgs,
    Arc89ExtraPayloadArgs,
    Arc89ReplaceMetadataArgs,
    Arc89ReplaceMetadataSliceArgs,
    AsaMetadataRegistryClient,
    AsaMetadataRegistryComposer,
)
from smart_contracts.asa_metadata_registry import errors as err
from tests.helpers.utils import (
    NON_EXISTENT_ASA_ID,
    add_extra_resources,
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

    if not metadata.is_empty:
        add_extra_resources(composer)
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


def add_create_head(
    client: AsaMetadataRegistryClient,
    composer: AsaMetadataRegistryComposer,
    sender: SigningAccount,
    metadata: AssetMetadata,
) -> None:
    composer.arc89_create_metadata(
        args=Arc89CreateMetadataArgs(
            asset_id=metadata.asset_id,
            reversible_flags=metadata.flags.reversible_byte,
            irreversible_flags=metadata.flags.irreversible_byte,
            metadata_size=metadata.body.size,
            payload=metadata.body.chunked_payload()[0],
            mbr_delta_payment=create_mbr_payment(client, sender, metadata),
        ),
        params=CommonAppCallParams(
            sender=sender.address,
            static_fee=AlgoAmount(micro_algo=get_create_metadata_fee(client, metadata)),
        ),
    )


def add_extra_payload(
    composer: AsaMetadataRegistryComposer,
    sender: SigningAccount,
    asset_id: int,
    payload: bytes,
) -> None:
    composer.arc89_extra_payload(
        args=Arc89ExtraPayloadArgs(asset_id=asset_id, payload=payload),
        params=CommonAppCallParams(
            sender=sender.address, static_fee=AlgoAmount(micro_algo=0)
        ),
    )


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


def test_fail_stray_extra_payload(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # Existing record and manager sender: only the missing head call can fail the chunk
    composer = asa_metadata_registry_client.new_group()
    composer.extra_resources(params=CommonAppCallParams(sender=asset_manager.address))
    add_extra_payload(
        composer, asset_manager, mutable_short_metadata.asset_id, b"stray"
    )
    with pytest.raises(LogicError, match=err.NO_PAYLOAD_HEAD_CALL):
        composer.send()


def test_fail_extra_payload_after_slice(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # A slice is not a head call: the trailing chunk fails instead of being dropped
    composer = asa_metadata_registry_client.new_group()
    composer.arc89_replace_metadata_slice(
        args=Arc89ReplaceMetadataSliceArgs(
            asset_id=mutable_short_metadata.asset_id, offset=0, payload=b"patch"
        ),
        params=CommonAppCallParams(
            sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=5_000)
        ),
    )
    add_extra_payload(
        composer, asset_manager, mutable_short_metadata.asset_id, b"dropped"
    )
    with pytest.raises(LogicError, match=err.NO_PAYLOAD_HEAD_CALL):
        composer.send()


def test_fail_extra_payload_before_head(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
) -> None:
    # The head scans forward only: a chunk placed before it has no head call
    size = mutable_short_metadata.body.size
    composer = asa_metadata_registry_client.new_group()
    composer.extra_resources(params=CommonAppCallParams(sender=asset_manager.address))
    add_extra_payload(
        composer, asset_manager, mutable_short_metadata.asset_id, b"early"
    )
    composer.arc89_replace_metadata(
        args=Arc89ReplaceMetadataArgs(
            asset_id=mutable_short_metadata.asset_id,
            metadata_size=size,
            payload=b"Q" * size,
        ),
        params=CommonAppCallParams(
            sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=5_000)
        ),
    )
    with pytest.raises(LogicError, match=err.NO_PAYLOAD_HEAD_CALL):
        composer.send()


class TestExtraPayloadGroups:
    """Extra payload chunks in groups with several head calls."""

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

    def _two_assets(
        self,
        client: AsaMetadataRegistryClient,
        sender: SigningAccount,
        partial_uri: str,
    ) -> tuple[AssetMetadata, AssetMetadata]:
        asset_1 = create_test_asa(client, sender, "Group ASA 1", "GRP1", partial_uri)
        asset_2 = create_test_asa(client, sender, "Group ASA 2", "GRP2", partial_uri)
        metadata_1 = create_metadata_for_asset(
            asset_1, b"X" * (const.FIRST_PAYLOAD_MAX_SIZE + 50)
        )
        metadata_2 = create_metadata_for_asset(
            asset_2, b"Y" * (const.FIRST_PAYLOAD_MAX_SIZE + 100)
        )
        return metadata_1, metadata_2

    def test_contiguous_extra_payloads_two_assets(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """[pay1, create1, chunk1, pay2, create2, chunk2]: each head gets its own run."""
        client = asa_metadata_registry_client
        metadata_1, metadata_2 = self._two_assets(
            client, asset_manager, arc89_partial_uri
        )
        composer = client.new_group()
        for metadata in (metadata_1, metadata_2):
            add_create_head(client, composer, asset_manager, metadata)
            add_extra_payload(
                composer,
                asset_manager,
                metadata.asset_id,
                metadata.body.chunked_payload()[1],
            )
        add_extra_resources(composer, 2)
        composer.send()
        verify_metadata_box(
            client, metadata_1.asset_id, metadata_1.body.raw_bytes, b"X"
        )
        verify_metadata_box(
            client, metadata_2.asset_id, metadata_2.body.raw_bytes, b"Y"
        )

    def test_fail_interleaved_extra_payloads(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """[pay1, create1, pay2, create2, chunk2, chunk1]: create1 stops at pay2."""
        client = asa_metadata_registry_client
        metadata_1, metadata_2 = self._two_assets(
            client, asset_manager, arc89_partial_uri
        )
        composer = client.new_group()
        add_create_head(client, composer, asset_manager, metadata_1)
        add_create_head(client, composer, asset_manager, metadata_2)
        for metadata in (metadata_2, metadata_1):
            add_extra_payload(
                composer,
                asset_manager,
                metadata.asset_id,
                metadata.body.chunked_payload()[1],
            )
        add_extra_resources(composer, 2)
        with pytest.raises(LogicError, match=err.METADATA_SIZE_MISMATCH):
            composer.send()

    def test_two_heads_same_asset(
        self,
        asset_manager: SigningAccount,
        asa_metadata_registry_client: AsaMetadataRegistryClient,
        arc89_partial_uri: str,
    ) -> None:
        """[pay, create, chunk, replace, chunk]: the create head stops at the replace."""
        client = asa_metadata_registry_client
        asset_id = create_test_asa(
            client, asset_manager, "Two Heads ASA", "TWOH", arc89_partial_uri
        )
        size = const.FIRST_PAYLOAD_MAX_SIZE + 10
        created = create_metadata_for_asset(asset_id, b"C" * size)
        replaced = create_metadata_for_asset(asset_id, b"R" * size)
        composer = client.new_group()
        add_create_head(client, composer, asset_manager, created)
        add_extra_payload(
            composer, asset_manager, asset_id, created.body.chunked_payload()[1]
        )
        composer.arc89_replace_metadata(
            args=Arc89ReplaceMetadataArgs(
                asset_id=asset_id,
                metadata_size=size,
                payload=replaced.body.chunked_payload()[0],
            ),
            params=CommonAppCallParams(
                sender=asset_manager.address, static_fee=AlgoAmount(micro_algo=12_000)
            ),
        )
        add_extra_payload(
            composer, asset_manager, asset_id, replaced.body.chunked_payload()[1]
        )
        add_extra_resources(composer, 2)
        composer.send()
        verify_metadata_box(client, asset_id, replaced.body.raw_bytes, b"R")
