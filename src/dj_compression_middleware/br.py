from collections.abc import Iterable

from brotli import Compressor, compress


DEFAULT_LEVEL = 4


def brotli_compress(content: bytes, quality: int = DEFAULT_LEVEL) -> bytes:  # noqa: D103
    return compress(content, quality=quality)


def brotli_compress_stream(sequence: Iterable[bytes], quality: int = DEFAULT_LEVEL) -> Iterable[bytes]:  # noqa: D103
    yield b""

    compressor = Compressor(quality=quality)
    try:
        # Brotli bindings
        process = compressor.process
    except AttributeError:
        # brotlipy
        process = compressor.compress

    for item in sequence:
        out = process(item)
        if out:
            yield out
    out = compressor.finish()
    if out:
        yield out
