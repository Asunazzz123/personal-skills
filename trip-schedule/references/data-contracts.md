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

## Restaurant candidate handoff

Restaurant ranking is intentionally independent from crawlers and transport
providers. The agent reviews sourced dining evidence, then passes structured
`RestaurantCandidate` objects to `planning.restaurant_scoring`. Each candidate
must contain:

- `name`: restaurant name from sourced evidence.
- `area`: human-readable district or route segment, such as `珠江新城` or
  `江南西`.
- `cuisine_tags`: normalized tags such as `西餐`, `高端粤菜`, `日料`, or
  `酒馆`.
- `average_cost_cny`: per-person budget when evidence gives one; use `null`
  if unknown.
- `reputation_score`: 0-1 score derived from sourced engagement, review count,
  or agent-assessed evidence quality.
- `detour_minutes`: estimated route detour compared with the planned path.
- `distance_to_nearest_metro_meters`: required when the next movement is by
  metro; use `null` if unknown.
- `transit_minutes_to_next_anchor`: minutes to the next fixed anchor by transit,
  such as a station or timed attraction.
- `taxi_minutes_to_next_anchor`: minutes to the next fixed anchor by taxi.
- `arrival_buffer_minutes`: remaining safety buffer at the next fixed anchor,
  such as a high-speed rail departure, after leaving this restaurant.
- `evidence_urls`: one or more source URLs supporting the candidate.
- `notes`: short sourced notes useful for final explanation.

The scorer applies budget, cuisine preference, route fit, transport-mode
convenience, and arrival-buffer viability. It must not import crawler wrappers,
Xiaohongshu providers, 12306 providers, or AMap clients. Provider-specific logic
stays upstream in evidence collection and route estimation.
