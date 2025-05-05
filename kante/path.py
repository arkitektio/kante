from typing import Any
from django.urls import path, re_path, URLPattern
from django.conf import settings


def dynamicpath(rel_path: str, view: Any, kwargs: dict[str, Any]| None  = None, name: str | None = None) -> URLPattern:
    if settings.MY_SCRIPT_NAME:
        return path(settings.MY_SCRIPT_NAME.lstrip("/") + "/" + rel_path,  view, kwargs, name)
    else:
        return path(rel_path, view, kwargs, name)



def re_dynamicpath(regex_path: str, view: Any, kwargs: dict[str, Any] | None = None, name: str | None = None) -> URLPattern:
    if settings.MY_SCRIPT_NAME:
        return re_path(rf"^{settings.MY_SCRIPT_NAME.lstrip('/')}/", view, kwargs, name)
    else:
        return re_path(regex_path, view, kwargs, name)

