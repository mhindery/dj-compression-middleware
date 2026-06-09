import pytest
from django.http import HttpRequest, HttpResponse

from dj_compression_middleware import CompressionMiddleware, no_compress

from .utils import UTF8_LOREM_IPSUM_IN_CZECH


def test_middleware_compress_does_not_compress_when_using_no_compress_decorator() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    fake_request.method = "GET"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    @no_compress
    def handler(request: HttpRequest) -> HttpResponse:  # noqa: ARG001
        return HttpResponse(response_content)

    compression_middleware = CompressionMiddleware(handler)
    response = compression_middleware(fake_request)

    assert response.content.decode("utf-8") == response_content
    assert response.get("Vary") is None
    assert response.get("Content-Encoding") is None


@pytest.mark.asyncio
async def test_middleware_compress_does_not_compress_when_using_async_no_compress_decorator() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    fake_request.method = "GET"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    @no_compress
    async def handler(request: HttpRequest) -> HttpResponse:  # noqa: ARG001, RUF029
        return HttpResponse(response_content)

    compression_middleware = CompressionMiddleware(handler)
    response = await compression_middleware(fake_request)

    assert response.content.decode("utf-8") == response_content
    assert response.get("Vary") is None
    assert response.get("Content-Encoding") is None
