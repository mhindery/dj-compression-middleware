# # partially based on tests in django and django-brotli

# import gzip
# import random
# import struct
# import sys
# from io import BytesIO
# from unittest import TestCase
import pytest
from django.middleware.gzip import compress_sequence as gzip_compress_stream, compress_string as gzip_compress

from dj_compression_middleware.br import brotli_compress, brotli_compress_stream

# import brotli
# if sys.version_info >= (3, 14):
#     # Python 3.14+ ships zstd in the standard library (PEP 784).
#     from compression import zstd
# else:
#     import zstandard as zstd
# from django.http import HttpResponse, StreamingHttpResponse
# from django.middleware.gzip import GZipMiddleware
# from django.test import RequestFactory, SimpleTestCase
from dj_compression_middleware.middleware import CompressionMiddleware
from dj_compression_middleware.zstd import zstd_compress, zstd_compress_stream


# from .utils import UTF8_LOREM_IPSUM_IN_CZECH


# int2byte = struct.Struct(">B").pack


# class FakeRequestAcceptsZstd:
#     META = {"HTTP_ACCEPT_ENCODING": "gzip, deflate, sdch, br, zstd"}


# class FakeRequestAcceptsBrotli:
#     META = {"HTTP_ACCEPT_ENCODING": "gzip, deflate, sdch, br"}


# class InvalidAcceptEcondingRequest:
#     META = {"HTTP_ACCEPT_ENCODING": "text/plain,*/*; charset=utf-8"}


# class FakeLegacyRequest:
#     META = {
#     }


# def gzip_decompress(gzipped_string):
#     with gzip.GzipFile(mode="rb", fileobj=BytesIO(gzipped_string)) as f:
#         return f.read()


# class FakeResponse:
#     streaming = False

#     def __init__(self, content, headers=None, streaming=None) -> None:
#         self.content = content.encode(encoding="utf-8")
#         self.headers = headers or {}

#         if streaming:
#             self.streaming = streaming

#     def has_header(self, header):
#         return header in self.headers

#     def get(self, key):
#         return self.headers.get(key, None)

#     def __getitem__(self, header):
#         return self.headers[header]

#     def __setitem__(self, header, value) -> None:
#         self.headers[header] = value


# class MiddlewareTestCase(TestCase):
#     def test_middleware_compress_response(self) -> None:
#         fake_request = FakeRequestAcceptsBrotli()
#         response_content = UTF8_LOREM_IPSUM_IN_CZECH
#         fake_response = FakeResponse(content=response_content)

#         compression_middleware = CompressionMiddleware(lambda: fake_response)
#         response = compression_middleware.process_response(fake_request, fake_response)

#         decompressed_response = brotli.decompress(response.content)  # type: bytes
#         assert response_content == decompressed_response.decode(encoding="utf-8")
#         assert response.get("Vary") == "Accept-Encoding"

#     def test_middleware_compress_response_zstd(self) -> None:
#         fake_request = FakeRequestAcceptsZstd()
#         response_content = UTF8_LOREM_IPSUM_IN_CZECH
#         fake_response = FakeResponse(content=response_content)

#         compression_middleware = CompressionMiddleware(lambda: fake_response)
#         response = compression_middleware.process_response(fake_request, fake_response)

#         cctx = zstd.ZstdDecompressor()
#         decompressed_response = cctx.decompress(response.content)  # type: bytes
#         assert response_content == decompressed_response.decode(encoding="utf-8")
#         assert response.get("Vary") == "Accept-Encoding"

#     def test_etag_is_updated_if_present(self) -> None:
#         fake_request = FakeRequestAcceptsBrotli()
#         response_content = UTF8_LOREM_IPSUM_IN_CZECH * 5
#         fake_etag_content = '"foo"'
#         fake_response = FakeResponse(content=response_content, headers={"ETag": fake_etag_content})

#         assert fake_response["ETag"] == fake_etag_content

#         compression_middleware = CompressionMiddleware(lambda: fake_response)
#         response = compression_middleware.process_response(fake_request, fake_response)

#         decompressed_response = brotli.decompress(response.content)  # type: bytes
#         assert response_content == decompressed_response.decode(encoding="utf-8")

#         # note: this is where we differ from django-brotli
#         # django-brotli's expectation:
#         # self.assertEqual(response["ETag"], '"foo;br\\"')  # noqa: ERA001
#         # Django's expectation:
#         assert response["ETag"] == 'W/"foo"'

#     def test_middleware_wont_compress_response_if_response_is_small(self) -> None:
#         fake_request = FakeRequestAcceptsBrotli()
#         response_content = "Hello World"

#         assert len(response_content) < 200  # a < b

#         fake_response = FakeResponse(content=response_content)

#         compression_middleware = CompressionMiddleware(lambda: fake_response)
#         response = compression_middleware.process_response(fake_request, fake_response)

#         assert response_content == response.content.decode(encoding="utf-8")
#         assert not response.has_header("Vary")
#         assert response.get("Content-Encoding") is None

#     def test_middleware_wont_compress_if_client_not_accept(self) -> None:
#         fake_request = FakeLegacyRequest()
#         response_content = UTF8_LOREM_IPSUM_IN_CZECH
#         fake_response = FakeResponse(content=response_content)

