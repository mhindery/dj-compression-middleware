import gzip
import sys
import zlib

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


def test_middleware_compress_streaming_response_brotli() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    sequence = [b"a" * 500, b"b" * 200, b"a" * 300]

    compression_middleware = CompressionMiddleware(
        lambda _: StreamingHttpResponse(
            sequence,
            headers={"Content-Type": "text/html; charset=UTF-8"},
        ),
    )
    response = compression_middleware(fake_request)

    decompressed_response: bytes = brotli.decompress(b"".join(response))
    assert decompressed_response == b"".join(sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "br"


def test_middleware_compress_streaming_unicode_response_brotli() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    sequence = ["a" * 500, "é" * 200, "a" * 300]

    compression_middleware = CompressionMiddleware(
        lambda _: StreamingHttpResponse(
            sequence,
            headers={"Content-Type": "text/html; charset=UTF-8"},
        ),
    )
    response = compression_middleware(fake_request)

    decompressed_response: bytes = brotli.decompress(b"".join(response))
    assert decompressed_response == b"".join(x.encode("utf-8") for x in sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "br"


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
