"""Typed pub/sub channels over the Django Channels layer.

A :class:`Channel` binds a pydantic model to a channel-layer message type, so a
broadcaster and a subscriber cannot disagree about the payload shape. What they
*can* still disagree about is the **group** (the "room") -- and that is where
tenancy lives, so this module tries hard to make the two sides share one
definition of it:

* :meth:`Channel.org_group` builds a room name from an organization, and both
  sides are expected to call it rather than writing the string twice.
* Omitting ``groups`` entirely is deprecated (see :meth:`Channel.abroadcast`),
  because the historical fallback was a single process-wide ``"default"`` room
  shared by every channel in the deployment.

The recommended message shape is :class:`CRUDSignal`: relay the *id* of the row
that changed, and have the subscriber re-fetch it through
:func:`kante.scoping.aget_for_org`. That keeps the payload small and makes the
re-fetch the place tenancy is enforced, rather than the room name alone.
"""

import asyncio
import logging
import warnings
from typing import (
    Any,
    AsyncGenerator,
    Generic,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from pydantic import BaseModel, ValidationError

from kante.context import Organization, WsContext
from kante.types import ChannelsLayer, Info

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

LEGACY_DEFAULT_GROUPS = ["default"]
"""The historical fallback when ``groups`` was omitted.

Every channel in the process shared this one room, so two unrelated channels
that both omitted ``groups`` cross-fed each other -- across tenants. Kept for
backwards compatibility and warned about; pass ``groups`` explicitly, or give the
channel ``default_groups``.
"""


class CRUDSignal(BaseModel):
    """The standard create/update/delete channel payload.

    Carries the *id* of the affected row, not the row itself: ids survive the
    channel layer's serializer unchanged, stay small, and force the subscriber to
    re-fetch -- which is the natural place to apply organization scoping.

    Exactly one field is set per message::

        channel.broadcast(CRUDSignal(create=instance.id), groups=[room])
    """

    create: Optional[int] = None
    update: Optional[int] = None
    delete: Optional[int] = None


def get_real_channel_layer() -> ChannelsLayer:
    """Get the real channel layer, not the mock one."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        raise RuntimeError("Channel layer is not available in the context")
    return channel_layer  # type: ignore[no-any-return]


def _organization_id(org: Union[int, str, Organization]) -> str:
    """Normalize an organization (or its id) to the id used in a room name."""
    if isinstance(org, (int, str)):
        return str(org)
    return str(org.id)


def org_group(prefix: str, org: Union[int, str, Organization], sub: Optional[object] = None) -> str:
    """Build a tenant-scoped room name.

    ``org`` may be an :class:`~kante.context.Organization` or a bare id::

        org_group("files", 7)            # "files:org:7"
        org_group("files", 7, folder.id) # "files:org:7:12"

    Prefer :meth:`Channel.org_group`, which fills ``prefix`` in from the channel
    name so a broadcaster and a listener cannot drift apart.
    """
    room = f"{prefix}:org:{_organization_id(org)}"
    return f"{room}:{sub}" if sub is not None else room


class Channel(Generic[T]):
    """A typed GraphQL channel using Pydantic for serialization.

    Note: channels built from the same model without an explicit ``name`` share
    the same message type and will receive each other's broadcasts. Pass a
    distinct ``name`` to keep two channels of the same model isolated.

    ``default_groups`` sets the rooms used when a call omits ``groups``. Setting
    it is the supported way to have a channel with an implicit room -- unlike the
    deprecated global ``"default"``, it is scoped to this channel.
    """

    def __init__(
        self,
        model: Type[T],
        name: Optional[str] = None,
        default_groups: Optional[Sequence[str]] = None,
    ) -> None:
        """Bind ``model`` to a channel-layer message type."""
        self.model = model
        self.name = name or model.__name__
        # Precomputed once so broadcast/listen don't rebuild it per call and so
        # both sides share a single source of truth for the message type.
        self.message_type = f"channel.{self.name}"
        self.default_groups: Optional[List[str]] = (
            list(default_groups) if default_groups is not None else None
        )

    def org_group(self, org: Union[int, str, Organization], sub: Optional[object] = None) -> str:
        """Build a tenant-scoped room name for this channel.

        Call this on **both** sides -- in the signal handler that broadcasts and
        in the resolver that listens -- so the room name has exactly one
        definition::

            # signals.py
            file_channel.broadcast(
                CRUDSignal(create=instance.id),
                groups=[file_channel.org_group(instance.organization)],
            )

            # subscriptions.py
            async for message in file_channel.listen(
                info, [file_channel.org_group(info.context.request.organization)]
            ):
                ...

        Writing the f-string by hand in two files instead is how a room name on
        one side stops matching the other -- which fails silently, because a
        subscription to a room nobody broadcasts to simply never yields.
        """
        return org_group(self.name, org, sub)

    def _resolve_groups(self, groups: Optional[Sequence[str]], caller: str) -> List[str]:
        """Return the rooms to use, warning if the legacy global default applies."""
        if groups is not None:
            return list(groups)
        if self.default_groups is not None:
            return list(self.default_groups)
        warnings.warn(
            f"Channel({self.name!r}).{caller}() was called without 'groups'. It "
            f"currently falls back to the process-wide {LEGACY_DEFAULT_GROUPS!r} "
            "room, which every channel in the deployment shares -- including "
            "across organizations. Pass groups= explicitly (see "
            "Channel.org_group), or set default_groups= on the channel. This "
            "fallback will be removed in kante 3.",
            DeprecationWarning,
            stacklevel=3,
        )
        return list(LEGACY_DEFAULT_GROUPS)

    async def abroadcast(self, message: T, groups: Optional[Sequence[str]] = None) -> None:
        """Broadcast a validated model instance to groups (async-native).

        Use this from async code (resolvers, subscriptions, any running event
        loop). ``broadcast`` is the sync wrapper around it.
        """
        resolved = self._resolve_groups(groups, "abroadcast")
        channel_layer = get_real_channel_layer()
        # mode="json" yields primitives (e.g. ISO strings for datetime, str for
        # UUID/Decimal) so the message survives the channel layer's serializer
        # (channels-redis uses msgpack, which cannot pack native datetime/UUID).
        # The receiving end's model_validate coerces them back to rich types.
        message_data = message.model_dump(mode="json")
        payload = {
            "type": self.message_type,
            "message": message_data,
        }

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "[%s] Broadcasting to groups %s: %s", self.name, resolved, message_data
            )

        # Fan out concurrently; group_send treats payload as read-only (it is
        # re-serialized per group), so sharing one dict across calls is safe.
        await asyncio.gather(
            *(channel_layer.group_send(group, payload) for group in resolved)
        )

    def broadcast(self, message: T, groups: Optional[Sequence[str]] = None) -> None:
        """Broadcast a validated model instance to groups (sync wrapper).

        Performance/correctness: this bridges to the event loop exactly once via
        a single ``async_to_sync`` call rather than once per group. Note that
        ``async_to_sync`` raises if called from a thread already running an event
        loop -- call ``abroadcast`` from async code instead.
        """
        resolved = self._resolve_groups(groups, "broadcast")
        async_to_sync(self.abroadcast)(message, resolved)

    def broadcast_on_commit(
        self, message: T, groups: Optional[Sequence[str]] = None
    ) -> None:
        """Broadcast once the surrounding transaction commits.

        Django signal handlers fire while the writing transaction is still open.
        Broadcasting immediately publishes events for rows that may still roll
        back -- subscribers then re-fetch an id that never existed -- and does the
        channel-layer work inside the lock window.

        Outside a transaction ``on_commit`` runs the callback immediately, so
        non-transactional paths behave exactly as :meth:`broadcast` does. This is
        the right default for anything driven by ``post_save`` / ``post_delete``.
        """
        resolved = self._resolve_groups(groups, "broadcast_on_commit")
        transaction.on_commit(lambda: self.broadcast(message, resolved))

    async def listen(
        self,
        context: Union[Info, WsContext],
        groups: Optional[Sequence[str]] = None,
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[T, None]:
        """Async generator that yields deserialized model messages.

        Accepts either the resolver's ``info`` or an already-narrowed
        :class:`~kante.context.WsContext`. Passing ``info`` directly is preferred:
        a subscription's ``info.context`` is typed as the
        ``HttpContext | WsContext`` union, so handing over the context forced
        every call site into an ``assert isinstance(...)`` or a ``cast``.

        ``timeout`` is forwarded to the underlying listener as a per-message wait
        bound (``None`` waits indefinitely).
        """
        ws_context = _as_ws_context(context)
        resolved = self._resolve_groups(groups, "listen")
        channel_layer = ws_context.consumer.channel_layer
        if not channel_layer:
            raise RuntimeError("Channel layer is not available in the context")

        # NOTE: do NOT call ``group_add`` here -- ``listen_to_channel(groups=...)``
        # already registers (and later discards) the channel for each group.
        # Adding them manually doubled the registration round-trips per
        # subscription and skipped the matching ``group_discard`` on teardown.
        async with ws_context.consumer.listen_to_channel(
            self.message_type, groups=resolved, timeout=timeout
        ) as cm:
            async for message in cm:
                raw = message.get("message")
                try:
                    yield self.model.model_validate(raw)
                except ValidationError as e:
                    logger.warning(f"[{self.name}] Invalid message received: {e}")
                    continue  # Optionally re-raise or yield raw here


def _as_ws_context(context: Union[Info, WsContext, Any]) -> WsContext:
    """Accept either an ``Info`` or a ``WsContext`` and return the ``WsContext``."""
    if isinstance(context, WsContext):
        return context
    inner = getattr(context, "context", None)
    if isinstance(inner, WsContext):
        return inner
    raise TypeError(
        "Channel.listen requires a websocket request: pass the resolver's `info` "
        "(preferred) or a WsContext. Received "
        f"{type(context).__name__}, which means this resolver was reached over "
        "HTTP -- subscriptions must run on the GraphQL websocket transport."
    )


def build_channel(
    model: Type[T],
    name: Optional[str] = None,
    default_groups: Optional[Sequence[str]] = None,
) -> Channel[T]:
    """Build a channel with the given model and optional name."""
    return Channel(model, name, default_groups=default_groups)


__all__ = [
    "CRUDSignal",
    "Channel",
    "LEGACY_DEFAULT_GROUPS",
    "build_channel",
    "get_real_channel_layer",
    "org_group",
]
