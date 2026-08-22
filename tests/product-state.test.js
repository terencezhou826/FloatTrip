const test = require("node:test");
const assert = require("node:assert/strict");

require("../frontend/chat-state.js");
require("../frontend/product-state.js");

test("flattens route data from the backend without a local route list", () => {
  const payload = {
    collections: [{
      package_id: "pkg",
      schema_version: "1.0",
      content_version: "2.0.0",
      region: { id: "region" },
      routes: [
        { id: "route-a", availability: "ready" },
        { id: "route-b", availability: "coming_soon" },
        { id: "route-c", availability: "preview" },
        { id: "route-d", availability: "coming_soon" },
      ],
    }],
  };

  const routes = ProductState.flattenCollections(payload);
  assert.equal(routes.length, 4);
  assert.equal(routes[0].package_id, "pkg");
  assert.equal(routes[0].catalog_version.content_version, "2.0.0");
});

test("allows full generation only when backend capabilities are all ready", () => {
  const capabilities = {
    catalog_available: true,
    planning_available: true,
    knowledge_available: true,
    story_available: true,
    experience_available: true,
    resources_available: true,
  };
  assert.equal(ProductState.canStart({ availability: "ready", capabilities }), true);
  assert.equal(ProductState.canStart({ availability: "coming_soon", capabilities }), false);
  assert.equal(ProductState.canStart({
    availability: "ready",
    capabilities: { ...capabilities, story_available: false },
  }), false);
});

test("renders explicit labels for loading-independent capability states", () => {
  assert.equal(ProductState.availabilityView("ready").cta, "开始体验");
  assert.equal(ProductState.availabilityView("preview").cta, "查看预告");
  assert.equal(ProductState.availabilityView("coming_soon").cta, "敬请期待");
});

test("maps the route form to the existing formal Runtime request", () => {
  const route = {
    id: "route.example",
    package_id: "package.example",
    availability: "ready",
    capabilities: Object.fromEntries([
      "catalog_available", "planning_available", "knowledge_available",
      "story_available", "experience_available", "resources_available",
    ].map(key => [key, true])),
    region_hierarchy: [{ name: "示例省", region_type: "province" }, { name: "示例市", region_type: "prefecture_city" }],
  };
  const request = ProductState.buildTripRequest(route, {
    startDate: "2026-09-10", days: 2, adults: 2, children: 1,
    childAges: "8", pace: "轻松节奏", interests: ["亲子", "文化", "自然"],
    budgetPreference: "均衡舒适",
  });
  assert.equal(request.destination, "示例市");
  assert.equal(request.end_date, "2026-09-11");
  assert.equal(request.package_id, "package.example");
  assert.equal(request.route_id, "route.example");
  assert.match(request.attraction_preference, /2名成人和1名儿童（8岁）/);
});

test("restores waiting_user and ignores duplicate durable events", () => {
  const run = { id: "run-1", status: "running", kind: "travel_plan" };
  const waiting = {
    kind: "custom", sequence: 3,
    payload: { kind: "run.waiting_user", interaction_id: "i-1", question: "确认日期" },
  };
  const restored = ProductState.restoreRun(run, [waiting]);
  assert.equal(restored.run.pending_interaction.interaction_id, "i-1");
  const duplicate = ProductState.applyRunEvent(restored.run, restored.cursor, waiting);
  assert.deepEqual(duplicate, restored);
  assert.equal(ProductState.shouldReconnect("waiting_user"), true);
  assert.equal(ProductState.shouldReconnect("succeeded"), false);
});
