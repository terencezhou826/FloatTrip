# Local Resource Model

M5 keeps four domains separate:

- Knowledge records reviewed cultural facts and Evidence.
- Story presents only evidence-grounded cultural narrative.
- Experience defines optional visitor interaction under safety rules.
- Local Resource describes a real merchant, product, service, ticket, event, or paid experience.

`LocalResource` is long-term curated Catalog data. `RuntimeResourceCandidate` is a short-lived Provider result. A runtime candidate never becomes a verified Catalog resource automatically.

## Identity

Map entities use the exact pair `provider + external_poi_id`. A name is display data, not identity. Internally recorded local, agricultural, and cultural products may omit a map binding only when they retain a stable Resource ID and verified provenance.

Verification and operation are independent. `verified` confirms identity and provenance; it does not mean the resource is open now. Operational states include `unknown`, `open`, `temporarily_closed`, `seasonal`, `appointment_required`, and `inactive`.

## Eligibility

`is_resource_recommendation_eligible()` requires verified identity/provenance, editorial approval, a valid date window, a non-inactive operational state, and valid commercial disclosure. Rejected, expired, inactive, name-only, and unresolved resources cannot enter curated production recommendation.

All M5 recommendations remain optional. A resource never becomes a mandatory Anchor or itinerary stop.
