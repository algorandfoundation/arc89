import math
from typing import get_args

from asa_metadata_registry import constants as const
from asa_metadata_registry.validation import Arc3PropertiesKey
from smart_contracts import constants as contract_const


def test_constants() -> None:
    assert const.MAX_ARG_SIZE == 4096
    assert const.HEADER_SIZE <= const.MAX_LOG_SIZE - const.ARC4_RETURN_PREFIX_SIZE
    assert const.MAX_METADATA_SIZE == const.MAX_BOX_SIZE - const.HEADER_SIZE == 32717
    assert const.MAX_PAGES == math.ceil(const.MAX_METADATA_SIZE / const.PAGE_SIZE)
    assert const.MAX_PAGES == 33
    assert const.MAX_PAGES <= 256

    assert contract_const.MAX_METADATA_SIZE == const.MAX_METADATA_SIZE
    assert contract_const.MAX_PAGES == const.MAX_PAGES
    assert contract_const.FIRST_PAYLOAD_MAX_SIZE == const.FIRST_PAYLOAD_MAX_SIZE
    assert contract_const.EXTRA_PAYLOAD_MAX_SIZE == const.EXTRA_PAYLOAD_MAX_SIZE
    assert contract_const.REPLACE_PAYLOAD_MAX_SIZE == const.REPLACE_PAYLOAD_MAX_SIZE

    assert const.FIRST_PAYLOAD_MAX_SIZE == 4094
    assert const.EXTRA_PAYLOAD_MAX_SIZE == 4094
    assert const.REPLACE_PAYLOAD_MAX_SIZE == 4094
    assert (
        const.ARC4_DYNAMIC_LENGTH_SIZE + const.FIRST_PAYLOAD_MAX_SIZE
        == const.MAX_ARG_SIZE
    )
    assert (
        const.ARC4_DYNAMIC_LENGTH_SIZE + const.EXTRA_PAYLOAD_MAX_SIZE
        == const.MAX_ARG_SIZE
    )
    assert (
        const.ARC4_DYNAMIC_LENGTH_SIZE + const.REPLACE_PAYLOAD_MAX_SIZE
        == const.MAX_ARG_SIZE
    )

    assert (
        const.ARC89_GET_METADATA_RETURN_FIXED_SIZE + const.PAGE_SIZE
        <= const.MAX_LOG_SIZE
    )

    print("ASA Metadata Registry Sizes:")
    print("HEADER_SIZE:\t\t\t", const.HEADER_SIZE)
    print("MAX_METADATA_SIZE:\t\t", const.MAX_METADATA_SIZE)
    print("MAX_PAGES:\t\t\t", const.MAX_PAGES)
    print("FIRST_PAYLOAD_MAX_SIZE:\t\t", const.FIRST_PAYLOAD_MAX_SIZE)
    print("EXTRA_PAYLOAD_MAX_SIZE:\t\t", const.EXTRA_PAYLOAD_MAX_SIZE)
    print("REPLACE_PAYLOAD_MAX_SIZE:\t", const.REPLACE_PAYLOAD_MAX_SIZE)

    # Ensure ARC3_PROPERTIES_KEYS and Arc3PropertiesKey stay in sync if new ARC keys are added
    assert const.ARC3_PROPERTIES_KEY_ARC20 in const.ARC3_PROPERTIES_KEYS
    assert const.ARC3_PROPERTIES_KEY_ARC62 in const.ARC3_PROPERTIES_KEYS
    assert set(const.ARC3_PROPERTIES_KEYS) == set(get_args(Arc3PropertiesKey))
