from collections.abc import Callable

import pytest
from algokit_utils import SigningAccount

from asa_metadata_registry import (
    AssetMetadata,
    flags,
)
from asa_metadata_registry._generated.asa_metadata_registry_client import (
    AsaMetadataRegistryClient,
)
from tests.helpers.utils import set_flag_and_verify


@pytest.mark.parametrize(
    "reversible_flag,check_fn",
    [
        (flags.REV_FLG_ARC20, lambda m: m.flags.reversible.arc20),
        (flags.REV_FLG_ARC62, lambda m: m.flags.reversible.arc62),
        (flags.REV_FLG_RESERVED_2, lambda m: m.flags.reversible.reserved_2),
        (flags.REV_FLG_RESERVED_3, lambda m: m.flags.reversible.reserved_3),
        (flags.REV_FLG_RESERVED_4, lambda m: m.flags.reversible.reserved_4),
        (flags.REV_FLG_RESERVED_5, lambda m: m.flags.reversible.reserved_5),
        (flags.REV_FLG_RESERVED_6, lambda m: m.flags.reversible.reserved_6),
        (flags.REV_FLG_RESERVED_7, lambda m: m.flags.reversible.reserved_7),
    ],
)
def test_set_and_clear_reversible_flags(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    mutable_short_metadata: AssetMetadata,
    reversible_flag: int,
    check_fn: Callable[[AssetMetadata], bool],
) -> None:
    # Verify initial state is False
    assert not check_fn(mutable_short_metadata)

    # Set flag to True and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        reversible_flag,
        check_fn,
        value=True,
    )

    # Set flag to False and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        mutable_short_metadata,
        reversible_flag,
        check_fn,
        value=False,
    )


# TODO: Test failing conditions
