# Use Cases

Zentaizo is for tasks where a single repository is not enough context.

## Q&A across a system

Example:

> Which API endpoint does the web UI call when creating a short link, and does the client library expose the same operation?

The agent should start with `summaries/overview.md`, then inspect the API, frontend, and client repositories only as needed.

## Debugging

Example:

> The web UI says a link was created, but the redirect route returns 404. Where could the mismatch be?

The agent may need to inspect:

- frontend request payload
- API create endpoint
- database model or migration
- redirect handler
- deployment route configuration

## Integrated change planning

Example:

> Add link expiration across the system.

Before editing code, the agent should identify the shared contract:

- API request and response fields
- frontend controls and display states
- client library parameters
- redirect behavior after expiration
- cleanup or deployment jobs, if any
- documentation updates

## Implementation support

After the integrated plan exists, the agent may edit one repository at a time while checking related repositories for compatibility.

Example prompt from inside `shortener-api`:

> Use the Zentaizo context to check frontend and client expectations, then implement the API side of link expiration.

## Reproducible answers

When an answer depends on external code or documents, the agent should cite the locked source versions. This matters when branches move or documentation changes.
