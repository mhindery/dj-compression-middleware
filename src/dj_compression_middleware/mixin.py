class NoCompressMixin:
    """When using this view mixin, the response will not be compressed by the CompressionMiddleware."""

    def dispatch(self, request, *args, **kwargs):  # noqa: D102
        response = super().dispatch(request, *args, **kwargs)  # ty:ignore[unresolved-attribute]
        response.no_compress = True
        return response
