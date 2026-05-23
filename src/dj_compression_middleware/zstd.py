#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

__all__ = ["zstd_compress", "zstd_compress_stream"]


import sys


DEFAULT_LEVEL = 7

# Python 3.14+ ships zstd in the standard library (PEP 784); older versions
# need the third-party `zstandard` package.
_HAS_STDLIB_ZSTD = sys.version_info >= (3, 14)

if _HAS_STDLIB_ZSTD:
    from compression.zstd import ZstdCompressor, compress
else:
    import zstandard as zstd  # ty:ignore[unresolved-import, unused-ignore-comment]
    from django.utils.text import StreamingBuffer


def zstd_compress(content, level=DEFAULT_LEVEL):  # noqa: D103
    if _HAS_STDLIB_ZSTD:
        return compress(content, level=level)

    return zstd.ZstdCompressor(level=level).compress(content)


def zstd_compress_stream(sequence, level=DEFAULT_LEVEL):  # noqa: D103
    if _HAS_STDLIB_ZSTD:
        compressor = ZstdCompressor(level=level)
        for item in sequence:
            out = compressor.compress(item)
            if out:
                yield out
        out = compressor.flush()
        if out:
            yield out
        return

    buf = StreamingBuffer()
    cctx = zstd.ZstdCompressor(level=level)
    with cctx.stream_writer(buf, write_return_read=False) as compressor:
        yield buf.read()
        for item in sequence:
            if compressor.write(item):
                yield buf.read()
        compressor.flush(zstd.FLUSH_FRAME)
        yield buf.read()
