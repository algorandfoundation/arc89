# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class MbrDelta(algopy.arc4.Struct):
    sign: algopy.arc4.UIntN[typing.Literal[8]]
    amount: algopy.arc4.UIntN[typing.Literal[64]]

class RegistryParameters(algopy.arc4.Struct):
    key_size: algopy.arc4.UIntN[typing.Literal[8]]
    header_size: algopy.arc4.UIntN[typing.Literal[16]]
    max_metadata_size: algopy.arc4.UIntN[typing.Literal[16]]
    short_metadata_size: algopy.arc4.UIntN[typing.Literal[16]]
    page_size: algopy.arc4.UIntN[typing.Literal[16]]
    first_payload_max_size: algopy.arc4.UIntN[typing.Literal[16]]
    extra_payload_max_size: algopy.arc4.UIntN[typing.Literal[16]]
    replace_payload_max_size: algopy.arc4.UIntN[typing.Literal[16]]
    flat_mbr: algopy.arc4.UIntN[typing.Literal[64]]
    byte_mbr: algopy.arc4.UIntN[typing.Literal[64]]

class MetadataExistence(algopy.arc4.Struct):
    asa_exists: algopy.arc4.Bool
    metadata_exists: algopy.arc4.Bool

class MutableFlag(algopy.arc4.Struct):
    flag: algopy.arc4.Bool
    last_modified_round: algopy.arc4.UIntN[typing.Literal[64]]

class MetadataHeader(algopy.arc4.Struct):
    identifiers: algopy.arc4.Byte
    reversible_flags: algopy.arc4.Byte
    irreversible_flags: algopy.arc4.Byte
    hash: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]
    last_modified_round: algopy.arc4.UIntN[typing.Literal[64]]
    deprecated_by: algopy.arc4.UIntN[typing.Literal[64]]

class Pagination(algopy.arc4.Struct):
    metadata_size: algopy.arc4.UIntN[typing.Literal[16]]
    page_size: algopy.arc4.UIntN[typing.Literal[16]]
    total_pages: algopy.arc4.UIntN[typing.Literal[8]]

class PaginatedMetadata(algopy.arc4.Struct):
    has_next_page: algopy.arc4.Bool
    last_modified_round: algopy.arc4.UIntN[typing.Literal[64]]
    page_content: algopy.arc4.DynamicBytes

