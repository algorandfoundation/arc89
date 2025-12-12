import math

from smart_contracts.asa_metadata_registry import constants as const


def test_constants() -> None:
    assert (
        const.METADATA_HEADER_SIZE <= const.MAX_LOG_SIZE - const.ARC4_RETURN_PREFIX_SIZE
    )
    assert const.MAX_METADATA_SIZE <= const.MAX_BOX_SIZE - const.METADATA_HEADER_SIZE
    assert const.MAX_PAGES == math.ceil(const.MAX_METADATA_SIZE / const.PAGE_SIZE)
    assert const.MAX_PAGES <= 256
