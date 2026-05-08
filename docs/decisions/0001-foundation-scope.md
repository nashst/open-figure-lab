# Decision 0001: Foundation Scope

## Status

Accepted

## Decision

Start Open Figure Lab as a dependency-light Python CLI plus durable product/agent documentation.

## Rationale

The product concept is strong but still early. The first risk is not UI polish; it is unstable scope, fabricated data paths, and agents losing context across threads.

The foundation phase therefore fixes:

- product boundary
- repository structure
- collaboration memory
- minimal executable CLI
- version control rules

## Consequences

- The web UI is postponed until the CLI figure package loop is credible.
- Third-party plotting and YAML dependencies are documented but not added yet.
- `figure.yaml` remains the product-facing target, while bootstrap CLI may create dependency-free templates.

Constraint: No new runtime dependencies during foundation setup.
Rejected: Start with a full Next.js app | premature before CLI loop and spec contracts are stable.
Rejected: Add matplotlib/PyYAML immediately | useful soon, but should be introduced with the first renderer and schema tests.
Confidence: high
Scope-risk: narrow