class AsaMetadataRegistry(algopy.arc4.ARC4Client, typing.Protocol):
    """

        Singleton Application providing ASA metadata via Algod API and AVM
    
    """
    @algopy.arc4.abimethod
    def arc89_create_metadata(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        reversible_flags: algopy.arc4.Byte,
        irreversible_flags: algopy.arc4.Byte,
        metadata_size: algopy.arc4.UIntN[typing.Literal[16]],
        payload: algopy.arc4.DynamicBytes,
        mbr_delta_payment: algopy.gtxn.PaymentTransaction,
    ) -> MbrDelta:
        """
        Create Asset Metadata for an existing ASA, restricted to the ASA Manager Address.
        """

    @algopy.arc4.abimethod
    def arc89_replace_metadata(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        metadata_size: algopy.arc4.UIntN[typing.Literal[16]],
        payload: algopy.arc4.DynamicBytes,
    ) -> MbrDelta:
        """
        Replace mutable Metadata with a smaller or equal size payload for an existing ASA,
        restricted to the ASA Manager Address.
        """

    @algopy.arc4.abimethod
    def arc89_replace_metadata_larger(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        metadata_size: algopy.arc4.UIntN[typing.Literal[16]],
        payload: algopy.arc4.DynamicBytes,
        mbr_delta_payment: algopy.gtxn.PaymentTransaction,
    ) -> MbrDelta:
        """
        Replace mutable Metadata with a larger size payload for an existing ASA,
        restricted to the ASA Manager Address.
        """

    @algopy.arc4.abimethod
    def arc89_replace_metadata_slice(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        offset: algopy.arc4.UIntN[typing.Literal[16]],
        payload: algopy.arc4.DynamicBytes,
    ) -> None:
        """
        Replace a slice of the Asset Metadata for an ASA with a payload of the same size,
        restricted to the ASA Manager Address.
        """

    @algopy.arc4.abimethod
    def arc89_migrate_metadata(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        new_registry_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None:
        """
        Migrate the Asset Metadata for an ASA to a new ASA Metadata Registry version,
        restricted to the ASA Manager Address
        """

    @algopy.arc4.abimethod
    def arc89_delete_metadata(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> MbrDelta:
        """
        Delete Asset Metadata for an ASA, restricted to the ASA Manager Address (if the ASA still exists).
        """

    @algopy.arc4.abimethod
    def arc89_extra_payload(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        payload: algopy.arc4.DynamicBytes,
    ) -> None:
        """
        Concatenate extra payload to Asset Metadata head call methods (creation or replacement).
        """

    @algopy.arc4.abimethod
    def arc89_set_reversible_flag(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        flag: algopy.arc4.UIntN[typing.Literal[8]],
        value: algopy.arc4.Bool,
    ) -> None:
        """
        Set a reversible Asset Metadata Flag, restricted to the ASA Manager Address
        """

    @algopy.arc4.abimethod
    def arc89_set_irreversible_flag(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        flag: algopy.arc4.UIntN[typing.Literal[8]],
    ) -> None:
        """
        Set an irreversible Asset Metadata Flag, restricted to the ASA Manager Address
        """

    @algopy.arc4.abimethod
    def arc89_set_immutable(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None:
        """
        Set Asset Metadata as immutable, restricted to the ASA Manager Address.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_registry_parameters(
        self,
    ) -> RegistryParameters:
        """
        Return the ASA Metadata Registry parameters.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_partial_uri(
        self,
    ) -> algopy.arc4.String:
        """
        Return the Asset Metadata ARC-90 partial URI, without compliance fragment (optional)
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_mbr_delta(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        new_metadata_size: algopy.arc4.UIntN[typing.Literal[16]],
    ) -> MbrDelta:
        """
        Return the Asset Metadata Box MBR Delta for an ASA, given a new Asset Metadata byte size.
        If the Asset Metadata Box does not exist, the creation MBR Delta is returned.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_check_metadata_exists(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> MetadataExistence:
        """
        Checks whether the specified ASA exists and whether its associated Asset Metadata is available.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_is_metadata_immutable(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool:
        """
        Return True if the Asset Metadata for an ASA is immutable, False otherwise.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_is_metadata_short(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> MutableFlag:
        """
        Return True if Asset Metadata for an ASA is short (up to 4096 bytes), False otherwise.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_header(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> MetadataHeader:
        """
        Return the Asset Metadata Header for an ASA.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_pagination(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> Pagination:
        """
        Return the Asset Metadata pagination for an ASA.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        page: algopy.arc4.UIntN[typing.Literal[8]],
    ) -> PaginatedMetadata:
        """
        Return paginated Asset Metadata (without Header) for an ASA.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_slice(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        offset: algopy.arc4.UIntN[typing.Literal[16]],
        size: algopy.arc4.UIntN[typing.Literal[16]],
    ) -> algopy.arc4.DynamicBytes:
        """
        Return a slice of the Asset Metadata for an ASA.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_header_hash(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]:
        """
        Return the Metadata Header Hash for an ASA.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_page_hash(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        page: algopy.arc4.UIntN[typing.Literal[8]],
    ) -> algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]:
        """
        Return the SHA512-256 of a Metadata page for an ASA.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_hash(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]:
        """
        Return the Metadata Hash for an ASA.
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_string_by_key(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        key: algopy.arc4.String,
    ) -> algopy.arc4.String:
        """
        Return the UTF-8 string value for a top-level JSON key of type JSON String
        from short Metadata for an ASA; errors if the key does not exist or is not a JSON String
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_uint64_by_key(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        key: algopy.arc4.String,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]:
        """
        Return the uint64 value for a top-level JSON key of type JSON Uint64 from
        short Metadata for an ASA; errors if the key does not exist or is not a JSON Uint64
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_object_by_key(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        key: algopy.arc4.String,
    ) -> algopy.arc4.String:
        """
        Return the UTF-8 object value for a top-level JSON key of type JSON Object
        from short Metadata for an ASA; errors if the key does not exist or is not a JSON Object
        """

    @algopy.arc4.abimethod(readonly=True)
    def arc89_get_metadata_b64_bytes_by_key(
        self,
        asset_id: algopy.arc4.UIntN[typing.Literal[64]],
        key: algopy.arc4.String,
        b64_encoding: algopy.arc4.UIntN[typing.Literal[8]],
    ) -> algopy.arc4.DynamicBytes:
        """
        Return the base64-decoded bytes for a top-level JSON key of type JSON String
        from short Metadata for an ASA; errors if the key does not exist, is not a JSON String, or is not valid base64 for the chosen encoding
        """

    @algopy.arc4.abimethod
    def extra_resources(
        self,
    ) -> None:
        """
        Non-normative placeholder method to acquire AVM extra resources.
        """

    @algopy.arc4.abimethod
    def withdraw_balance_excess(
        self,
    ) -> None:
        """
        Non-normative method to withdraw balance excess due to accidental deposits
        (it should never happen if deposits match exactly the required MBR. Deleted metadata MBR is not included in the excess, since it is immediately returned on delete).
        """
