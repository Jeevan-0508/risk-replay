# RISK//REPLAY deployment security

The API does not use wildcard CORS. Set `RISK_REPLAY_ALLOWED_ORIGINS` to a comma-separated list of the exact browser origins that may call the API.

Production deployments must set:

```text
RISK_REPLAY_ENV=production
RISK_REPLAY_API_KEY=<secret from the deployment secret store>
RISK_REPLAY_REQUIRE_API_KEY=true
RISK_REPLAY_ALLOWED_ORIGINS=https://approved.example
```

The `/health` endpoint and CORS preflight remain available without the key. All other routes require the `X-API-Key` header when the guard is enabled. The key is compared in memory and is never written to the database or returned in an API response.

This is an API boundary control, not proof of user identity or authorization. A production deployment still needs a secret manager, rotation, TLS, network policy, operator identity, audit retention, and a review of every mutating route before exposure to untrusted clients. Hashes and replay output continue to establish recorded-byte integrity only; they do not prove source truth.
