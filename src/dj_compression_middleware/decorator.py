from collections.abc import Callable
from functools import wraps
from inspect import iscoroutinefunction

from django.http import HttpRequest, HttpResponse


def no_compress(view_func: Callable) -> Callable:
    """When using this decorator, the view function will be exempt from compression."""
    # view_func.no_compress = True would also work, but decorators are nicer
    # if they don't have side effects, so return a new function.

    if iscoroutinefunction(view_func):

        async def _view_wrapper(request: HttpRequest, *args: tuple, **kwargs: dict) -> HttpResponse:
            return await view_func(request, *args, **kwargs)

    else:

        def _view_wrapper(request: HttpRequest, *args: tuple, **kwargs: dict) -> HttpResponse:
            return view_func(request, *args, **kwargs)

    _view_wrapper.no_compress = True  # ty:ignore[invalid-assignment]

    return wraps(view_func)(_view_wrapper)
