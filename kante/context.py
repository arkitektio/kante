"""The request context kante hands to every resolver.

A resolver reaches the caller through ``info.context.request``: the user, the
client, the organization, the membership and (when present) the provenance
token. The principals are declared here as structural protocols so kante stays
independent of whichever models a service authenticates with -- ``authentikate``
is what fills them in.
"""

import datetime
from strawberry.channels import ChannelsConsumer
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Mapping, Optional, Protocol
from strawberry.http.temporal_response import TemporalResponse


# NOTE: every member of every protocol below is declared read-only
# (``@property``) -- including ``Actor`` and ``Provenance``. Do not "simplify"
# any of them back to a plain annotation (``sub: str``).
#
# A plain annotation is a *settable* protocol member, which has two consequences,
# both of which have bitten us:
#
#   1. mypy rejects a read-only implementation against it -- which is exactly
#      what Django hands us: ``is_anonymous`` is a ``@property`` on
#      ``AbstractBaseUser``. Getting this wrong forced a ``# type: ignore`` onto
#      every ``UniversalRequest(...)`` construction downstream.
#   2. A settable member is *invariant*, so its type must match exactly rather
#      than merely be compatible. ``Provenance.act`` was declared as settable
#      ``act: Actor``, which meant no implementation could ever satisfy
#      ``Provenance`` unless its ``act`` was literally ``kante.context.Actor`` --
#      a structural match was not enough, so
#      ``authentikate.provenance.ProvenanceToken`` was rejected despite being a
#      perfect fit.
#
# Read-only members accept both plain attributes (Django fields, pydantic fields)
# and properties, and are covariant, so this is the permissive direction in both
# respects.


class User(Protocol):
    """The authenticated principal of a request."""

    @property
    def id(self) -> int:
        """The user's primary key."""
        ...

    @property
    def sub(self) -> str | None:
        """The ``sub`` claim of the token that authenticated this user.

        Optional: a user row can exist without one (e.g. a locally created
        superuser), which is how ``authentikate`` models it.
        """
        ...

    @property
    def is_anonymous(self) -> bool:
        """Whether the user is anonymous.

        A read-only property, matching ``django.contrib.auth.base_user``.
        """
        ...


class Client(Protocol):
    """The OAuth client an authenticated request was made through."""

    @property
    def id(self) -> int:
        """The client's primary key."""
        ...

    @property
    def client_id(self) -> str:
        """The client's OAuth ``client_id``."""
        ...


class Organization(Protocol):
    """The tenant a request is scoped to."""

    @property
    def id(self) -> int:
        """The organization's primary key."""
        ...

    @property
    def slug(self) -> str:
        """The organization's unique slug."""
        ...


class Membership(Protocol):
    """The link between a :class:`User` and an :class:`Organization`."""

    @property
    def id(self) -> int:
        """The membership's primary key."""
        ...


class Actor(Protocol):
    "The executing agent a provenance token is issued to."

    @property
    def sub(self) -> str:
        """The executing agent's user sub."""
        ...

    @property
    def cid(self) -> str:
        """The executing agent's OAuth client_id."""
        ...


class Provenance(Protocol):
    """A provenance token attesting who caused a unit of work and with which inputs.

    Minted by Rekuest at each assignment and verified on the consuming end; it is
    delivered under the Rekuest task header and attached to the request so
    resolvers can read it contextually. Mirrors
    ``authentikate.provenance.ProvenanceToken``.
    """

    # --- registered claims ---
    @property
    def iss(self) -> str:
        """The provenance issuer id (e.g. "rekuest")."""
        ...

    @property
    def aud(self) -> List[str]:
        """The target services the token is scoped to."""
        ...

    @property
    def sub(self) -> str:
        """The immediate causer of this hop (the request principal)."""
        ...

    @property
    def act(self) -> Actor:
        """The actor the token is issued to (the executing agent).

        Read-only for the reason in the NOTE above, and this member in
        particular: a settable member is *invariant*, so an implementation whose
        ``act`` is its own concrete Actor class would be rejected even though
        that class satisfies :class:`Actor` perfectly well. Read-only makes it
        covariant, which is what lets ``authentikate.provenance.ProvenanceToken``
        satisfy this protocol.
        """
        ...

    @property
    def iat(self) -> datetime.datetime:
        """Issued-at."""
        ...

    @property
    def exp(self) -> datetime.datetime:
        """Expiry."""
        ...

    @property
    def jti(self) -> str:
        """Unique per token; the verifier enforces single-use."""
        ...

    # --- rekuest provenance claims ---
    @property
    def tsk(self) -> str:
        """This assignation id."""
        ...

    @property
    def ptk(self) -> str | None:
        """Immediate parent assignation id (None if this is the root)."""
        ...

    @property
    def rtk(self) -> str:
        """Root assignation id of the whole tree."""
        ...

    @property
    def rcb(self) -> str:
        """The human principal at the root of the tree (always human)."""
        ...

    @property
    def ahs(self) -> str:
        """SHA-256 of the canonicalized args."""
        ...

    @property
    def aha(self) -> str:
        """The canonicalization algorithm/version, so a verifier can recompute ahs."""
        ...

    @property
    def raw(self) -> str:
        """The raw original token string."""
        ...

    @property
    def is_root(self) -> bool:
        """Whether this token is the root of its causal tree."""
        ...

    def has_audience(self, service: str) -> bool:
        """Whether ``service`` is one of the token's target audiences."""
        ...

    def verify_args(self, args: Any) -> bool:
        """Whether ``args`` canonically hash to this token's ``ahs``."""
        ...


