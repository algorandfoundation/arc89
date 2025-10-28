from algopy import Account, TemplateVar, Txn, arc4

from . import errors as err
from .interface import AsaMetadataRegistryInterface
from .template_vars import TRUSTED_DEPLOYER


class AsaMetadataRegistry(AsaMetadataRegistryInterface):
    """
    Singleton Application providing ASA metadata via Algod API and AVM
    """

    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Create the ASA Metadata Registry Application, restricted to the Trusted Deployer."""
        # Preconditions
        assert Txn.sender == TemplateVar[Account](
            TRUSTED_DEPLOYER
        ), err.UNTRUSTED_DEPLOYER
