# CHANGELOG


## Unreleased

### Changed

- **strawberry bumped to 0.324 and strawberry-django to 0.87** (from 0.312 / 0.82),
  which also required `cross-web` 0.7 -- strawberry 0.324 needs `>=0.6`, and kante
  pinned `==0.4.1` despite never importing it.
  - `Info.field_nodes` was **removed** in 0.324. `kante.scoping` read it behind a
    blanket `except Exception: return False`, so the inline-`filters.scope`
    deprecation warning would have stopped firing silently -- queries stayed scoped
    either way, so nothing leaked. The nodes are now read from the graphql-core info
    strawberry wraps, and a test exercises that shape instead of a shim that always
    defined `field_nodes`.
  - Passing a `SchemaExtension` *instance* to `kante.Schema(extensions=[...])` is
    deprecated by strawberry in favour of a zero-argument factory. Both are still
    accepted and forwarded unchanged; the annotation now admits the factory form.

### Fixed

- **`kante.Info` is now the context-typed `Info`.** `kante/__init__` re-exported
  the *unparameterized* `strawberry.types.Info` that `kante/type.py` imports for
  its own annotations, so `from kante import Info` and `kante.Info` silently
  resolved to `Info[Any, Any]` and `info.context` type-checked against nothing.
  It is now imported from `kante.types`, matching `from kante.types import Info`.
- **The `User`, `Client`, `Organization` and `Membership` protocols are now
  satisfiable.** `User` declared `sub: str` and `def is_anonymous(self) -> bool`,
  but Django's `is_anonymous` is a read-only `@property` and `authentikate`'s
  `sub` is nullable -- so no real model matched, and every downstream conftest
  carried a `# type: ignore` on each field of `UniversalRequest(...)`. All
  members are now read-only properties, which accept plain attributes and
  properties alike.
- `django_type(federated=True)` raises `TypeError` instead of asserting that the
  type declares `id`; an `assert` is stripped under `python -O`, leaving a schema
  that advertises `@key(fields: "id")` on a type without one.
- `HttpGetTestClient.get` referenced `List`/`Tuple` without importing them.
  Harmless at runtime (PEP 526 does not evaluate local annotations) but a real
  type error.
- The `router()` example in the README passed `django_asgi_app` positionally,
  where it binds to `schema` and raises `TypeError`.
- `mypy` and `ruff` now pass on the whole repository. Both already ran in CI
  (`quality.yaml`) and both were failing.

### Added

- **`kante.unions`** -- discriminated input unions, previously carried by each
  service by hand. GraphQL has no input unions, so a union arriving through an
  argument is wired as one *merged* input: a discriminator plus every member's
  fields, all optional. `@union_member` declares a member and attaches the
  `@unionElementOf` directive a client generator reads; `@merged_input` fills an
  empty class with the merge, deriving each field's type from the member that
  declares it, computing the `(SCALE, BY_DIMENSION)` description prefix from the
  members that read it, and generating a `to_pydantic` that dispatches through
  `parse_union_member` -- so a parameter contradicting the discriminator is an
  error naming both, never a silent drop. `union_member_types` returns the member
  types for `Schema(types=[...])`, which nothing references and a schema that
  omits them prunes silently.
- **`kante.errors`** now also carries the prose helpers `describe_validation_error`,
  `prose_errors` and `camel_field`: a pydantic `ValidationError` reaches the client
  as one sentence rather than as a multi-line report naming pydantic's machinery.
- `pydantic` is now a declared dependency. It was already required at runtime --
  `kante.pydantic_input` aliases `strawberry.experimental.pydantic.input` -- but
  went undeclared.
- **`kante.scoping`** -- organization (tenant) scoping, previously copy-pasted
  into four services: `for_org`, `get_for_org`, `aget_for_org`,
  `organization_path`, `build_prescoped_queryset`, `build_prescoper`, and an
  `OrganizationScoper` for services needing a different depth or an escape list.
  A model with no path to an organization now raises `UnscopedModelError` rather
  than silently returning every tenant's rows. `filters: null` passed as a
  variable no longer raises `AttributeError` inside the scope check.
- **`kante.errors`** -- `KanteError` and friends (`NotFound`, `PermissionDenied`,
  `ValidationError`, `AuthenticationError`), which attach `extensions.code` so a
  client can distinguish a deliberate error from an internal one. No masking
  extension is installed; messages travel exactly as before.
