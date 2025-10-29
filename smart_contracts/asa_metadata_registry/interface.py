from abc import ABC, abstractmethod

from algopy import ARC4Contract, Asset, arc4, gtxn

from . import abi_types as abi


class AsaMetadataRegistryInterface(ARC4Contract, ABC):
    @abstractmethod
    @arc4.baremethod(create="require")
    def create(self) -> None:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_create_metadata(
        self,
        asset_id: Asset,
        flags: arc4.Byte,
        payload: arc4.DynamicBytes,
        mbr_delta_payment: gtxn.PaymentTransaction,
    ) -> abi.MbrDelta:
        """Create Asset Metadata for an existing ASA, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to create the Asset Metadata for
            flags: The Metadata Flags. WARNING: if the MSB is True the Asset Metadata is IMMUTABLE
            payload: The Metadata payload (without Header). WARNING: Payload larger than args capacity
                     must be provided with arc89_extra_payload calls in the Group
            mbr_delta_payment: Payment of the MBR Delta amount (microALGO) for the Asset Metadata Box creation

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_replace_metadata(
        self,
        asset_id: Asset,
        payload: arc4.DynamicBytes,
    ) -> abi.MbrDelta:
        """Replace mutable Metadata with a smaller or equal size payload for an existing ASA,
        restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to replace the Asset Metadata for
            payload: The Metadata payload (without Header). WARNING: Payload larger than args capacity
                     must be provided with arc89_extra_payload calls in the Group

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_replace_metadata_larger(
        self,
        asset_id: Asset,
        payload: arc4.DynamicBytes,
        mbr_delta_payment: gtxn.PaymentTransaction,
    ) -> abi.MbrDelta:
        """Replace mutable Metadata with a larger size payload for an existing ASA,
        restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to replace the Asset Metadata for
            payload: The Metadata payload (without Header). WARNING: Payload larger than args capacity
                     must be provided with arc89_extra_payload calls in the Group
            mbr_delta_payment: Payment of the MBR Delta amount (microALGO) for the larger Asset Metadata Box replace

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_delete_metadata(
        self,
        asset_id: Asset,
    ) -> abi.MbrDelta:
        """Delete Asset Metadata for an ASA, restricted to the ASA Manager Address (if the ASA still exists).

        Args:
            asset_id: The Asset ID to delete the Asset Metadata for

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_extra_payload(
        self,
        asset_id: Asset,
        payload: arc4.DynamicBytes,
    ) -> None:
        """Concatenate extra payload to Asset Metadata head call methods (creation or replacement).

        Args:
            asset_id: The Asset ID to provide Metadata extra payload for
            payload: The Metadata extra payload to concatenate
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_set_metadata_flags(
        self,
        asset_id: Asset,
        flags: arc4.Byte,
    ) -> None:
        """Set Asset Metadata Flags, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to set the Metadata Flags for
            flags: The Metadata Flags. WARNING: bits 4...MSB are irreversible if set to True,
                MSB set Asset Metadata as IMMUTABLE
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_set_arc20(
        self,
        asset_id: Asset,
        flag: arc4.Bool,
    ) -> None:
        """Set ARC-20 Smart ASA support for the ASA, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to set ARC-20 support for
            flag: The Asset ID supports ARC-20
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_set_arc62(
        self,
        asset_id: Asset,
        flag: arc4.Bool,
    ) -> None:
        """Set ARC-62 Circulating Supply support for the ASA, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to set ARC-62 support for
            flag: The Asset ID supports ARC-62
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_set_immutable(
        self,
        asset_id: Asset,
    ) -> None:
        """Set Asset Metadata as immutable, restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to set immutable Asset Metadata for
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_replace_metadata_slice(
        self,
        asset_id: Asset,
        offset: arc4.UInt16,
        size: arc4.UInt16,
        payload: arc4.DynamicBytes,
    ) -> None:
        """Replace a slice of the Asset Metadata for an ASA with a payload of the same size,
        restricted to the ASA Manager Address.

        Args:
            asset_id: The Asset ID to replace the Asset Metadata slice for
            offset: The 0-based byte offset within the Metadata
            size: The slice bytes size to set
            payload: The slice payload
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_registry_parameters(
        self,
    ) -> arc4.Tuple[
        arc4.UInt16, arc4.UInt16, arc4.UInt16, arc4.UInt16, arc4.UInt64, arc4.UInt64
    ]:
        """Return the ASA Metadata Registry parameters.

        Returns:
            Tuple of (HEADER_SIZE, MAX_METADATA_SIZE, MAX_SHORT_METADATA_SIZE, PAGE_SIZE, FLAT_MBR, BYTE_MBR)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_mbr_delta(
        self,
        asset_id: Asset,
        metadata_size: arc4.UInt16,
    ) -> abi.MbrDelta:
        """Return the Asset Metadata Box MBR Delta for an ASA, given a new Asset Metadata byte size.

        Args:
            asset_id: The Asset ID to calculate the Asset Metadata MBR Delta for
            metadata_size: The Asset Metadata byte size

        Returns:
            MBR Delta: tuple of (sign enum, amount in microALGO)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_check_metadata_exists(
        self,
        asset_id: Asset,
    ) -> arc4.Tuple[arc4.Bool, arc4.Bool]:
        """Checks whether the specified ASA exists and whether its associated Asset Metadata is available.

        Args:
            asset_id: The Asset ID to check the ASA and Asset Metadata existence for

        Returns:
            Tuple of (ASA exists, Asset Metadata exists)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_is_arc20_asa(
        self,
        asset_id: Asset,
    ) -> abi.MutableFlag:
        """Return True if the ASA is an ARC-20 Smart ASA, False otherwise.

        Args:
            asset_id: The Asset ID to check ARC-20 setting for

        Returns:
            Tuple of (is ARC-20 ASA, Metadata Last Modified Round)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_is_arc62_asa(
        self,
        asset_id: Asset,
    ) -> abi.MutableFlag:
        """Return True if the ASA supports ARC-62 Circulating Supply, False otherwise.

        Args:
            asset_id: The Asset ID to check ARC-62 setting for

        Returns:
            Tuple of (supports ARC-62, Metadata Last Modified Round)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_is_metadata_immutable(
        self,
        asset_id: Asset,
    ) -> arc4.Bool:
        """Return True if the Asset Metadata for an ASA is immutable, False otherwise.

        Args:
            asset_id: The Asset ID to check the Asset Metadata immutability for

        Returns:
            Asset Metadata for the ASA is immutable
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_is_arc3_asa(
        self,
        asset_id: Asset,
    ) -> arc4.Bool:
        """Return True if the ASA is ARC-3 Compliant, False otherwise.

        Args:
            asset_id: The Asset ID to check ARC-3 identification for

        Returns:
            The ASA is an ARC-3 ASA
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_is_native_asa(
        self,
        asset_id: Asset,
    ) -> arc4.Bool:
        """Return True if the ASA is a native ARC-89 ASA, False otherwise.

        Args:
            asset_id: The Asset ID to check the ARC-89 native definition for

        Returns:
            The ASA is native ARC-89
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_is_metadata_short(
        self,
        asset_id: Asset,
    ) -> abi.MutableFlag:
        """Return True if Asset Metadata for an ASA is short (up to 4096 bytes), False otherwise.

        Args:
            asset_id: The Asset ID to check the Asset Metadata size classification for

        Returns:
            Tuple of (is short metadata, Metadata Last Modified Round)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_header(
        self,
        asset_id: Asset,
    ) -> arc4.Tuple[arc4.Byte, arc4.Byte, abi.Hash, arc4.UInt64]:
        """Return the Asset Metadata Header for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata Header for

        Returns:
            Asset Metadata Header: (Identifiers, Flags, Hash, Last Modified Round)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_pagination(
        self,
        asset_id: Asset,
    ) -> arc4.Tuple[arc4.UInt16, arc4.UInt16, arc4.UInt8]:
        """Return the Asset Metadata pagination for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata pagination for

        Returns:
            Tuple of (total Metadata byte size, PAGE_SIZE, total number of pages)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata(
        self,
        asset_id: Asset,
        page: arc4.UInt8,
    ) -> arc4.Tuple[arc4.Bool, arc4.UInt64, arc4.DynamicBytes]:
        """Return paginated Asset Metadata (without Header) for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata for
            page: The 0-based Metadata page number

        Returns:
            Tuple of (has next page, Metadata Last Modified Round, paginated Asset Metadata)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_page_hash(
        self,
        asset_id: Asset,
        page: arc4.UInt8,
    ) -> abi.Hash:
        """Return the SHA512-256 of a Metadata page for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata page hash for
            page: The 0-based Metadata page number

        Returns:
            The SHA512-256 of the Metadata page
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_slice(
        self,
        asset_id: Asset,
        offset: arc4.UInt16,
        size: arc4.UInt16,
    ) -> arc4.DynamicBytes:
        """Return a slice of the Asset Metadata for an ASA.

        Args:
            asset_id: The Asset ID to get the Asset Metadata slice for
            offset: The 0-based byte offset within the Metadata
            size: The slice bytes size to return

        Returns:
            Asset Metadata slice (size limited to PAGE_SIZE)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_header_hash(
        self,
        asset_id: Asset,
    ) -> abi.Hash:
        """Return the Metadata Header Hash for an ASA.

        Args:
            asset_id: The Asset ID to get the Metadata Header Hash for

        Returns:
            Asset Metadata Header Hash
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_hash(
        self,
        asset_id: Asset,
    ) -> abi.Hash:
        """Return the Metadata Hash for an ASA.

        Args:
            asset_id: The Asset ID to get the Metadata Hash for

        Returns:
            Asset Metadata Hash
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_get_metadata_key_value(
        self,
        asset_id: Asset,
        key: arc4.DynamicBytes,
        key_type: arc4.UInt8,
    ) -> arc4.DynamicBytes:
        """Return the JSON Metadata key value for an ASA, if identified as short.

        Args:
            asset_id: The Asset ID to get the key value for
            key: The key to fetch
            key_type: The JSON key type (0: JSON String, 1: JSON Uint64, 2: JSON Object)

        Returns:
            The key's value from valid UTF-8 encoded JSON Metadata (size limited to PAGE_SIZE)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_precompute_metadata_identifiers(
        self,
        asset_name: arc4.String,
        asset_unit: arc4.String,
        asset_url: arc4.String,
        metadata_size: arc4.UInt16,
    ) -> arc4.Tuple[arc4.Bool, arc4.Bool, arc4.Bool]:
        """Pre-compute the Metadata Identifiers based on ASA field and Metadata size, before the ASA creation.

        Args:
            asset_name: The Asset Name field
            asset_unit: The Asset Unit field
            asset_url: The Asset URL field
            metadata_size: The Asset Metadata byte size at creation

        Returns:
            Asset Metadata Identifiers bits in the following order: (LSB, 4, MSB)
        """
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_validate_metadata_identifiers(
        self,
        asset_id: Asset,
        metadata_size: arc4.UInt16,
        expected_identifiers: arc4.Byte,
    ) -> arc4.Bool:
        """Validate expected Metadata Identifiers for an ASA, given the ASA field and Metadata size.

        Args:
            asset_id: The Asset ID to validate the Metadata Identifiers for
            metadata_size: The Asset Metadata byte size at creation
            expected_identifiers: The expected Metadata Identifiers bits

        Returns:
            Returns True if the ASA is identified with the expected Metadata Identifiers bits
        """
        pass
