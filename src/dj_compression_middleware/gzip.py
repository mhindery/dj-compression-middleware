import gzip
from gzip import GzipFile, compress as gzip_compress

from django.utils.text import StreamingBuffer, _get_random_filename  # noqa: PLC2701


# The functions below are adapted from django.utils.text, with as only change the addition of a compresslevel argument,
# to allow for choosing the compression level.
# Django's built-in functions do not take a configurable compression level and use 6 hardcoded.


def compress_string(s, compresslevel=6, max_random_bytes=None):  # noqa: D103
    compressed_data = gzip_compress(s, compresslevel=compresslevel, mtime=0)

    if not max_random_bytes:
        return compressed_data

    compressed_view = memoryview(compressed_data)
    header = bytearray(compressed_view[:10])
    header[3] = gzip.FNAME

    filename = _get_random_filename(max_random_bytes) + b"\x00"

    return bytes(header) + filename + compressed_view[10:]


def compress_sequence(sequence, compresslevel=6, max_random_bytes=None):  # noqa: D103
    buf = StreamingBuffer()
    filename = _get_random_filename(max_random_bytes) if max_random_bytes else None
    with GzipFile(filename=filename, mode="wb", compresslevel=compresslevel, fileobj=buf, mtime=0) as zfile:
        # Output headers...
        yield buf.read()
        for item in sequence:
            zfile.write(item)
            data = buf.read()
            if data:
                yield data
    yield buf.read()
