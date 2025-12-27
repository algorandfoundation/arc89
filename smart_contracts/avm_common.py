from algopy import Application, Bytes, TemplateVar, UInt64, op, subroutine

from .constants import (
    ARC90_URI_APP_PATH,
    ARC90_URI_BOX_QUERY,
    ARC90_URI_SCHEME,
)
from .template_vars import ARC90_NETAUTH


@subroutine
def trimmed_itob(*, uint: UInt64, size: UInt64) -> Bytes:
    """
    Return exactly `size` rightmost bytes of the 8-byte big-endian itob(a).
    Size is assumed to be 1 (UInt8), 2 (UInt16), or 4 (UInt32) bytes.
    """
    start = UInt64(8) - size  # left-trim offset
    return op.extract(op.itob(uint), start, size)


@subroutine
def umin(a: UInt64, b: UInt64) -> UInt64:
    return a if a < b else b


@subroutine
def ceil_div(*, num: UInt64, den: UInt64) -> UInt64:
    # Assumes den >= 1
    return (num + (den - 1)) // den


@subroutine
def itoa(i: UInt64) -> Bytes:
    # ASCII digits (valid UTF-8)
    digits = Bytes(b"0123456789")
    acc = Bytes(b"")

    while i > 0:
        d = i % UInt64(10)
        acc = digits[d : d + UInt64(1)] + acc
        i //= UInt64(10)

    return acc or Bytes(b"0")


@subroutine
def arc90_box_query(app: Application, box_name: Bytes) -> Bytes:
    return (
        ARC90_URI_SCHEME
        + TemplateVar[Bytes](ARC90_NETAUTH)
        + ARC90_URI_APP_PATH
        + itoa(app.id)
        + ARC90_URI_BOX_QUERY
        + box_name
    )
