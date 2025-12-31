from collections.abc import Callable

import pytest
from algokit_utils import SigningAccount

from src import bitmasks, flags
from src.generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from tests.helpers.factories import AssetMetadata
from tests.helpers.utils import set_flag_and_verify


@pytest.mark.parametrize(
    "irreversible_flag,check_fn",
    [
        (
            flags.IRR_FLG_RESERVED_2,
            lambda m: bool(m.irreversible_flags & bitmasks.MASK_IRR_RESERVED_2),
        ),
        (
            flags.IRR_FLG_RESERVED_3,
            lambda m: bool(m.irreversible_flags & bitmasks.MASK_IRR_RESERVED_3),
        ),
        (
            flags.IRR_FLG_RESERVED_4,
            lambda m: bool(m.irreversible_flags & bitmasks.MASK_IRR_RESERVED_4),
        ),
        (
            flags.IRR_FLG_RESERVED_5,
            lambda m: bool(m.irreversible_flags & bitmasks.MASK_IRR_RESERVED_5),
        ),
        (
            flags.IRR_FLG_RESERVED_6,
            lambda m: bool(m.irreversible_flags & bitmasks.MASK_IRR_RESERVED_6),
        ),
    ],
)
def test_set_irreversible_flags(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    irreversible_flag: int,
    check_fn: Callable[[AssetMetadata], bool],
) -> None:
    # Verify initial state is False
    assert not check_fn(mutable_short_metadata)

    # Set flag to True and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        irreversible_flag,
        check_fn,
        reversible=False,
    )


# TODO: Test failing conditions
