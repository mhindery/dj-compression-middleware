import logging
from collections.abc import Callable, Iterable
from functools import partial
from inspect import iscoroutinefunction, markcoroutinefunction

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.utils.cache import patch_vary_headers

from .br import brotli_compress, brotli_compress_stream
from .gzip import compress_sequence as gzip_compress_stream, compress_string as gzip_compress
from .zlib import compress_sequence as zlib_compress_stream, compress_string as zlib_compress
from .zstd import zstd_compress, zstd_compress_stream


logger = logging.getLogger(__name__)


class CompressionMiddleware:
    """Middleware to compress the response content if the browser allows gzip, brotli or zstd compression."""

    sync_capable = True
    async_capable = True

    # For gzip, we add some random bytes to the end of the content to make it more difficult for attackers to use BREACH attacks to extract information from compressed responses.  # noqa: E501
    # This is a common mitigation strategy for such attacks. The number of random bytes added can be adjusted based on the desired level of security and performance trade-offs.  # noqa: E501
    # A value of 100 is often considered a reasonable choice, as it provides a significant amount of randomness without adding too much overhead to the response size.  # noqa: E501
    MAX_RANDOM_BYTES = 100

    # If a response is less than 500 bytes, it is not worth compressing.
    # It would fit uncompressed in a single MTU, and the overhead of compression would likely outweigh any benefits.
    MIN_LEN = 500

    # The minimum gain required to justify compression.
    # If the compressed content is not at least this many bytes smaller than the original content, then the original content will be returned uncompressed.  # noqa: E501
    # This is to avoid the overhead of compression when it doesn't provide a significant reduction in size.
    # The overhead if the addition of the Content-Encoding header is 24 bytes + the decompression effort on the client.
    MIN_IMPROVEMENT = 100

    # Tweak compression settings
    ZSTD_LEVEL = 7
    BROTLI_QUALITY = 4
    GZIP_COMPRESSLEVEL = 6
    ZLIB_COMPRESSLEVEL = -1

    COMPRESSORS: tuple[tuple[str, Callable[[bytes], bytes], Callable[[Iterable[bytes]], Iterable[bytes]]], ...]

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse | StreamingHttpResponse]) -> None:  # noqa: D107
        self.get_response = get_response

        self.is_async = iscoroutinefunction(get_response)
        if self.is_async:
            markcoroutinefunction(self)

        # supported encodings in order of preference
        # (encoding, bulk_compressor, stream_compressor)  # noqa: ERA001
        self.COMPRESSORS = (
            (
                "zstd",
                partial(
                    zstd_compress,
                    level=self.ZSTD_LEVEL,
                ),
                partial(
                    zstd_compress_stream,
                    level=self.ZSTD_LEVEL,
                ),
            ),
            (
                "br",
                partial(
                    brotli_compress,
                    quality=self.BROTLI_QUALITY,
                ),
                partial(
                    brotli_compress_stream,
                    quality=self.BROTLI_QUALITY,
                ),
            ),
            (
                "gzip",
                partial(
                    gzip_compress,
                    compresslevel=self.GZIP_COMPRESSLEVEL,
                    max_random_bytes=self.MAX_RANDOM_BYTES,
                ),
                partial(
                    gzip_compress_stream,
                    compresslevel=self.GZIP_COMPRESSLEVEL,
                    max_random_bytes=self.MAX_RANDOM_BYTES,
                ),
            ),
            (
                "deflate",
                partial(
                    zlib_compress,
                    level=self.ZLIB_COMPRESSLEVEL,
                ),
                partial(
                    zlib_compress_stream,
                    level=self.ZLIB_COMPRESSLEVEL,
                ),
            ),
        )

    def __call__(self, request: HttpRequest) -> HttpResponse | StreamingHttpResponse:  # noqa: D102
        if self.is_async:
            return self.__acall__(request)  # ty: ignore[invalid-return-type]

        response = self.get_response(request)
        return self.process_response(request, response)

    async def __acall__(self, request: HttpRequest) -> HttpResponse | StreamingHttpResponse:  # noqa: D105, PLW3201
        response = await self.get_response(request)  # ty:ignore[invalid-await]
        return self.process_response(request, response)

    def process_response(  # noqa: C901
        self,
        request: HttpRequest,
        response: HttpResponse | StreamingHttpResponse,
    ) -> HttpResponse | StreamingHttpResponse:
        """Compress the response content if the client and response allows it and if it's worth compressing."""
        if getattr(response, "no_compress", False) or getattr(self.get_response, "no_compress", False):
            return response

        # It's not worth attempting to compress really short responses.
        if not response.streaming and len(response.content) < self.MIN_LEN:
            return response

        # Avoid compression if we've already got a content-encoding.
        if response.has_header("Content-Encoding"):
            return response

        patch_vary_headers(response, ("Accept-Encoding",))

        encoding, compress_string, compress_sequence = self.get_supported_compressor(
            request.headers.get("Accept-Encoding", ""),
        )
        if encoding is None:
            # Client didn't indicate support for anything we can do, so just return the original response.
            return response

        if response.streaming:
            if getattr(response, "is_async", False):
                # forward args explicitly to capture fixed references in case they are set again later.
                async def compress_wrapper(streaming_content: Iterable[bytes]) -> Iterable[bytes]:  # ty:ignore[invalid-return-type]
                    async for chunk in streaming_content:  # ty:ignore[not-iterable]
                        yield compress_string(chunk)  # ty:ignore[call-non-callable]

                response.streaming_content = compress_wrapper(response.streaming_content)  # ty:ignore[invalid-assignment, unresolved-attribute]
            else:
                response.streaming_content = compress_sequence(response.streaming_content)  # ty:ignore[call-non-callable, invalid-assignment, unresolved-attribute]

            # Delete the `Content-Length` header for streaming content, because
            # we won't know the compressed size until we stream it.
            del response.headers["Content-Length"]
        else:
            # Return the compressed content only if it's actually shorter.
            compressed_content = compress_string(response.content)  # ty:ignore[call-non-callable]
            if len(response.content) - len(compressed_content) < self.MIN_IMPROVEMENT:
                return response
            response.content = compressed_content  # ty:ignore[invalid-assignment]
            response.headers["Content-Length"] = str(len(response.content))

        # If there is a strong ETag, make it weak to fulfill the requirements
        # of RFC 9110 Section 8.8.1 while also allowing conditional request
        # matches on ETags.
        etag = response.headers.get("ETag")
        if etag and etag.startswith('"'):
            response.headers["ETag"] = "W/" + etag

        response.headers["Content-Encoding"] = encoding

        return response

    def get_supported_compressor(
        self,
        accept_encoding_header: str,
    ) -> (
        tuple[str, Callable[[bytes], bytes] | None, Callable[[Iterable[bytes]], Iterable[bytes]] | None]
        | tuple[None, None, None]
    ):
        """Determine the best compressor to use based on the Accept-Encoding incoming request header.

        Returns a tuple of (encoding_name, bulk_compressor, stream_compressor).
        Returns (None, None, None) if no suitable compressor is found.
        """
        # If everything is supported, just take the first one we prefer.
        if accept_encoding_header == "*":
            return self.COMPRESSORS[0]

        # We don't want to process extremely long headers. It might be an attack:
        accept_encoding_header = accept_encoding_header[:200]
        supported_client_encodings = {self.extract_encoding_name(e) for e in accept_encoding_header.split(",")}

        for encoding, compress_string, compress_sequence in self.COMPRESSORS:
            if encoding in supported_client_encodings:
                return encoding, compress_string, compress_sequence

        return (None, None, None)

    def extract_encoding_name(self, specifier: str) -> str | None:
        """Return the encoding name from a string like 'br;q=0.5' (which would return 'br).

        If the quality level is 0, return None to indicate that the encoding is not acceptable.

        If the extracted encoding name is unrecognized, return None to indicate that the encoding is not acceptable.
        """
        # We won't break if the ordering is specified with q=, but we ignore it.
        # Only a quality level of 0 is honoured -- in such a case we handle it as
        # if the encoding wasn't specified at all.
        if ";" in specifier:
            specifier, quality_level = specifier.split(";", 1)
            if "=" in quality_level:
                _, quality_level = quality_level.split("=", 1)
                try:
                    if float(quality_level) == 0.0:  # noqa: RUF069
                        return None
                except ValueError:
                    pass
        specifier = specifier.strip()

        if specifier not in [encoding for encoding, _, _ in self.COMPRESSORS]:
            logger.warning("Unrecognized encoding: %s", specifier, extra={"specifier": specifier})
            return None

        return specifier
