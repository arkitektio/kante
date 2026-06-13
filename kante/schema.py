from typing import Iterable
from graphql import ExecutionContext
import strawberry
from strawberry.extensions import SchemaExtension
from strawberry.schema.config import StrawberryConfig
from strawberry.types.scalar import ScalarDefinition, ScalarWrapper
from strawberry_django.optimizer import DjangoOptimizerExtension


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
        enable_optimizer: bool = True,
        enable_federation_2: bool = True,
        **kwargs,
    ) -> None:
        # Performance: strawberry-django issues one query per nested relation
        # unless the optimizer extension is installed. Since kante exists to
        # support strawberry-django projects, register it by default so users
        # are not silently exposed to N+1 across the whole API. Opt out with
        # ``enable_optimizer=False`` or by passing your own instance.
        extensions = list(extensions)
        if enable_optimizer and not any(
            ext is DjangoOptimizerExtension
            or isinstance(ext, DjangoOptimizerExtension)
            for ext in extensions
        ):
            extensions.insert(0, DjangoOptimizerExtension)

        # NOTE: ``enable_federation_2`` is accepted for backwards compatibility
        # but intentionally NOT forwarded: the underlying federation Schema no
        # longer takes this argument (it uses ``federation_version``, defaulting
        # to v2), so forwarding it would raise. Federation 2 is already the
        # default, making this a no-op kept only to avoid breaking callers.
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