- **`Channel.org_group()` / `kante.channel.org_group()`** -- one definition of a
  tenant-scoped room name for the broadcaster and the listener to share, instead
  of the same f-string written in two files.
- **`Channel.broadcast_on_commit()`** -- fan an event out only once the writing
  transaction commits, so a rolled-back create never announces a row that does
  not exist.
- **`kante.channel.CRUDSignal`** -- the standard `create`/`update`/`delete`
  envelope, previously hand-written in eight services.
- **`Channel(..., default_groups=[...])`** -- a channel-scoped default room, the
  supported replacement for the process-wide `"default"` one.
- **`kante.types.WsInfo` / `HttpInfo` / `require_ws()` / `is_ws()`** -- narrowing
  for subscriptions, which previously needed an `assert isinstance(...)` (also
  stripped under `-O`) or a `cast` at every call site.
- **`kante.testing.build_http_context` / `build_ws_context` / `build_request`** --
  request-context factories for tests, replacing the block repeated in ten
  services' conftests.

### Changed

- `Channel.listen()` now accepts the resolver's `info` as well as a `WsContext`.
  Every call site passes `info.context`, whose static type is the
  `HttpContext | WsContext` union, so the old signature was unsatisfiable without
  a cast. Passing a `WsContext` still works.

### Deprecated

- Calling `broadcast` / `abroadcast` / `listen` **without `groups`** now warns.
  The fallback is a single process-wide `"default"` room shared by every channel
  in the deployment -- including across organizations. Pass `groups=` (see
  `Channel.org_group`) or set `default_groups=` on the channel. The fallback will
  be removed in kante 3.
- `Schema(enable_federation_2=False)` now warns instead of being silently
  ignored. kante always builds a federation 2 schema.
- Passing `filters: {scope: ...}` **inline** in a query document now warns. It
  was never refused (only a scope passed as a *variable* was): `variable_values`
  did not contain it, so the query fell through and was scoped to the
  authenticated organization anyway. It stays ignored and stays scoped -- the
  warning just makes the ignoring visible. It becomes an error in kante 3.
- The plain re-exports in `kante.type` (`type`, `input`, `interface`, `field`,
  `mutation`, `scalar`, ...) are documented as discouraged: mypy does not carry
  an overload set across a module-level alias, so `@kante.type` resolves the
  decorated class to `builtins.type` and its constructor keywords are all
  reported as unexpected. Import these from `strawberry` / `strawberry_django`
  directly. `django_type` and `django_interface` are unaffected -- they are real
  functions, and they are the ones that add behaviour.


## v2.0.1 (2026-06-20)

### Fixes

- Remove deprecated filters


## v2.0.0 (2026-06-20)

### Breaking

- Carry the provenance token on the request instead of the rekuest task.
- `ChannelsContext` and `EnhancendChannelsHTTPRequest` were removed from
  `kante.context`; use `WsContext` / `HttpContext` and `UniversalRequest`.
- `Channel.listen()` yields a validated pydantic model rather than a raw dict, so
  `message["type"]` must become `message.create` / `.update` / `.delete`.


## v1.3.0 (2026-06-13)

### Features

- Federation reference resolution is batched through a per-request DataLoader.


## v1.2.0 (2026-05-05)

### Features

- `kante.Schema` installs `DjangoOptimizerExtension` by default.


## v1.1.0 (2026-02-13)

### Features

