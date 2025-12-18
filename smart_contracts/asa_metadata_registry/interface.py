from abc import ABC, abstractmethod

from algopy import ARC4Contract, Asset, arc4, gtxn

from . import abi_types as abi


class AsaMetadataRegistryInterface(ARC4Contract, ABC):
    @abstractmethod
    @arc4.abimethod
    def arc89_create_metadata(
        self,
        *,
        asset_id: Asset,
        flags: arc4.Byte,
        metadata_size: arc4.UInt16,
        payload: arc4.DynamicBytes,
        mbr_delta_payment: gtxn.PaymentTransaction,
    ) -> abi.MbrDelta:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_replace_metadata(
        self,
        *,
        asset_id: Asset,
        metadata_size: arc4.UInt16,
        payload: arc4.DynamicBytes,
    ) -> abi.MbrDelta:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_replace_metadata_larger(
        self,
        *,
        asset_id: Asset,
        metadata_size: arc4.UInt16,
        payload: arc4.DynamicBytes,
        mbr_delta_payment: gtxn.PaymentTransaction,
    ) -> abi.MbrDelta:
        pass

    # @abstractmethod
    # @arc4.abimethod
    # def arc89_replace_metadata_slice(
    #     self,
    #     asset_id: Asset,
    #     offset: arc4.UInt16,
    #     size: arc4.UInt16,
    #     payload: arc4.DynamicBytes,
    # ) -> None:
    #     """Replace a slice of the Asset Metadata for an ASA with a payload of the same size,
    #     restricted to the ASA Manager Address.
    #
    #     Args:
    #         asset_id: The Asset ID to replace the Asset Metadata slice for
    #         offset: The 0-based byte offset within the Metadata
    #         size: The slice bytes size to set
    #         payload: The slice payload
    #     """
    #     pass

    @abstractmethod
    @arc4.abimethod
    def arc89_delete_metadata(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MbrDelta:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_extra_payload(
        self,
        *,
        asset_id: Asset,
        payload: arc4.DynamicBytes,
    ) -> None:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_set_reversible_flag(
        self,
        *,
        asset_id: Asset,
        flag: arc4.UInt8,
        value: arc4.Bool,
    ) -> None:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_set_irreversible_flag(
        self,
        *,
        asset_id: Asset,
        flag: arc4.UInt8,
    ) -> None:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_set_immutable(
        self,
        *,
        asset_id: Asset,
    ) -> None:
        pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_registry_parameters(
    #     self,
    # ) -> arc4.Tuple[
    #     arc4.UInt16, arc4.UInt16, arc4.UInt16, arc4.UInt16, arc4.UInt64, arc4.UInt64
    # ]:
    #     """Return the ASA Metadata Registry parameters.
    #
    #     Returns:
    #         Tuple of (HEADER_SIZE, MAX_METADATA_SIZE, MAX_SHORT_METADATA_SIZE, PAGE_SIZE, FLAT_MBR, BYTE_MBR)
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_mbr_delta(
    #     self,
    #     asset_id: Asset,
    #     metadata_size: arc4.UInt16,
    # ) -> abi.MbrDelta:
    #     """Return the Asset Metadata Box MBR Delta for an ASA, given a new Asset Metadata byte size.
    #
    #     Args:
    #         asset_id: The Asset ID to calculate the Asset Metadata MBR Delta for
    #         metadata_size: The Asset Metadata byte size
    #
    #     Returns:
    #         MBR Delta: tuple of (sign enum, amount in microALGO)
    #     """
    #     pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_check_metadata_exists(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MetadataExistence:
        pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_is_metadata_immutable(
    #     self,
    #     asset_id: Asset,
    # ) -> arc4.Bool:
    #     """Return True if the Asset Metadata for an ASA is immutable, False otherwise.
    #
    #     Args:
    #         asset_id: The Asset ID to check the Asset Metadata immutability for
    #
    #     Returns:
    #         Asset Metadata for the ASA is immutable
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_is_metadata_short(
    #     self,
    #     asset_id: Asset,
    # ) -> abi.MutableFlag:
    #     """Return True if Asset Metadata for an ASA is short (up to 4096 bytes), False otherwise.
    #
    #     Args:
    #         asset_id: The Asset ID to check the Asset Metadata size classification for
    #
    #     Returns:
    #         Tuple of (is short metadata, Metadata Last Modified Round)
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_header(
    #     self,
    #     asset_id: Asset,
    # ) -> arc4.Tuple[arc4.Byte, arc4.Byte, abi.Hash, arc4.UInt64]:
    #     """Return the Asset Metadata Header for an ASA.
    #
    #     Args:
    #         asset_id: The Asset ID to get the Asset Metadata Header for
    #
    #     Returns:
    #         Asset Metadata Header: (Identifiers, Flags, Hash, Last Modified Round)
    #     """
    #     pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_pagination(
        self,
        *,
        asset_id: Asset,
    ) -> abi.Pagination:
        pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata(
    #     self,
    #     asset_id: Asset,
    #     page: arc4.UInt8,
    # ) -> arc4.Tuple[arc4.Bool, arc4.UInt64, arc4.DynamicBytes]:
    #     """Return paginated Asset Metadata (without Header) for an ASA.
    #
    #     Args:
    #         asset_id: The Asset ID to get the Asset Metadata for
    #         page: The 0-based Metadata page number
    #
    #     Returns:
    #         Tuple of (has next page, Metadata Last Modified Round, paginated Asset Metadata)
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_page_hash(
    #     self,
    #     asset_id: Asset,
    #     page: arc4.UInt8,
    # ) -> abi.Hash:
    #     """Return the SHA512-256 of a Metadata page for an ASA.
    #
    #     Args:
    #         asset_id: The Asset ID to get the Asset Metadata page hash for
    #         page: The 0-based Metadata page number
    #
    #     Returns:
    #         The SHA512-256 of the Metadata page
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_slice(
    #     self,
    #     asset_id: Asset,
    #     offset: arc4.UInt16,
    #     size: arc4.UInt16,
    # ) -> arc4.DynamicBytes:
    #     """Return a slice of the Asset Metadata for an ASA.
    #
    #     Args:
    #         asset_id: The Asset ID to get the Asset Metadata slice for
    #         offset: The 0-based byte offset within the Metadata
    #         size: The slice bytes size to return
    #
    #     Returns:
    #         Asset Metadata slice (size limited to PAGE_SIZE)
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_header_hash(
    #     self,
    #     asset_id: Asset,
    # ) -> abi.Hash:
    #     """Return the Metadata Header Hash for an ASA.
    #
    #     Args:
    #         asset_id: The Asset ID to get the Metadata Header Hash for
    #
    #     Returns:
    #         Asset Metadata Header Hash
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_hash(
    #     self,
    #     asset_id: Asset,
    # ) -> abi.Hash:
    #     """Return the Metadata Hash for an ASA.
    #
    #     Args:
    #         asset_id: The Asset ID to get the Metadata Hash for
    #
    #     Returns:
    #         Asset Metadata Hash
    #     """
    #     pass

    # @abstractmethod
    # @arc4.abimethod(readonly=True)
    # def arc89_get_metadata_key_value(
    #     self,
    #     asset_id: Asset,
    #     key: arc4.DynamicBytes,
    #     key_type: arc4.UInt8,
    # ) -> arc4.DynamicBytes:
    #     """Return the JSON Metadata key value for an ASA, if identified as short.
    #
    #     Args:
    #         asset_id: The Asset ID to get the key value for
    #         key: The key to fetch
    #         key_type: The JSON key type (0: JSON String, 1: JSON Uint64, 2: JSON Object)
    #
    #     Returns:
    #         The key's value from valid UTF-8 encoded JSON Metadata (size limited to PAGE_SIZE)
    #     """
    #     pass
