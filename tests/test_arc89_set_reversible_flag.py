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
        (flags.FLG_ARC20, lambda m: m.is_arc20),
        (flags.FLG_ARC62, lambda m: m.is_arc62),
        (flags.FLG_RESERVED_2, lambda m: bool(m.flags & bitmasks.MASK_RESERVED_2)),
        (flags.FLG_RESERVED_3, lambda m: bool(m.flags & bitmasks.MASK_RESERVED_3)),
    ],
)
def test_set_and_clear_reversible_flags(
    asset_manager: SigningAccount,
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    uploaded_short_metadata: AssetMetadata,
    flag: int,
    check_fn: Callable[[AssetMetadata], bool],
) -> None:
    asset_id = uploaded_short_metadata.asset_id

    # Verify initial state is False
    assert not check_fn(uploaded_short_metadata)

    # Set flag to True and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        asset_id,
        flag,
        check_fn,
        value=True,
    )

    # Set flag to False and verify
    set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        asset_id,
        flag,
        check_fn,
        value=False,
    )


# TODO: Test failing conditions