@dataclass(slots=True)
class UniversalRequest:
    """The authenticated principals of one request.

    Fields start unset and are filled in by a strawberry extension
    (``authentikate``'s). Reading one that was never set raises, so an
    unauthenticated request fails loudly rather than resolving as nobody.
    """

    _extensions: Dict[str, Any]
    _client: Optional[Client] = None
    _user: Optional[User] = None
    _provenance: Optional[Provenance] = None
    _organization: Optional[Organization] = None
    _membership: Optional[Membership] = None

    @property
    def user(self) -> User:
        """Get the user associated with the request."""
        if self._user is None:
            raise ValueError(
                "User is not set in the request. Do you have a strawberry extension setting this?"
            )

        return self._user

    @property
    def membership(self) -> Membership:
        """Get the user associated with the request."""
        if self._membership is None:
            raise ValueError(
                "Membserhip is not set in the request. Do you have a strawberry extension setting this?"
            )

        return self._membership

    @property
    def provenance(self) -> Provenance:
        """Get the provenance token associated with the request."""
        if self._provenance is None:
            raise ValueError(
                "Provenance is not set in the request. Do you have a strawberry extension setting this?"
            )

        return self._provenance

    @property
    def client(self) -> Client:
        """Get the OAuth client associated with the request."""
        if self._client is None:
            raise ValueError(
                "Client is not set in the request.  Do you have a strawberry extension setting this?"
            )

        return self._client

    @property
    def organization(self) -> Organization:
        """Get the organization associated with the request."""
        if self._organization is None:
            raise ValueError(
                "Organization is not set in the request.  Do you have a strawberry extension setting this?"
            )

        return self._organization

    def set_user(self, user: User) -> None:
        """Set an extension value in the request."""
        self._user = user

    def set_organization(self, organization: Organization) -> None:
        """Set an organization in the request."""
        self._organization = organization

    def set_membership(self, membership: Membership) -> None:
        """Set the membership in the request."""
        self._membership = membership

    def set_client(self, client: Client) -> None:
        """Set an extension value in the request."""
        self._client = client

    def set_provenance(self, provenance: Provenance) -> None:
        """Set the provenance token in the request."""
        self._provenance = provenance

    def get_extension(self, name: str) -> Any:
        """Get an extension value from the request."""

        if name not in self._extensions:
            raise ValueError(f"Extension {name} is not set in the request.")
        return self._extensions.get(name)

    def set_extension(self, name: str, value: Any) -> None:
        """Set an extension value in the request."""

        self._extensions[name] = value


@dataclass
class WsContext:
    """The request context of a GraphQL websocket connection."""

    request: UniversalRequest
    response: TemporalResponse
    connection_params: Dict[str, Any]
    consumer: ChannelsConsumer
    extensions: Optional[Dict[str, Any]] = None
    type: Literal["ws"] = "ws"
    # Per-request store for batching DataLoaders (e.g. federation reference
    # resolution). Not slotted so downstream extensions can still stash state.
    _loaders: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass
class HttpContext:
    """The request context of a GraphQL HTTP request."""

    request: UniversalRequest
    response: TemporalResponse
    headers: Mapping[str, str]
    type: Literal["http"] = "http"
    # Per-request store for batching DataLoaders (e.g. federation reference
    # resolution). Not slotted so downstream extensions can still stash state.
    _loaders: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


Context = HttpContext | WsContext
