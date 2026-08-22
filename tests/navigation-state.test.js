const test = require("node:test");
const assert = require("node:assert/strict");

require("../frontend/navigation-state.js");

test("restores a protected chat target after authentication", () => {
  const target = NavigationState.chatTarget();
  assert.deepEqual(NavigationState.resolveAfterAuth(target), {
    page: "chat",
  });
});

test("rejects incomplete detail targets and closed authentication state", () => {
  assert.equal(NavigationState.resolveAfterAuth(null), null);
  assert.equal(NavigationState.resolveAfterAuth({ page: "detail" }), null);
  assert.deepEqual(
    NavigationState.resolveAfterAuth(NavigationState.detailTarget("plan-1")),
    { page: "detail", planId: "plan-1" },
  );
});

test("parses product routes without route-specific branches", () => {
  assert.deepEqual(NavigationState.routeFromPath("/"), { page: "home" });
  assert.deepEqual(NavigationState.routeFromPath("/myth-journeys"), { page: "journeys" });
  assert.deepEqual(
    NavigationState.routeFromPath("/myth-journeys/route.example"),
    { page: "journey", routeId: "route.example" },
  );
  assert.deepEqual(
    NavigationState.routeFromPath("/my-trips/run.example"),
    { page: "trip", runId: "run.example" },
  );
});
