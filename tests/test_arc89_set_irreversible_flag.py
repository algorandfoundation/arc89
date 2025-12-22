from collections.abc import Callable

import pytest
from algokit_utils import SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import flags
from tests.helpers import bitmasks
from tests.helpers.factories import AssetMetadata
from tests.helpers.utils import set_flag_and_verify


@pytest.mark.parametrize(
    "flag,check_fn",
    [
        (flags.FLG_RESERVED_6, lambda m: bool(m.flags & bitmasks.MASK_RESERVED_6)),
        (flags.FLG_IMMUTABLE, lambda m: m.is_immutable),
    ],
)
def test_set_irreversible_flags(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    flag: int,
    check_fn: Callable[[AssetMetadata], bool],
) -> None:
    # Verify initial state is False
    assert not check_fn(mutable_short_metadata)

    # Set flag to True and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        flag,
        check_fn,
        reversible=False,
    )


# TODO: Test failing conditions
