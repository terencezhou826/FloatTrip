# Resource Recommendation

The M5 recommendation engine is deterministic and read-only:

```text
Itinerary + persisted Story/Experience context
  + runtime Provider candidates
  + optional verified Catalog resources
  -> exact identity projection
  -> TravelTimeMatrix / meal detour assessment
  -> deterministic editorial ranking
  -> optional ResourceRecommendation
```

Allowed factors are route feasibility, real distance and detour, itinerary meal identity, user preference, resource type, Provider rating/review count, verified price availability, freshness, and operational status. Missing routing produces `INSUFFICIENT_DATA`; an excessive detour produces `NOT_SUITABLE`.

Commercial relationship, sponsorship, partnership, commission, and commercial amount are never read by the editorial score. Ties are resolved by status, score, Provider, and external ID, so input order cannot change ranking.

Recommendations expose machine-readable reasons such as `selected_meal`, `near_itinerary_stop`, `low_detour`, `meal_time_match`, and `price_data_available`. They do not claim "best", "must eat", authenticity, history, or cultural identity without separate Evidence.

Story Chapter and Experience Activity links are contextual relations only. Recommendation does not edit narration or Activity instructions, require a purchase, or force an itinerary change. Every recommendation validates with `optional=true`.
