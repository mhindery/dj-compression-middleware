# Dj Compression Middleware


*Note: This repo is a fork of the project [django-compression-middleware](https://github.com/friedelwolff/django-compression-middleware). As the project did not seem maintained anymore, I forked the project in order
to get some open PR's and issues resolved. Most of the credit goes to the original creator: Friedel Wolff.*


This middleware implements compressed content encoding for HTTP. It is similar
to Django's ``GZipMiddleware`` but additionally supports
other compression methods. It is meant to be a drop-in replacement for Django's
``GZipMiddleware``. Its documentation — including security warnings — therefore
apply here as well.

The middleware is focussed on the task of compressing typical Django responses
such as HTML, JSON, etc.  Both normal (bulk) and streaming responses are
supported. For static file compression, have a look at other projects such as
`WhiteNoise`_.

Zstandard is a new method for compression with little client support so far.
Most browsers now support Brotli compression (check support status on `Can I
use... Brotli`_). The middleware will choose the best compression method
supported by the client as indicated in the request's ``Accept-Encoding``
header. In order of preference:

- Zstandard (zstd)
- Brotli (br)
- gzip (gzip)

Installation and usage
----------------------

The following requirements are supported and tested in all reasonable
combinations:

- Python versions: 3.10–3.14
- Django versions: 4.0–5.2

Add the package to your project, e.g.

```shell
uv add dj-compression-middleware
# or
pip install dj-compression-middleware
```

To apply compression to all the views served by Django, add
``dj_compression_middleware.middleware.CompressionMiddleware`` to the
``MIDDLEWARE`` setting:


```python
MIDDLEWARE = [
    # ...
    'dj_compression_middleware.middleware.CompressionMiddleware',
    # ...
]
```

Remove ``GZipMiddleware`` and ``BrotliMiddleware`` if you used it before.
Consult the Django documentation on the correct [ordering of middleware](https://docs.djangoproject.com/en/dev/ref/middleware/#middleware-ordering)

Alternatively you can decorate views individually to serve them with
compression:

```python
from dj_compression_middleware.decorators import compress_page

@compress_page
def index_view(request):
    ...
```

Note that your browser might not send the ``br`` entry in the ``Accept-Encoding``
header when you test without HTTPS (common on localhost). You can force it to
send the header, though. In Firefox, visit ``about:config`` and set
``network.http.accept-encoding`` to indicate support. Note that you might
encounter some problems on the web with such a setting (which is why Brotli is
only supported on secure connections by default).

Credits and Resources
---------------------

The code and tests in this project are based on Django's ``GZipMiddleware`` and
Vašek Dohnal's ``django-brotli``. For compression, it uses the following modules
to bind to fast C modules:

- The `zstandard` bindings. It supports both a C module (for CPython) and CFFI
  which should be appropriate for PyPy. See the documentation for full details.
- The `Brotli` bindings or `brotlipy`. The latter is preferred on PyPy since
  it is implemented using cffi. But both should work on both Python
  implementations.
- Python's builtin `gzip` module.

Contributing
------------

1. Clone this repository
2. Setup an environment using uv: ``uv sync --python-preference only-managed --python 3.12 --frozen --compile-bytecode --all-extras --group dev --group tests --group pages``
3. Change some code
4. Run the tests: in the project root simply execute ``uv run pytest``
5. Submit a pull request and check for any errors reported by the Continuous Integration service.

License
-------

The MPL 2.0 License
