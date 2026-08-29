# Security Policy

SENTINEL is a reference implementation / portfolio project, currently
configured for local development and demonstration only -- see
`README.md`'s "Security / deployment caveats" section for the specific,
current gaps (open CORS, no API authentication, local-dev default
credentials). None of that is production security hardening, and none of
it is presented as such.

## Reporting a vulnerability

If you find a security issue in this repository, please open a GitHub
issue or contact the repository owner directly rather than a public pull
request, so any fix can be reviewed before the details are made public.

## Scope

This policy covers the code in this repository. It does not cover
third-party services this project can optionally integrate with (Gemini,
a Kafka broker, Redis, PostgreSQL, Neo4j, Qdrant) -- report issues in
those to their own maintainers.
