from typing import Iterable
from graphql import ExecutionContext
import strawberry
from strawberry.extensions import SchemaExtension
from strawberry.schema.config import StrawberryConfig
from strawberry.types.scalar import ScalarDefinition, ScalarWrapper


class Schema(strawberry.federation.Schema):
    """Custom schema class to use the custom type and field functions."""

    def __init__(
        self,
        query: type | None = None,
        mutation: type | None = None,
        subscription: type | None = None,
        directives: Iterable[type] = (),
        types: Iterable[type] = (),
        extensions: Iterable[type[SchemaExtension] | SchemaExtension] = (),
        execution_context_class: type[ExecutionContext] | None = None,
        config: StrawberryConfig | None = None,
        scalar_overrides: dict[object, type | ScalarWrapper | ScalarDefinition] | None = None,
        schema_directives: Iterable[object] = (),
        enable_federation_2: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(
            query=query,
            mutation=mutation,
            subscription=subscription,
            directives=directives,
            types=types,
            extensions=extensions,
            execution_context_class=execution_context_class,
            config=config,
            scalar_overrides=scalar_overrides,
            schema_directives=schema_directives,
            **kwargs,
        )
