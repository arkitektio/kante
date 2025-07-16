from typing import Any
from django.urls import path, re_path, URLPattern
from django.conf import settings


def dynamicpath(rel_path: str, view: Any, kwargs: dict[str, Any]| None  = None, name: str | None = None) -> URLPattern:
    """ Create a path that respects the MY_SCRIPT_NAME setting. 
    
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
        return path(settings.MY_SCRIPT_NAME.lstrip("/") + "/" + rel_path,  view, kwargs, name) # type: ignore
    else:
        return path(rel_path, view, kwargs, name) # type: ignore



def re_dynamicpath(regex_path: str, view: Any, kwargs: dict[str, Any] | None = None, name: str | None = None) -> URLPattern:
    """ Create a path that respects the MY_SCRIPT_NAME setting. 
    
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
        return re_path(rf"^{settings.MY_SCRIPT_NAME.lstrip('/')}/" + regex_path.lstrip("^"), view, kwargs, name) # type: ignore
    else:
        return re_path(regex_path, view, kwargs, name) # type: ignore

