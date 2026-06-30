# Data Contracts

All timestamps are ISO 8601 values with timezone offsets. Monetary values use
numeric CNY amounts. Unknown prices are `null`; they are never inferred.

Every provider returns `provider_id`, `status`, `queried_at`, `records`,
`warnings`, and optional `error_kind`. Every external record contains source
evidence with URL, query time, freshness, and confidence.

## Attraction candidate handoff

After reviewing XHS/Dianping evidence, the agent writes
`attraction_candidates.json`. Each item contains `name`, `description`,
`source_url`, `queried_at`, `suggested_visit_minutes`, and nullable
`ticket_price_cny`. The resolver accepts only these fields and verifies every
location through AMap before creating an `Attraction`.
