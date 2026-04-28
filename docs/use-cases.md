# Use Cases

Zentaizo is for tasks where a single repository is not enough context.

## Q&A Across A System

Example:

> Which API endpoint does the web UI call when creating a short link, and does the client library expose the same operation?

The assistant should start with `summaries/overview.md`, then inspect the API, frontend, and client repositories only as needed.

## Debugging

Example:

> The web UI says a link was created, but the redirect route returns 404. Where could the mismatch be?

The assistant may need to inspect:

- frontend request payload
- API create endpoint
- database model or migration
- redirect handler
- deployment route configuration

## Integrated Change Planning

Example:

> Add link expiration across the system.

Before editing code, the assistant should identify the shared contract:

- API request and response fields
- frontend controls and display states
- client library parameters
- redirect behavior after expiration
- cleanup or deployment jobs, if any
- documentation updates

## Implementation Support

After the integrated plan exists, the assistant may edit one repository at a time while checking related repositories for compatibility.

Example prompt from inside `shortener-api`:

> Use the Zentaizo context to check frontend and client expectations, then implement the API side of link expiration.

## Reproducible Answers

When an answer depends on external code or documents, the assistant should cite the locked source versions. This matters when branches move or documentation changes.
