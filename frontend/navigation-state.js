// navigation-state.js — 可测试的认证后目标与对话入口规则

(function (global) {
  function chatTarget() {
    return { page: "chat" };
  }

  function detailTarget(planId) {
    return planId ? { page: "detail", planId } : null;
  }

  function resolveAfterAuth(target) {
    if (!target || !["chat", "detail"].includes(target.page)) return null;
    if (target.page === "detail" && !target.planId) return null;
    return { ...target };
  }

  function routeFromPath(pathname) {
    const path = String(pathname || "/").replace(/\/+$/, "") || "/";
    if (path === "/") return { page: "home" };
    if (path === "/myth-journeys") return { page: "journeys" };
    if (path.startsWith("/myth-journeys/")) {
      return { page: "journey", routeId: decodeURIComponent(path.slice(15)) };
    }
    if (path.startsWith("/my-trips/")) {
      return { page: "trip", runId: decodeURIComponent(path.slice(10)) };
    }
    if (path === "/profile") return { page: "profile" };
    if (path === "/history") return { page: "history" };
    return { page: "chat" };
  }

  function pathForPage(page) {
    return ({ home: "/", journeys: "/myth-journeys", chat: "/chat", history: "/history", profile: "/profile" })[page] || "/";
  }

  global.NavigationState = {
    chatTarget,
    detailTarget,
    resolveAfterAuth,
    routeFromPath,
    pathForPage,
  };
})(typeof window === "undefined" ? globalThis : window);
