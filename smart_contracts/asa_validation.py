from algopy import ARC4Contract, Asset, Bytes, Global, Txn, op

from .avm_library import arc90_box_query, endswith, startswith
from .constants import (
    ARC3_NAME,
    ARC3_NAME_SUFFIX,
    ARC3_URL_SUFFIX,
)


class AsaValidation(ARC4Contract):
    """Base class for ASA validation"""

    def _asa_exists(self, asa: Asset) -> bool:
        _creator, exists = op.AssetParamsGet.asset_creator(asa)
        return exists

    def _is_asa_manager(self, asa: Asset) -> bool:
        return Txn.sender == asa.manager

    def _is_arc3_compliant(self, asa: Asset) -> bool:
        asa_name = asa.name
        asa_url = asa.url
        arc3_name_suffix = Bytes(ARC3_NAME_SUFFIX)
        arc3_url_suffix = Bytes(ARC3_URL_SUFFIX)

        if asa_name == ARC3_NAME:
            return True

        if asa_name.length >= arc3_name_suffix.length:
            if endswith(asa_name, arc3_name_suffix):
                return True

        if asa_url.length >= arc3_url_suffix.length:
            if endswith(asa_url, arc3_url_suffix):
                return True

        return False

    def _is_arc89_compliant(self, asa: Asset) -> bool:
        # This validation does not enforce ARC-90 compliance fragments (optional)
        arc89_partial_uri = arc90_box_query(Global.current_application_id, Bytes())
        asa_url = asa.url

        if asa_url.length < arc89_partial_uri.length:
            return False

        return startswith(asa_url, arc89_partial_uri)
