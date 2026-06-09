import gzip
import sys
import zlib
from inspect import iscoroutinefunction

import brotli
import pytest
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse


if sys.version_info >= (3, 14):
    # Python 3.14+ ships zstd in the standard library (PEP 784).
    from compression import zstd
else:
    import zstandard as zstd  # ty:ignore[unresolved-import, unused-ignore-comment]


from dj_compression_middleware.gzip import compress_string as gzip_compress_string
from dj_compression_middleware.middleware import CompressionMiddleware
from dj_compression_middleware.zlib import compress_string as zlib_compress_string
from dj_compression_middleware.zstd import zstd_compress

from .utils import UTF8_LOREM_IPSUM_IN_CZECH


async def async_get_response_empty(request: HttpRequest) -> HttpResponse:  # noqa: ARG001, RUF029
    return HttpResponse("hello world")


def get_response_empty(request: HttpRequest) -> HttpResponse:  # noqa: ARG001
    return HttpResponse("hello world")


def test_async_get_response_marks_coroutine_function() -> None:
    """Depending on the nature of the get_response, the middleware instance is marked as a coroutine function.

    In case of an async get_response, the handler runs it natively, rather than adapting it with sync_to_async.
    A sync get_response leaves it unmarked, so it is treated as a regular function.
    """
    assert iscoroutinefunction(CompressionMiddleware(async_get_response_empty))
    assert not iscoroutinefunction(CompressionMiddleware(get_response_empty))


@pytest.mark.asyncio
async def test_sync_and_async_get_response_work() -> None:
    """The middleware processes both sync and async get_response functions correctly."""
    fake_request = HttpRequest()

    mdlw_async = CompressionMiddleware(async_get_response_empty)
    async_response = await mdlw_async(fake_request)
    assert async_response.content == b"hello world"

    mdlw_sync = CompressionMiddleware(get_response_empty)
    sync_response = mdlw_sync(fake_request)
    assert sync_response.content == b"hello world"


def test_middleware_compress_response_brotli() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    decompressed_response: bytes = brotli.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"


def test_middleware_compress_response_zstd() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "zstd"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    decompressed_response: bytes = zstd.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "zstd"


def test_middleware_compress_response_gzip() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "gzip"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    decompressed_response: bytes = gzip.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "gzip"


def test_middleware_compress_response_zlib() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "deflate"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    decompressed_response: bytes = zlib.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "deflate"


def test_middleware_etag_is_updated_if_present() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content, headers={"ETag": '"foo"'}))
    response = compression_middleware(fake_request)

    assert response["ETag"] == 'W/"foo"'


def test_middleware_wont_compress_response_if_response_is_small() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    response_content = "Hello World"

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    assert response.content.decode(encoding="utf-8") == response_content
    assert response.get("Vary") is None
    assert response.get("Content-Encoding") is None


def test_middleware_wont_compress_response_if_client_does_not_accept_encoding() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "identity"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    assert response.content.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") is None


def test_middleware_wont_compress_response_if_client_sends_invalid_accept_encoding() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "text/plain,*/*; charset=utf-8"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    assert response.content.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") is None


def test_middleware_wont_compress_response_if_it_was_already_compressed() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    response_content = gzip.compress(UTF8_LOREM_IPSUM_IN_CZECH.encode(encoding="utf-8"))

    compression_middleware = CompressionMiddleware(
        lambda _: HttpResponse(
            response_content,
            headers={"Content-Encoding": "gzip"},
        ),
    )
    response = compression_middleware(fake_request)

    assert response.content == response_content
    assert response.get("Vary") is None
    assert response.get("Content-Encoding") == "gzip"


