__all__ = ["CompressionMiddleware"]


from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.middleware.gzip import compress_sequence as gzip_compress_stream, compress_string as gzip_compress
from django.utils.cache import patch_vary_headers

from .br import brotli_compress, brotli_compress_stream
from .zstd import zstd_compress, zstd_compress_stream


# supported encodings in order of preference
# (encoding, bulk_compressor, stream_compressor)  # noqa: ERA001
compressors = (
    ("zstd", zstd_compress, zstd_compress_stream),
    ("br", brotli_compress, brotli_compress_stream),
    ("gzip", gzip_compress, gzip_compress_stream),
)


def extract_encoding_name(s):
    """Return the encoding name from a string like 'br;q=0.5'.

    If the quality level is 0, return None to indicate that the encoding is not acceptable.
    """
    # We won't break if the ordering is specified with q=, but we ignore it.
    # Only a quality level of 0 is honoured -- in such a case we handle it as
    # if the encoding wasn't specified at all.
    if ";" in s:
        s, q = s.split(";", 1)
        if "=" in q:
            _, q = q.split("=", 1)
            try:
                q = float(q)
                if q == 0.0:  # noqa: RUF069
                    return None
            except ValueError:
                pass
    return s.strip()


class CompressionMiddleware:
    """Middleware to compress the response content if the browser allows gzip, brotli or zstd compression."""

    MAX_RANDOM_BYTES = 100

    # Minimum response length before we'll consider compression. Small responses
    # won't necessarily be smaller after compression, and we want to save at least
    # enough to make the time expended worthwhile. Since MTUs around 1500 are
    # common, and HTTP headers are often more than 500 bytes (more so if there
    # are cookies), we guess that responses smaller than 500 bytes is likely to fit
    # in the MTU (or not) mostly due to other factors, not compression.
    MIN_LEN = 500

    # The compression has to reduce the length, otherwise we're just fooling
    # around. Since we'll have to add the Content-Encoding header, we need to
    # make that addition worthwhile, too. So the compressed response must be
    # smaller by some margin. This value should be at least 24 which is
    # len("Content-Encoding: gzip\r\n"), but a bigger value could reflect that a
    # non-trivial improvement in transfer time is required to make up for the time
    # required for decompression. An improvement of a few bytes is unlikely to
    # actually reduce the network communication in terms of MTUs.
    MIN_IMPROVEMENT = 100

    def __init__(self, get_response):  # noqa: D107
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:  # noqa: C901, D102
        response = self.get_response(request)

        # It's not worth attempting to compress really short responses.
        if not response.streaming and len(response.content) < self.MIN_LEN:
            return response

        # Avoid compression if we've already got a content-encoding.
        if response.has_header("Content-Encoding"):
            return response

        patch_vary_headers(response, ("Accept-Encoding",))

        encoding, compress_string, compress_sequence = self.get_supported_compressor(
            request.META.get("HTTP_ACCEPT_ENCODING", "")
        )
        if encoding is None:
            # Client didn't indicate support for anything we can do, so just return the original response.
            return response

        compress_kwargs = {}
        if encoding == "gzip":
            compress_kwargs["max_random_bytes"] = self.MAX_RANDOM_BYTES

        if response.streaming:
            if getattr(response, "is_async", False):
                # forward args explicitly to capture fixed references in case they are set again later.
                async def compress_wrapper(streaming_content, **compress_kwargs):
                    async for chunk in streaming_content:
                        yield compress_string(chunk, **compress_kwargs)

                response.streaming_content = compress_wrapper(response.streaming_content, **compress_kwargs)
            else:
                response.streaming_content = compress_sequence(response.streaming_content, **compress_kwargs)

            # Delete the `Content-Length` header for streaming content, because
            # we won't know the compressed size until we stream it.
            del response.headers["Content-Length"]
        else:
            # Return the compressed content only if it's actually shorter.
            compressed_content = compress_string(response.content, **compress_kwargs)
            if len(response.content) - len(compressed_content) < self.MIN_IMPROVEMENT:
                return response
            response.content = compressed_content
            response.headers["Content-Length"] = str(len(response.content))

        # If there is a strong ETag, make it weak to fulfill the requirements
        # of RFC 9110 Section 8.8.1 while also allowing conditional request
        # matches on ETags.
        etag = response.headers.get("ETag")
        if etag and etag.startswith('"'):
            response.headers["ETag"] = "W/" + etag
        response.headers["Content-Encoding"] = encoding

        return response

    @classmethod
    def get_supported_compressor(
        cls, accept_encoding_header: str
    ) -> tuple[str, Callable[..., bytes] | None, Callable[..., bytes] | None] | tuple[None, None, None]:
        """Determine the best compressor to use based on the client's Accept-Encoding header.

        Returns a tuple of (encoding_name, bulk_compressor, stream_compressor),
        or (None, None, None) if no suitable compressor is found.
        """
        # We don't want to process extremely long headers. It might be an attack:
        accept_encoding_header = accept_encoding_header[:200]
        supported_client_encodings = {extract_encoding_name(e) for e in accept_encoding_header.split(",")}

        # If everything is supported, just take the first one in our preference order.
        if "*" in supported_client_encodings:
            return compressors[0]

        for encoding, compress_string, compress_sequence in compressors:
            if encoding in supported_client_encodings:
                return encoding, compress_string, compress_sequence

        return (None, None, None)
