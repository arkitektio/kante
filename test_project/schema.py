from kante.types import Info
from typing import AsyncGenerator
import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension
from strawberry import ID
from kante.directives import upper, replace, relation
from strawberry.permission import BasePermission
from typing import Any, Type
from strawberry.field_extensions import InputMutationExtension
import strawberry_django
from koherent.strawberry.extension import KoherentExtension

from authentikate.strawberry.permissions import HasScopes, IsAuthenticated, NeedsScopes


@strawberry.type
class Me:
    id: str


@strawberry.type
class Query:
    
    @strawberry.field
    def me(self, info: Info, id: ID) -> Me:
        return Me(id=id)


@strawberry.type
class Mutation:
    
    
    @strawberry.field
    def me(self, info: Info, id: ID) -> Me:
        return Me(id=id)

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    directives=[upper, replace, relation],
    extensions=[
        KoherentExtension,
    ],
)
