"""URL helpers that respect the ``MY_SCRIPT_NAME`` deployment prefix."""

from typing import Any

from django.conf import settings
from django.urls import URLPattern, path, re_path


def dynamicpath(
    rel_path: str,
    view: object,
    kwargs: dict[str, Any] | None = None,
    name: str | None = None,
) -> URLPattern:
    """Create a path that respects the MY_SCRIPT_NAME setting.

    This is useful for normal paths that need to be prefixed with the script name.

    Args:
        regex_path (str): The regex path to use.
        view (Any): The view to use.
        kwargs (dict[str, Any] | None, optional): Additional keyword arguments for the path.
        name (str | None, optional): The name of the path.
    Returns:
        URLPattern: The URL pattern with the script name prefixed.
    """
    if settings.MY_SCRIPT_NAME:
        return path(
            settings.MY_SCRIPT_NAME.lstrip("/") + "/" + rel_path,
            view,  # type: ignore[arg-type] -- whatever path() takes: a view, include(), admin urls
            kwargs,
            name,
        )
    else:
        return path(rel_path, view, kwargs, name)  # type: ignore


def re_dynamicpath(
    regex_path: str,
    view: object,
    kwargs: dict[str, Any] | None = None,
    name: str | None = None,
) -> URLPattern:
    """Create a path that respects the MY_SCRIPT_NAME setting.

    This is useful for regex paths that need to be prefixed with the script name.

    Args:
        regex_path (str): The regex path to use.
        view (Any): The view to use.
        kwargs (dict[str, Any] | None, optional): Additional keyword arguments for the path.
        name (str | None, optional): The name of the path.
    Returns:
        URLPattern: The URL pattern with the script name prefixed.
    """
    if settings.MY_SCRIPT_NAME:
        return re_path(
            rf"^{settings.MY_SCRIPT_NAME.lstrip('/')}/" + regex_path.lstrip("^"),
            view,  # type: ignore[arg-type] -- whatever re_path() takes: a view, include(), admin urls
            kwargs,
            name,
        )
    else:
        return re_path(regex_path, view, kwargs, name)  # type: ignore