#         compression_middleware = CompressionMiddleware(lambda: fake_response)
#         response = compression_middleware.process_response(fake_request, fake_response)

#         django_gzip_middleware = GZipMiddleware(lambda: fake_response)
#         django_gzip_middleware.process_response(fake_request, fake_response)

#         assert response_content == response.content.decode(encoding="utf-8")
#         assert response.get("Vary") == "Accept-Encoding"
#         assert response.get("Content-Encoding") is None

#     def test_middleware_wont_compress_if_invalid_header(self) -> None:
#         """Test that the middleware doesn't crash if the client sends an invalid Accept-Encoding header."""
#         fake_request = InvalidAcceptEcondingRequest()
#         response_content = UTF8_LOREM_IPSUM_IN_CZECH
#         fake_response = FakeResponse(content=response_content)

#         compression_middleware = CompressionMiddleware(lambda: fake_response)
#         response = compression_middleware.process_response(fake_request, fake_response)

#         django_gzip_middleware = GZipMiddleware(lambda: fake_response)
#         gzip_response = django_gzip_middleware.process_response(fake_request, fake_response)

#         assert response_content == response.content.decode(encoding="utf-8")
#         assert gzip_response.content.decode(encoding="utf-8") == response.content.decode(encoding="utf-8")
#         assert response.get("Vary") == "Accept-Encoding"
#         assert response.get("Content-Encoding") is None

#     def test_middleware_wont_compress_if_response_is_already_compressed(self) -> None:
#         fake_request = FakeRequestAcceptsBrotli()
#         response_content = UTF8_LOREM_IPSUM_IN_CZECH
#         fake_response = FakeResponse(content=response_content)

#         compression_middleware = CompressionMiddleware(lambda: fake_response)
#         django_gzip_middleware = GZipMiddleware(lambda: fake_response)

#         gzip_response = django_gzip_middleware.process_response(fake_request, fake_response)
#         response = compression_middleware.process_response(fake_request, gzip_response)

#         assert response_content == gzip_decompress(response.content).decode(encoding="utf-8")
#         assert response.get("Vary") == "Accept-Encoding"

#     def test_content_encoding_parsing(self) -> None:
#         assert compressor("")[0] is None
#         assert compressor("gzip")[0] == "gzip"
#         assert compressor("br")[0] == "br"
#         assert compressor("gzip, br")[0] == "br"
#         assert compressor("br;q=1.0, gzip;q=0.8")[0] == "br"
#         assert compressor("br;q=0, gzip;q=0.8")[0] == "gzip"
#         assert compressor("bla;bla;gzip")[0] is None
#         assert compressor("text/plain,*/*; charset=utf-8")[0] is None  # PR #12
#         assert compressor("gzip;q==1")[0] == "gzip"  # questionable
#         assert compressor("br;gzip")[0] == "br"  # questionable
#         assert compressor("*")[0] == "zstd"


# class StreamingTest(SimpleTestCase):
#     """Tests streaming."""

#     short_string = b"This string is too short to be worth compressing."
#     compressible_string = b"a" * 500
#     incompressible_string = b"".join(
#         int2byte(random.randint(0, 255)) for _ in range(500)
#     )
#     sequence = [b"a" * 500, b"b" * 200, b"a" * 300]
#     sequence_unicode = ["a" * 500, "é" * 200, "a" * 300]
#     request_factory = RequestFactory()

#     def setUp(self) -> None:
#         self.req = self.request_factory.get("/")
#         self.req.META["HTTP_ACCEPT_ENCODING"] = "gzip, deflate, br"
#         self.req.META[
#             "HTTP_USER_AGENT"
#         ] = "Mozilla/5.0 (Windows NT 5.1; rv:9.0.1) Gecko/20100101 Firefox/9.0.1"
#         self.resp = HttpResponse()
#         self.resp.status_code = 200
#         self.resp.content = self.compressible_string
#         self.resp["Content-Type"] = "text/html; charset=UTF-8"
#         self.stream_resp = StreamingHttpResponse(self.sequence)
#         self.stream_resp["Content-Type"] = "text/html; charset=UTF-8"
#         self.stream_resp_unicode = StreamingHttpResponse(self.sequence_unicode)
#         self.stream_resp_unicode["Content-Type"] = "text/html; charset=UTF-8"

#     def test_compress_streaming_response(self) -> None:
#         """Compression is performed on responses with streaming content."""
#         r = CompressionMiddleware(lambda: self.stream_resp).process_response(self.req, self.stream_resp)
#         assert brotli.decompress(b"".join(r)) == b"".join(self.sequence)
#         assert r.get("Content-Encoding") == "br"
#         assert not r.has_header("Content-Length")
#         assert r.get("Vary") == "Accept-Encoding"

#     def test_compress_streaming_response_unicode(self) -> None:
#         """Compression is performed on responses with streaming Unicode content."""
#         r = CompressionMiddleware(lambda: self.stream_resp_unicode).process_response(self.req, self.stream_resp_unicode)
#         assert brotli.decompress(b"".join(r)) == b"".join(x.encode("utf-8") for x in self.sequence_unicode)
#         assert r.get("Content-Encoding") == "br"
#         assert not r.has_header("Content-Length")
#         assert r.get("Vary") == "Accept-Encoding"


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
