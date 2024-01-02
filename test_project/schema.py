from kante.types import Info
import strawberry
from strawberry import ID
from kante.directives import upper, replace, relation
from koherent.strawberry.extension import KoherentExtension



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
