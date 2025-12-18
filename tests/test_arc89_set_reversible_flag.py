from collections.abc import Callable

import pytest
from algokit_utils import CommonAppCallParams, SigningAccount

from smart_contracts.artifacts.asa_metadata_registry.asa_metadata_registry_client import (
    Arc89SetReversibleFlagArgs,
    AsaMetadataRegistryClient,
)
from smart_contracts.asa_metadata_registry import flags
from tests.helpers import bitmasks
from tests.helpers.factories import AssetMetadata


def _set_flag_and_verify(
    asa_metadata_registry_client: AsaMetadataRegistryClient,
    asset_manager: SigningAccount,
    asset_id: int,
    flag: int,
    check_fn: Callable[[AssetMetadata], bool],
    *,
    value: bool,
) -> None:
    asa_metadata_registry_client.send.arc89_set_reversible_flag(
        args=Arc89SetReversibleFlagArgs(
            asset_id=asset_id,
            flag=flag,
            value=value,
        ),
        params=CommonAppCallParams(sender=asset_manager.address),
    )
    post_set = AssetMetadata.from_box_value(
        asset_id,
        asa_metadata_registry_client.state.box.asset_metadata.get_value(asset_id),
    )
    assert check_fn(post_set) == value


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
    _set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        asset_id,
        flag,
        check_fn,
        value=True,
    )

    # Set flag to False and verify
    _set_flag_and_verify(
        asa_metadata_registry_client,
        asset_manager,
        asset_id,
        flag,
        check_fn,
        value=False,
    )


# TODO: Test failing conditions
