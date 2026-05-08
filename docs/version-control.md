# Version Control

## Branches

- `main` - stable, reviewable history.
- `develop` - integration branch for product work.
- `feature/<short-topic>` - focused implementation branches.
- `docs/<short-topic>` - documentation-only branches.
- `spike/<short-topic>` - disposable investigation branches.

Default working branch after foundation setup: `develop`.

## Commit Style

Use the Lore protocol when practical:

```text
<why this change exists>

<context, constraints, and approach>

Constraint: <external constraint>
Rejected: <alternative> | <reason>
Confidence: <low|medium|high>
Scope-risk: <narrow|moderate|broad>
Tested: <verification>
Not-tested: <known gap>
```

## Release Tags

Use semantic tags once implementation begins:

- `v0.1.0-foundation`
- `v0.2.0-cli-loop`
- `v0.3.0-revision-loop`
- `v0.4.0-web-preview`

## GitHub Setup

The preferred remote is:

```text
origin = git@github.com:<owner>/open-figure-lab.git
```

HTTPS is acceptable when GitHub CLI is configured for HTTPS.

Recommended GitHub settings after the remote exists:

- protect `main`
- require pull request before merge
- require status checks once CI exists
- disallow force pushes to `main`
- keep issues and discussions enabled for product decisions

