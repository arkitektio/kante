"""Tests for channel group derivation, the deprecated default, and on-commit."""

import asyncio
import warnings

import pytest
from channels.layers import get_channel_layer
from django.db import transaction

from kante.channel import CRUDSignal, Channel, build_channel, org_group


class _Org:
    """Shaped like the organization protocol."""

    id = 7
    slug = "acme"


# --------------------------------------------------------------------------
# group derivation
# --------------------------------------------------------------------------


def test_org_group_accepts_an_organization_or_an_id() -> None:
    """A room name is the same whether built from the object or its id."""
    assert org_group("files", _Org()) == org_group("files", 7) == "files:org:7"


def test_org_group_appends_a_sub_key() -> None:
    """A sub-key narrows the room within one organization."""
    assert org_group("files", 7, 12) == "files:org:7:12"


def test_channel_org_group_uses_the_channel_name() -> None:
    """The prefix comes from the channel, so both sides cannot disagree."""
    channel = build_channel(CRUDSignal, "files")

    assert channel.org_group(_Org()) == "files:org:7"


def test_broadcaster_and_listener_derive_the_same_room() -> None:
    """The whole point of the helper: one definition, two call sites.

    Room names written by hand in a signal handler and a resolver are how
    elektro ended up broadcasting to `traces` while listening on `images` --
    a subscription that silently never yields.
    """
    channel = build_channel(CRUDSignal, "files")
    org = _Org()

    broadcaster_room = channel.org_group(org)
    listener_room = channel.org_group(org)

    assert broadcaster_room == listener_room


def test_different_organizations_get_different_rooms() -> None:
    """Two tenants never share a room."""
    channel = build_channel(CRUDSignal, "files")

    assert channel.org_group(1) != channel.org_group(2)


# --------------------------------------------------------------------------
# the deprecated global default group
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_omitting_groups_warns() -> None:
    """The process-wide "default" room is deprecated, not silent."""
    channel = build_channel(CRUDSignal, "warns_channel")

    with pytest.warns(DeprecationWarning, match="default"):
        await channel.abroadcast(CRUDSignal(create=1))


@pytest.mark.asyncio
async def test_explicit_groups_do_not_warn() -> None:
    """Passing groups is the supported path and stays quiet."""
    channel = build_channel(CRUDSignal, "quiet_channel")

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        await channel.abroadcast(CRUDSignal(create=1), groups=["room"])


@pytest.mark.asyncio
async def test_default_groups_replace_the_global_default() -> None:
    """A channel-scoped default is supported; the process-wide one is not."""
    channel = build_channel(
        CRUDSignal, "defaulted_channel", default_groups=["its_own_room"]
    )
    layer = get_channel_layer()
    listener = await layer.new_channel()
    await layer.group_add("its_own_room", listener)

    await channel.abroadcast(CRUDSignal(create=3))

    received = await asyncio.wait_for(layer.receive(listener), timeout=2)
    assert received["message"] == {"create": 3, "update": None, "delete": None}


# --------------------------------------------------------------------------
# CRUDSignal
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_signal_round_trips() -> None:
    """The standard envelope survives the channel layer and validates back."""
    channel: Channel[CRUDSignal] = build_channel(CRUDSignal, "crud_channel")
    layer = get_channel_layer()
    listener = await layer.new_channel()
    await layer.group_add("crud_room", listener)

    await channel.abroadcast(CRUDSignal(update=42), groups=["crud_room"])

    received = await asyncio.wait_for(layer.receive(listener), timeout=2)
    assert CRUDSignal.model_validate(received["message"]) == CRUDSignal(update=42)


# --------------------------------------------------------------------------
# broadcast_on_commit
# --------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_broadcast_on_commit_waits_for_the_commit() -> None:
    """Nothing is published while the writing transaction is still open."""
    channel = build_channel(CRUDSignal, "commit_channel")
    sent = []
    channel.broadcast = lambda message, groups=None: sent.append((message, groups))  # type: ignore[method-assign]

    with transaction.atomic():
        channel.broadcast_on_commit(CRUDSignal(create=1), groups=["room"])
        assert sent == [], "broadcast must not fire inside the transaction"

    assert sent == [(CRUDSignal(create=1), ["room"])]


@pytest.mark.django_db(transaction=True)
def test_broadcast_on_commit_is_dropped_on_rollback() -> None:
    """A rolled-back write never announces a row that does not exist."""
    channel = build_channel(CRUDSignal, "rollback_channel")
    sent = []
    channel.broadcast = lambda message, groups=None: sent.append((message, groups))  # type: ignore[method-assign]

    class _Rollback(Exception):
        pass

    with pytest.raises(_Rollback):
        with transaction.atomic():
            channel.broadcast_on_commit(CRUDSignal(create=1), groups=["room"])
            raise _Rollback

    assert sent == []
