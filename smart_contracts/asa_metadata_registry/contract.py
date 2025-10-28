from algopy import Account, ARC4Contract, TemplateVar, Txn, arc4

from . import errors as err
from .template_vars import TRUSTED_DEPLOYER


class AsaMetadataRegistry(ARC4Contract):
    """
    Singleton Application providing ASA metadata via Algod API and AVM
    """

    @arc4.baremethod(create="require")
    def create(self) -> None:
        # Preconditions
        assert Txn.sender == TemplateVar[Account](
            TRUSTED_DEPLOYER
        ), err.UNTRUSTED_DEPLOYER
