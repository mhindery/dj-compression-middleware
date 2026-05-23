from django.http import HttpRequest, HttpResponse
from django.views import View

from dj_compression_middleware import CompressionMiddleware, NoCompressMixin

from .utils import UTF8_LOREM_IPSUM_IN_CZECH


def test_middleware_compress_does_not_compress_when_using_no_compress_mixin() -> None:
    fake_request = HttpRequest()
    fake_request.META["HTTP_ACCEPT_ENCODING"] = "br"
    fake_request.method = "GET"
    response_content = UTF8_LOREM_IPSUM_IN_CZECH

    class TestView(NoCompressMixin, View):
        def get(self, request: HttpRequest, *args: tuple, **kwargs: dict) -> HttpResponse:  # noqa: ARG002
            return HttpResponse(response_content)

    compression_middleware = CompressionMiddleware(TestView.as_view())
    response = compression_middleware(fake_request)

    assert response.content.decode("utf-8") == response_content
    assert response.get("Vary") is None
    assert response.get("Content-Encoding") is None
