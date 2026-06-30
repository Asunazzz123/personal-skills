# Data Contracts

All timestamps are ISO 8601 values with timezone offsets. Monetary values use
numeric CNY amounts. Unknown prices are `null`; they are never inferred.

Every provider returns `provider_id`, `status`, `queried_at`, `records`,
`warnings`, and optional `error_kind`. Every external record contains source
evidence with URL, query time, freshness, and confidence.
