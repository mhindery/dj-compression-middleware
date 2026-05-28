from collections.abc import Iterable
from zlib import DEFLATED, Z_DEFAULT_COMPRESSION, compress as zlib_compress, compressobj as zlib_compressobj


# The functions below are adapted from django.utils.text, with as only change the addition of a compresslevel argument,
# to allow for choosing the compression level.
# Django's built-in functions do not take a configurable compression level and use 6 hardcoded.


def compress_string(  # noqa: D103
    s: str | bytes,
    level: int = Z_DEFAULT_COMPRESSION,
) -> bytes:
    return zlib_compress(s, level=level)  # ty:ignore[invalid-argument-type]


def compress_sequence(  # noqa: D103
    sequence: Iterable[bytes],
    level: int = Z_DEFAULT_COMPRESSION,
) -> Iterable[bytes]:
    compressor = zlib_compressobj(level=level, method=DEFLATED)

    for item in sequence:
        yield compressor.compress(item)
    yield compressor.flush()
