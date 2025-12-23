import math

from smart_contracts.asa_metadata_registry import constants as const


def test_constants() -> None:
    assert const.HEADER_SIZE <= const.MAX_LOG_SIZE - const.ARC4_RETURN_PREFIX_SIZE
    assert const.MAX_METADATA_SIZE <= const.MAX_BOX_SIZE - const.HEADER_SIZE
    assert const.MAX_PAGES == math.ceil(const.MAX_METADATA_SIZE / const.PAGE_SIZE)
    assert const.MAX_PAGES <= 256

    assert (
        const.ARC89_CREATE_METADATA_FIXED_SIZE + const.FIRST_PAYLOAD_MAX_SIZE
        <= const.MAX_ARG_SIZE
    )
    assert (
        const.ARC89_EXTRA_PAYLOAD_FIXED_SIZE + const.EXTRA_PAYLOAD_MAX_SIZE
        <= const.MAX_ARG_SIZE
    )
    assert (
        const.ARC89_REPLACE_METADATA_SLICE_FIXED_SIZE + const.REPLACE_PAYLOAD_MAX_SIZE
        <= const.MAX_ARG_SIZE
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
