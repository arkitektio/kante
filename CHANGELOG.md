# CHANGELOG


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
