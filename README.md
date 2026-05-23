![PyPI - Version](https://img.shields.io/pypi/v/dj-compression-middleware)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dj-compression-middleware)
![PyPI - Versions from Framework Classifiers](https://img.shields.io/pypi/frameworkversions/django/dj-compression-middleware)
![PyPI - License](https://img.shields.io/pypi/l/dj-compression-middleware)


# Dj Compression Middleware


*Note: This project and repo was originally a fork of the project [django-compression-middleware](https://github.com/friedelwolff/django-compression-middleware). As the project did not seem maintained anymore, I forked the project in order to get some open PR's and issues resolved. Credit goes to the original creator: Friedel Wolff. In the meantime I have refactored a lot of the code.*


This package provides Django middleware to compress responses with gzip, brotli, or zstd. It is a replacement of Django's built-in GZipMiddleware but support more compression algorithms. Both normal and streaming responses get compressed.

Compression of responses happens at runtime, if you are looking to compress your static assets, look at e.g. [Django-compressor](https://github.com/django-compressor/django-compressor), [WhiteNoise](https://whitenoise.readthedocs.io/en/stable/django.html#django-compressor).

The middleware looks at a requests' ``Accept-Encoding`` header in order to select appropriate compression. It will choose one using this order of preference:

- Zstandard (zstd)
- Brotli (br)
- gzip (gzip)

## Installation and usage

Install the package:

```shell
uv add dj-compression-middleware
# or
pip install dj-compression-middleware
```

In your Django settings, add ``dj_compression_middleware.middleware.CompressionMiddleware`` to the ``MIDDLEWARE``:


```python
MIDDLEWARE = [
    # ...
    'dj_compression_middleware.middleware.CompressionMiddleware',
    # ...
]
```

Remove ``GZipMiddleware`` and ``BrotliMiddleware`` if they were present, as this middleware replaces them.

### Excluding views from compression

When you want to disable compression for a single view, it can be done like this for either a function-based or class-based view:

```python
from dj_compression_middleware import no_compress, NoCompressMixin

@no_compress
def index_view(request):
    ...


class MyView(NoCompressMixin, View):
    ...
```
