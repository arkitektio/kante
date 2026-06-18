import datetime
from strawberry.channels import ChannelsConsumer
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Mapping, Optional, Protocol
from strawberry.http.temporal_response import TemporalResponse


class User(Protocol):
    id: int
    sub: str

    def is_anonymous(self) -> bool:
        """Check if the user is anonymous."""
        ...


class Client(Protocol):
    id: str
    client_id: str


class Organization(Protocol):
    id: int
    slug: str


class Membership(Protocol):
    id: int


class Actor(Protocol):
    "The executing agent a provenance token is issued to."

    sub: str
    """ The executing agent's user sub. """
    cid: str
    """ The executing agent's OAuth client_id. """


class Provenance(Protocol):
    """A provenance token attesting who caused a unit of work and with which inputs.

    Minted by Rekuest at each assignment and verified on the consuming end; it is
    delivered under the Rekuest task header and attached to the request so
    resolvers can read it contextually. Mirrors
    ``authentikate.provenance.ProvenanceToken``.
    """

    # --- registered claims ---
    iss: str
    """ The provenance issuer id (e.g. "rekuest"). """
    aud: List[str]
    """ The target services the token is scoped to. """
    sub: str
    """ The immediate causer of this hop (the request principal). """
    act: Actor
    """ The actor the token is issued to (the executing agent). """
    iat: datetime.datetime
    """ Issued-at. """
    exp: datetime.datetime
    """ Expiry. """
    jti: str
    """ Unique per token; the verifier enforces single-use. """

    # --- rekuest provenance claims ---
    tsk: str
    """ This assignation id. """
    ptk: str | None
    """ Immediate parent assignation id (None if this is the root). """
    rtk: str
    """ Root assignation id of the whole tree. """
    rcb: str
    """ The human principal at the root of the tree (always human). """
    ahs: str
    """ SHA-256 of the canonicalized args. """
    aha: str
    """ The canonicalization algorithm/version, so a verifier can recompute ahs. """
    raw: str
    """ The raw original token string. """

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
        if self._client is None:
            raise ValueError(
                "Client is not set in the request.  Do you have a strawberry extension setting this?"
            )

        return self._client

    @property
    def organization(self) -> Organization:
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
    request: UniversalRequest
    response: TemporalResponse
    headers: Mapping[str, str]
    type: Literal["http"] = "http"
    # Per-request store for batching DataLoaders (e.g. federation reference
    # resolution). Not slotted so downstream extensions can still stash state.
    _loaders: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


Context = HttpContext | WsContext
