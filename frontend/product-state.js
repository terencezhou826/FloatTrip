// product-state.js — 可测试的 Catalog 产品可用性与路由规则

(function (global) {
  const STATUS = {
    ready: { label: "完整体验可用", cta: "开始体验" },
    preview: { label: "内容预览", cta: "查看预告" },
    coming_soon: { label: "即将开放", cta: "敬请期待" },
  };

  function availabilityView(status) {
    return STATUS[status] || STATUS.coming_soon;
  }

  function canStart(route) {
    return route?.availability === "ready"
      && Object.values(route.capabilities || {}).every(Boolean);
  }

  function flattenCollections(payload) {
    return (payload?.collections || []).flatMap(collection =>
      (collection.routes || []).map(route => ({
        ...route,
        package_id: collection.package_id,
        catalog_version: {
          schema_version: collection.schema_version,
          content_version: collection.content_version,
        },
        collection_region: collection.region,
      }))
    );
  }

  function isoDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function buildTripRequest(route, form) {
    if (!canStart(route)) throw new Error("route_not_ready");
    const start = new Date(`${form.startDate}T12:00:00`);
    if (Number.isNaN(start.valueOf())) throw new Error("invalid_start_date");
    const days = Math.max(1, Number(form.days || 1));
    const end = new Date(start);
    end.setDate(end.getDate() + days - 1);
    const city = [...(route.region_hierarchy || [])]
      .reverse()
      .find(region => region.region_type === "prefecture_city");
    if (!city) throw new Error("missing_prefecture_city");
    const adults = Math.max(1, Number(form.adults || 1));
    const children = Math.max(0, Number(form.children || 0));
    const ages = children && form.childAges ? `（${form.childAges}岁）` : "";
    const party = `${adults}名成人${children ? `和${children}名儿童${ages}` : ""}`;
    const interests = (form.interests || []).join("、") || "文化、自然";
    return {
      destination: city.name,
      days,
      start_date: form.startDate,
      end_date: isoDate(end),
      attraction_preference: `${interests}；${party}`,
      food_preference: children ? "适合家庭用餐" : "无特殊要求",
      habit_preference: form.pace || "轻松节奏",
      ...(form.budgetPreference ? { trip_budget: form.budgetPreference } : {}),
      package_id: route.package_id,
      route_id: route.id,
    };
  }

  function restoreRun(run, events) {
    let state = ChatState.initialState();
    state.runs[run.id] = run;
    for (const event of events || []) state = ChatState.applyEvent(state, run.id, event);
    return { run: state.runs[run.id], cursor: state.cursors[run.id] || 0 };
  }

  function applyRunEvent(run, cursor, event) {
    const state = ChatState.initialState();
    state.runs[run.id] = run;
    state.cursors[run.id] = Number(cursor || 0);
    const next = ChatState.applyEvent(state, run.id, event);
    return { run: next.runs[run.id], cursor: next.cursors[run.id] || 0 };
  }

  function shouldReconnect(status) {
    return ["queued", "running", "waiting_user"].includes(status);
  }

  global.ProductState = {
    STATUS, availabilityView, canStart, flattenCollections,
    buildTripRequest, restoreRun, applyRunEvent, shouldReconnect,
  };
})(typeof window === "undefined" ? globalThis : window);
