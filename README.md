<a href="https://pypi.org/project/dj_compression_middleware/">
    <img src="https://img.shields.io/pypi/v/dj-compression-middleware" alt="PyPI - Latest version">
</a>
<a href="https://pypi.org/project/dj_compression_middleware/">
    <img src="https://img.shields.io/pypi/pyversions/dj-compression-middleware" alt="PyPI - Python versions">
</a>
<a href="https://pypi.org/project/dj_compression_middleware/">
    <img src="https://img.shields.io/pypi/frameworkversions/django/dj-compression-middleware" alt="PyPI - Versions from Framework Classifiers">
</a>

# Dj Compression Middleware


*Note: This project and repo was originally a fork of the project [django-compression-middleware](https://github.com/friedelwolff/django-compression-middleware). As the project did not seem maintained anymore, I forked the project in order to get some open PR's and issues resolved. Credit goes to the original creator: Friedel Wolff. In the meantime I have refactored a lot of the code.*


This package provides Django middleware to compress responses with gzip, brotli, or zstd. It is a replacement of Django's built-in GZipMiddleware as it supports more compression algorithms. Both normal and streaming responses get compressed.

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

Add ``dj_compression_middleware.middleware.CompressionMiddleware`` to your middleware:


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

### Customizing the middleware

You can subclass the middleware and customize some attributes of it to tweak its behaviour, e.g. to select the compression level:

```python
class CustomCompressionMiddleware(CompressionMiddleware):
    # Tweak compression settings
    ZSTD_LEVEL = 7
    BROTLI_QUALITY = 4
    GZIP_COMPRESSLEVEL = 6
    ZLIB_COMPRESSLEVEL = 8
```

For even more customization, you can override the init method and modify the COMPRESSORS to an ordered set of your own preferred compression algorithms.


## Development

Setup a virtual environment:

```shell
uv sync --frozen --all-extras --all-groups
```

Run linting:

```shell
uv run ruff check --no-fix
uv run ty check
```

Run the tests:

```shell
uv run pytest
```