@pytest.mark.parametrize(
    ("sequence"),
    [
        [b"a" * 500, b"b" * 200, b"a" * 300],
        [b"a" * 500, b"\xc3\xa9" * 200, b"a" * 300],
    ],
)
def test_middleware_compress_streaming_response_brotli(sequence: list[bytes]) -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"

    def stream():  # noqa: ANN202
        yield from sequence

    compression_middleware = CompressionMiddleware(
        lambda _: StreamingHttpResponse(
            stream(),
            headers={"Content-Type": "text/html; charset=UTF-8"},
        ),
    )
    response = compression_middleware(fake_request)

    decompressed_response: bytes = brotli.decompress(b"".join(response))
    assert decompressed_response == b"".join(sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "br"


@pytest.mark.parametrize(
    ("sequence"),
    [
        [b"a" * 500, b"b" * 200, b"a" * 300],
        [b"a" * 500, b"\xc3\xa9" * 200, b"a" * 300],
    ],
)
def test_middleware_compress_streaming_response_gzip(sequence: list[bytes]) -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "gzip"

    def stream():  # noqa: ANN202
        yield from sequence

    compression_middleware = CompressionMiddleware(
        lambda _: StreamingHttpResponse(
            stream(),
            headers={"Content-Type": "text/html; charset=UTF-8"},
        ),
    )
    response = compression_middleware(fake_request)

    decompressed_response: bytes = gzip.decompress(b"".join(response))
    assert decompressed_response == b"".join(sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "gzip"


@pytest.mark.parametrize(
    ("sequence"),
    [
        [b"a" * 500, b"b" * 200, b"a" * 300],
        [b"a" * 500, b"\xc3\xa9" * 200, b"a" * 300],
    ],
)
def test_middleware_compress_streaming_response_zlib(sequence: list[bytes]) -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "deflate"

    def stream():  # noqa: ANN202
        yield from sequence

    compression_middleware = CompressionMiddleware(
        lambda _: StreamingHttpResponse(
            stream(),
            headers={"Content-Type": "text/html; charset=UTF-8"},
        ),
    )
    response = compression_middleware(fake_request)

    decompressed_response: bytes = zlib.decompress(b"".join(response))
    assert decompressed_response == b"".join(sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "deflate"


@pytest.mark.parametrize(
    ("sequence"),
    [
        [b"a" * 500, b"b" * 200, b"a" * 300],
        [b"a" * 500, b"\xc3\xa9" * 200, b"a" * 300],
    ],
)
def test_middleware_compress_streaming_response_zstd(sequence: list[bytes]) -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "zstd"

    def stream():  # noqa: ANN202
        yield from sequence

    compression_middleware = CompressionMiddleware(
        lambda _: StreamingHttpResponse(
            stream(),
            headers={"Content-Type": "text/html; charset=UTF-8"},
        ),
    )
    response = compression_middleware(fake_request)

    decompressed_response: bytes = zstd.decompress(b"".join(response), 1200)
    assert decompressed_response == b"".join(sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "zstd"


@pytest.mark.parametrize(
    ("specifier", "expected"),
    [
        ("", None),
        ("br", "br"),
        ("br;q=1.0", "br"),
        ("br;q=0.0", None),
        ("deflate", "deflate"),
        ("gzip", "gzip"),
        ("gzip;q=1.0", "gzip"),
        ("gzip;q=0.0", None),
        ("zstd", "zstd"),
        ("zstd;q=1.0", "zstd"),
        ("zstd;q=0.0", None),
        ("random", None),
        ("*", None),
    ],
)
def test_extract_encoding_name(specifier: str, expected: str | None) -> None:
    extracted_encoding = CompressionMiddleware(lambda _: None).extract_encoding_name(specifier)  # ty:ignore[invalid-argument-type]
    assert extracted_encoding == expected


@pytest.mark.parametrize(
    ("accept_encoding_header", "expected"),
    [
        ("", None),
        ("gzip", "gzip"),
        ("br", "br"),
        ("zstd", "zstd"),
        ("deflate", "deflate"),
        ("gzip, br", "br"),
        ("gzip, deflate", "gzip"),
        ("deflate, gzip", "gzip"),
        ("br;q=1.0, gzip;q=0.8", "br"),
        ("br;q=0, gzip;q=0.8", "gzip"),
        ("br;q=0, gzip;q=0", None),
        ("bla;bla;gzip", None),
        ("text/plain,*/*; charset=utf-8", None),
        ("gzip;q==1", "gzip"),
        ("br;gzip", "br"),
        ("*", "zstd"),
    ],
)
def test_get_supported_compressor(accept_encoding_header: str, expected: str | None) -> None:
    result = CompressionMiddleware(lambda _: None).get_supported_compressor(accept_encoding_header)  # ty:ignore[invalid-argument-type]
    assert result[0] == expected


def test_middleware_compress_response_zstd_custom_compression_level() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "zstd"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    class CustomCompressionMiddleware(CompressionMiddleware):
        ZSTD_LEVEL = 1

    compression_middleware = CustomCompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    compressed_data = zstd_compress(response_content.encode("utf-8"), level=1)

    assert response.content == compressed_data

    decompressed_response: bytes = zstd.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "zstd"


def test_middleware_compress_response_brotli_custom_compression_level() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    class CustomCompressionMiddleware(CompressionMiddleware):
        BROTLI_QUALITY = 11

    compression_middleware = CustomCompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    compressed_data = brotli.compress(response_content.encode("utf-8"), quality=11)

    assert response.content == compressed_data

    decompressed_response: bytes = brotli.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "br"


def test_middleware_compress_response_gzip_custom_compression_level() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "gzip"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    class CustomCompressionMiddleware(CompressionMiddleware):
        GZIP_COMPRESSLEVEL = 9
        MAX_RANDOM_BYTES = 0  # so we can test deterministic output for gzip

    compression_middleware = CustomCompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    compressed_data = gzip_compress_string(
        response_content.encode("utf-8"),
        compresslevel=9,
        max_random_bytes=CustomCompressionMiddleware.MAX_RANDOM_BYTES,
    )

    assert response.content == compressed_data

    decompressed_response: bytes = gzip.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "gzip"


def test_middleware_compress_response_zlib_custom_compression_level() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "deflate"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    class CustomCompressionMiddleware(CompressionMiddleware):
        ZLIB_COMPRESSLEVEL = 9

    compression_middleware = CustomCompressionMiddleware(lambda _: HttpResponse(response_content))
    response = compression_middleware(fake_request)

    compressed_data = zlib_compress_string(
        response_content.encode("utf-8"),
        level=9,
    )

    assert response.content == compressed_data

    decompressed_response: bytes = zlib.decompress(response.content)
    assert decompressed_response.decode(encoding="utf-8") == response_content
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "deflate"
