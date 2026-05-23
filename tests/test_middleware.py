import gzip
import sys

import brotli
import pytest
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.middleware.gzip import compress_sequence as gzip_compress_stream, compress_string as gzip_compress

from dj_compression_middleware.br import brotli_compress, brotli_compress_stream


if sys.version_info >= (3, 14):
    # Python 3.14+ ships zstd in the standard library (PEP 784).
    from compression import zstd
else:
    import zstandard as zstd


from dj_compression_middleware.middleware import CompressionMiddleware
from dj_compression_middleware.zstd import zstd_compress, zstd_compress_stream

from .utils import UTF8_LOREM_IPSUM_IN_CZECH


# class MiddlewareTestCase(TestCase):
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

    compression_middleware = CompressionMiddleware(lambda _: HttpResponse(response_content, headers={"Content-Encoding": "gzip"}))
    response = compression_middleware(fake_request)

    assert response.content == response_content
    assert response.get("Vary") is None
    assert response.get("Content-Encoding") == "gzip"


def test_middleware_compress_streaming_response_brotli() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    sequence = [b"a" * 500, b"b" * 200, b"a" * 300]

    compression_middleware = CompressionMiddleware(lambda _: StreamingHttpResponse(sequence, headers={"Content-Type": "text/html; charset=UTF-8"}))
    response = compression_middleware(fake_request)

    decompressed_response: bytes = brotli.decompress(b"".join(response))
    assert decompressed_response == b"".join(sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "br"


def test_middleware_compress_streaming_unicode_response_brotli() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    sequence = ["a" * 500, "é" * 200, "a" * 300]

    compression_middleware = CompressionMiddleware(lambda _: StreamingHttpResponse(sequence, headers={"Content-Type": "text/html; charset=UTF-8"}))
    response = compression_middleware(fake_request)

    decompressed_response: bytes = brotli.decompress(b"".join(response))
    assert decompressed_response == b"".join(x.encode("utf-8") for x in sequence)
    assert response.get("Vary") == "Accept-Encoding"
    assert response.get("Content-Encoding") == "br"


@pytest.mark.parametrize(
    ("specifier", "expected"),
    [("", None), ("br", "br"), ("br;q=1.0", "br"), ("br;q=0.0", None), ("gzip", "gzip"), ("gzip;q=1.0", "gzip"), ("gzip;q=0.0", None), ("zstd", "zstd"), ("zstd;q=1.0", "zstd"), ("zstd;q=0.0", None), ("random", None), ("*", None)],
)
def test_extract_encoding_name(specifier, expected):
    extracted_encoding = CompressionMiddleware.extract_encoding_name(specifier)
    assert extracted_encoding == expected


@pytest.mark.parametrize(
    ("accept_encoding_header", "expected"),
    [
        ("", (None, None, None)),
        ("gzip", ("gzip", gzip_compress, gzip_compress_stream)),
        ("br", ("br", brotli_compress, brotli_compress_stream)),
        ("zstd", ("zstd", zstd_compress, zstd_compress_stream)),
        ("gzip, br", ("br", brotli_compress, brotli_compress_stream)),
        ("br;q=1.0, gzip;q=0.8", ("br", brotli_compress, brotli_compress_stream)),
        ("br;q=0, gzip;q=0.8", ("gzip", gzip_compress, gzip_compress_stream)),
        ("br;q=0, gzip;q=0", (None, None, None)),
        ("bla;bla;gzip", (None, None, None)),
        ("text/plain,*/*; charset=utf-8", (None, None, None)),
        ("gzip;q==1", ("gzip", gzip_compress, gzip_compress_stream)),
        ("br;gzip", ("br", brotli_compress, brotli_compress_stream)),
        ("*", ("zstd", zstd_compress, zstd_compress_stream)),
    ],
)
def test_get_supported_compressor(accept_encoding_header, expected):
    result = CompressionMiddleware.get_supported_compressor(accept_encoding_header)
    assert result == expected
