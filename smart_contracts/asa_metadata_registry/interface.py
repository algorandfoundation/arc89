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
        reversible_flags: arc4.Byte,
        irreversible_flags: arc4.Byte,
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

    @abstractmethod
    @arc4.abimethod
    def arc89_replace_metadata_slice(
        self,
        *,
        asset_id: Asset,
        offset: arc4.UInt16,
        payload: arc4.DynamicBytes,
    ) -> None:
        pass

    @abstractmethod
    @arc4.abimethod
    def arc89_migrate_metadata(
        self,
        *,
        asset_id: Asset,
        new_registry_id: arc4.UInt64,
    ) -> None:
        pass

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

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_registry_parameters(self) -> abi.RegistryParameters:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_partial_uri(self) -> arc4.String:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_mbr_delta(
        self,
        *,
        asset_id: Asset,
        new_metadata_size: arc4.UInt16,
    ) -> abi.MbrDelta:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_check_metadata_exists(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MetadataExistence:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_is_metadata_immutable(
        self,
        *,
        asset_id: Asset,
    ) -> arc4.Bool:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_is_metadata_short(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MutableFlag:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_header(
        self,
        *,
        asset_id: Asset,
    ) -> abi.MetadataHeader:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_pagination(
        self,
        *,
        asset_id: Asset,
    ) -> abi.Pagination:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata(
        self,
        *,
        asset_id: Asset,
        page: arc4.UInt8,
    ) -> abi.PaginatedMetadata:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_slice(
        self,
        *,
        asset_id: Asset,
        offset: arc4.UInt16,
        size: arc4.UInt16,
    ) -> arc4.DynamicBytes:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_header_hash(
        self,
        *,
        asset_id: Asset,
    ) -> abi.Hash:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_page_hash(
        self,
        *,
        asset_id: Asset,
        page: arc4.UInt8,
    ) -> abi.Hash:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_hash(
        self,
        *,
        asset_id: Asset,
    ) -> abi.Hash:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_string_by_key(
        self,
        *,
        asset_id: Asset,
        key: arc4.String,
    ) -> arc4.String:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_uint64_by_key(
        self,
        *,
        asset_id: Asset,
        key: arc4.String,
    ) -> arc4.UInt64:
        pass

    @abstractmethod
    @arc4.abimethod(readonly=True)
    def arc89_get_metadata_object_by_key(
        self,
        *,
        asset_id: Asset,
        key: arc4.String,
    ) -> arc4.String:
        pass