- With updatet strabwery-grahql-django
  ([`8c5e8af`](https://github.com/arkitektio/kante/commit/8c5e8afe7faebe91020844a87de5e46557d08151))


## v1.0.0 (2026-02-13)

### Features

- Updated dependencies
  ([`12d2ed7`](https://github.com/arkitektio/kante/commit/12d2ed78c8002fdf91d6994141344c6c8abd97f0))


## v0.16.1 (2025-10-03)

### Bug Fixes

- Add membership property
  ([`3394aff`](https://github.com/arkitektio/kante/commit/3394affef831220148b34943fb6410e12a73d74b))


## v0.16.0 (2025-09-25)

### Features

- Fix wrong membership
  ([`789384d`](https://github.com/arkitektio/kante/commit/789384d512df7183b828df1a554409fd22933ce4))


## v0.15.0 (2025-09-25)

### Features

- Add membership feature
  ([`e3a0b5e`](https://github.com/arkitektio/kante/commit/e3a0b5e3fa8457a44bd24b31e480ba43c88720a6))


## v0.14.0 (2025-08-07)

### Features

- Add mutation
  ([`dcb0254`](https://github.com/arkitektio/kante/commit/dcb0254a496dc5eeb0e8d0eb6098306252e93102))


## v0.13.0 (2025-08-07)

### Features

- Add inherit federation support
  ([`f23f3fd`](https://github.com/arkitektio/kante/commit/f23f3fd17b85cd1c9cd30c8f7af8956ece91531b))


## v0.12.1 (2025-07-16)

### Bug Fixes

- Organization inside request
  ([`d431454`](https://github.com/arkitektio/kante/commit/d431454e28fb2c48fbf683d2a2545388bdd4218e))


## v0.12.0 (2025-07-16)

### Features

- Update channel layer handling and add type hints
  ([`36cb81e`](https://github.com/arkitektio/kante/commit/36cb81e14e264f24472cf3408f18e0a000728469))

- Added type hints to channel layer functions in `channel.py`, `path.py`, and `router.py`. - Updated
  `context.py` to use ellipsis for the `is_anonymous` method. - Enhanced `ChannelsLayer` protocol in
  `types.py` with detailed method specifications. - Incremented version to 0.11.0 in `uv.lock`. -
  Created `py.typed` file for type checking support.


## v0.11.0 (2025-07-16)

### Features

- Add organization
  ([`ec35f55`](https://github.com/arkitektio/kante/commit/ec35f55e7ffb9571a2ac1de5a96ed60640b55dda))


## v0.10.1 (2025-07-11)


## v0.10.0 (2025-07-11)

### Bug Fixes

- Add fix for double setting bug in strawberry graphql
  ([`2ea7272`](https://github.com/arkitektio/kante/commit/2ea7272af6ce3c6b93170efd7eb0119332557451))

### Features

- Add schema path option
  ([`4431dd9`](https://github.com/arkitektio/kante/commit/4431dd9f152955b4399ee18e0b50807e629da822))


## v0.9.0 (2025-05-06)

### Bug Fixes

- Update WebSocket path in test_echo_consumer and bump version to 0.8.0
  ([`54c39dc`](https://github.com/arkitektio/kante/commit/54c39dc7a609f4fe32c6a6442df8c82592fef6a6))


## v0.8.0 (2025-05-06)

### Features

- Implement EchoConsumer and add WebSocket testing
  ([`7895403`](https://github.com/arkitektio/kante/commit/7895403bfdc089f4ba6eee5545acd85f8ba77d11))


## v0.7.0 (2025-05-06)

### Features

- Update dependencies for channels and bump version to 0.6.0
  ([`53dd8c9`](https://github.com/arkitektio/kante/commit/53dd8c9de12b4de2dc694a85c0334fe425da86b9))


## v0.6.0 (2025-05-06)

### Features

- Update CORS middleware to include trailers and integrate with ProtocolTypeRouter
  ([`dcaed4c`](https://github.com/arkitektio/kante/commit/dcaed4c3263bdb1a4f12ab7e79c785129a865c3d))


## v0.5.0 (2025-05-06)

### Features

- Simplify ASGI router configuration and update version to 0.4.0
  ([`01c194c`](https://github.com/arkitektio/kante/commit/01c194c63acdf942d862a10550d5b10643fd54de))


## v0.4.0 (2025-05-06)

### Features

- Introduce UniversalRequest for improved request handling in HTTP and WebSocket consumers
  ([`a88d96f`](https://github.com/arkitektio/kante/commit/a88d96f1ddfc6cb7f1ef77c3ec4ca080b35d3a46))

- Update router to support multiple GraphQL URL patterns and add tests for HTTP and WebSocket
  clients
  ([`9c153bc`](https://github.com/arkitektio/kante/commit/9c153bc0677a0f0fd74e181fae5030071eec2931))


## v0.3.0 (2025-05-05)

### Bug Fixes

- Update package versions and remove resolution markers in uv.lock
  ([`5e6f694`](https://github.com/arkitektio/kante/commit/5e6f69476e6a745ddda67ed12ceded32d1722e58))

### Features

- Enhance README with detailed usage examples and subscription features
  ([`b285ed0`](https://github.com/arkitektio/kante/commit/b285ed0e17f15baae20d41fabf7c0ee855fd5060))

- Refactor code structure for improved readability and maintainability
  ([`69ee550`](https://github.com/arkitektio/kante/commit/69ee550c81004da2374484451acfd7be803ef31e))


## v0.2.1 (2025-02-26)
