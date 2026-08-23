// product-pages.jsx — Catalog 驱动的主题文旅页面

const CAPABILITY_LABELS = {
  catalog_available: "线路资料",
  planning_available: "真实行程",
  knowledge_available: "文化知识",
  story_available: "主题故事",
  experience_available: "现场互动",
  resources_available: "沿途资源",
};

function ProductHomePage({ onExplore, onPlan }) {
  return (
    <main className="product-home page-fade">
      <section className="product-hero" aria-labelledby="product-home-title">
        <div className="product-hero-lines" aria-hidden="true"><i></i><i></i><i></i></div>
        <div className="product-hero-copy">
          <p className="product-kicker">山西主题文旅 · 长治首期</p>
          <h1 id="product-home-title">跟着山海经<br />游长治</h1>
          <p className="product-lede">从真实地点出发，在一日行程里听见故事、完成亲子互动，也看清沿途可选的本地资源。</p>
          <div className="product-actions">
            <button className="product-primary" onClick={onExplore}>查看四条主题线路 <span aria-hidden="true">→</span></button>
            <button className="product-secondary" onClick={onPlan}>规划其他旅行</button>
          </div>
        </div>
        <div className="product-seal" aria-hidden="true"><span>长治</span><b>四境</b></div>
      </section>
      <section className="product-home-next" aria-label="体验层次">
        <span>去哪</span><span>为什么来</span><span>到了做什么</span><span>顺路有什么</span>
      </section>
    </main>
  );
}

function ProductStatus({ availability }) {
  const view = ProductState.availabilityView(availability);
  return <span className={`product-status status-${availability || "coming_soon"}`}>{view.label}</span>;
}

function CapabilityList({ capabilities, compact = false }) {
  return (
    <ul className={`capability-chips${compact ? " compact" : ""}`} aria-label="当前可用能力">
      {Object.entries(CAPABILITY_LABELS).map(([key, label]) => (
        <li key={key} className={capabilities?.[key] ? "available" : "unavailable"}>
          <span aria-hidden="true">{capabilities?.[key] ? "✓" : "○"}</span>{label}
        </li>
      ))}
    </ul>
  );
}

function RouteCard({ route, onOpen }) {
  const primaryAnchor = route.anchors?.find(item => item.mandatory) || route.anchors?.[0];
  const status = ProductState.availabilityView(route.availability);
  return (
    <article className="journey-card">
      <div className="journey-card-top">
        <ProductStatus availability={route.availability} />
        <span className="journey-theme">{route.theme?.name || "主题线路"}</span>
      </div>
      <h2>{route.name}</h2>
      {route.capabilities?.spatial_resolution && <p className={`spatial-status${route.capabilities.spatial_degraded ? " degraded" : ""}`}>{ProductState.spatialView(route.capabilities.spatial_resolution)}</p>}
      <dl className="journey-meta">
        <div><dt>区域</dt><dd>{route.primary_region?.name || "未提供"}</dd></div>
        <div><dt>核心地点</dt><dd>{primaryAnchor?.name || "未提供"}</dd></div>
      </dl>
      <CapabilityList capabilities={route.capabilities} compact />
      <button className="journey-card-cta" onClick={() => onOpen(route)}>
        {route.availability === "coming_soon" ? "查看预告" : status.cta}<span aria-hidden="true">→</span>
      </button>
    </article>
  );
}

function CatalogLoadState({ kind, onRetry }) {
  if (kind === "loading") return <div className="product-state" role="status"><span className="state-loader"></span><h2>正在读取主题线路</h2><p>从已验证的 Catalog 加载最新内容。</p></div>;
  if (kind === "empty") return <div className="product-state"><h2>暂无线路</h2><p>当前区域还没有已启用的主题线路。</p></div>;
  return <div className="product-state" role="alert"><h2>线路暂时无法加载</h2><p>没有使用备用或模拟数据。</p><button onClick={onRetry}>重新加载</button></div>;
}

function MythJourneysPage({ onOpen, onHome }) {
  const [state, setState] = React.useState({ kind: "loading", payload: null });
  const load = React.useCallback(() => {
    setState({ kind: "loading", payload: null });
    getProductCollections().then(payload => {
      const routes = ProductState.flattenCollections(payload);
      setState({ kind: routes.length ? "ready" : "empty", payload, routes });
    }).catch(error => setState({ kind: "error", error }));
  }, []);
  React.useEffect(load, [load]);
  if (state.kind !== "ready") return <main className="journeys-page"><CatalogLoadState kind={state.kind} onRetry={load} /></main>;
  const collection = state.payload.collections[0];
  return (
    <main className="journeys-page page-fade">
      <header className="journeys-header">
        <button className="text-back" onClick={onHome}>← 返回首页</button>
        <p className="product-kicker">{collection.region.name} · Catalog {collection.content_version}</p>
        <h1>四条主题线路</h1>
        <p>每条线路的开放状态来自后端真实能力。内容尚未完备的线路可以预览，但不会启动完整旅程。</p>
      </header>
      <section className="journey-grid" aria-label="主题线路列表">
        {state.routes.map(route => <RouteCard key={route.id} route={route} onOpen={onOpen} />)}
      </section>
    </main>
  );
}

function ThemeRoutePreviewPage({ routeId, onBack, onStart, currentUsername, onRequestLogin }) {
  const [state, setState] = React.useState({ kind: "loading" });
  const [creating, setCreating] = React.useState(false);
  const [createError, setCreateError] = React.useState("");
  const creatingRef = React.useRef(false);
  const load = React.useCallback(() => {
    setState({ kind: "loading" });
    getProductRoute(routeId)
      .then(route => setState({ kind: "ready", route }))
      .catch(error => setState({ kind: error.message?.includes("不存在") ? "missing" : "error", error }));
  }, [routeId]);
  React.useEffect(load, [load]);
  if (state.kind !== "ready") {
    if (state.kind === "missing") return <main className="journeys-page"><div className="product-state"><h1>没有找到这条线路</h1><button onClick={onBack}>返回线路列表</button></div></main>;
    return <main className="journeys-page"><CatalogLoadState kind={state.kind} onRetry={load} /></main>;
  }
  const route = state.route;
  const ready = ProductState.canStart(route);
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const defaultDate = tomorrow.toISOString().slice(0, 10);
  const submitTrip = async (event) => {
    event.preventDefault();
    if (creatingRef.current || !ready) return;
    if (!currentUsername) { onRequestLogin?.(); return; }
    const data = new FormData(event.currentTarget);
    const form = {
      startDate: data.get("start_date"),
      adults: data.get("adults"),
      children: data.get("children"),
      childAges: data.get("child_ages"),
      days: data.get("days"),
      budgetPreference: data.get("budget_preference"),
      pace: data.get("pace"),
      interests: data.getAll("interests"),
    };
    creatingRef.current = true;
    setCreating(true);
    setCreateError("");
    try {
      await onStart(route, ProductState.buildTripRequest(route, form));
    } catch (error) {
      creatingRef.current = false;
      setCreating(false);
      setCreateError(error.message || "旅程暂时无法创建");
    }
  };
  return (
    <main className="route-preview-page page-fade">
      <button className="text-back" onClick={onBack}>← 返回四条线路</button>
      <header className="route-preview-head">
        <div>
          <ProductStatus availability={route.availability} />
          <p className="product-kicker">{route.region_hierarchy?.map(item => item.name).join(" · ")}</p>
          <h1>{route.name}</h1>
          <p className="route-intro">围绕 {route.anchors?.map(item => item.name).join("、")} 展开的策展主题线路。文化预览仅展示已有证据支持、可用于生产的 Catalog 内容。</p>
          {route.capabilities?.spatial_resolution && <p className={`spatial-status${route.capabilities.spatial_degraded ? " degraded" : ""}`}>{ProductState.spatialView(route.capabilities.spatial_resolution)}</p>}
        </div>
        <div className="route-anchor-mark"><span>主题</span><strong>{route.theme?.name}</strong></div>
      </header>
      <section className="route-preview-grid">
        <div className="route-preview-main">
          <h2>核心地点</h2>
          {(route.anchors || []).map(anchor => <div className="anchor-row" key={anchor.id}><strong>{anchor.name}</strong>{anchor.mandatory && <span>策展核心地点</span>}</div>)}
          {(route.location_disclosures || []).map((text, index) => <div className="location-disclosure" role="note" key={index}><strong>位置说明</strong><p>{text}</p></div>)}
          <h2>文化预览</h2>
          {(route.cultural_preview || []).length ? route.cultural_preview.map(item => (
            <article className="preview-claim" key={item.claim_id}>
              <p>{item.text}</p>
              {item.required_qualifier && <p className="claim-qualifier">说明：{item.required_qualifier}</p>}
              {!!item.citations?.length && <details><summary>资料来源</summary>{item.citations.map(citation => <p key={citation.source_id}>{citation.source_title}</p>)}</details>}
            </article>
          )) : <p className="empty-copy">当前暂无可公开展示的文化预览。</p>}
        </div>
        <aside className="route-capability-panel">
          <h2>当前体验状态</h2>
          <CapabilityList capabilities={route.capabilities} />
          {ready ? (
            <form className="trip-create-form" onSubmit={submitTrip}>
              <h3>开始我的旅程</h3>
              <label>出发日期<input type="date" name="start_date" min={defaultDate} defaultValue={defaultDate} required /></label>
              <div className="form-pair">
                <label>成人数<input type="number" name="adults" min="1" max="20" defaultValue="2" required /></label>
                <label>儿童数<input type="number" name="children" min="0" max="10" defaultValue="1" required /></label>
              </div>
              <label>儿童年龄（可选）<input name="child_ages" inputMode="numeric" placeholder="例如：8" /></label>
              <label>时长<select name="days" defaultValue="1"><option value="1">1 天</option><option value="2">2 天</option><option value="3">3 天</option></select></label>
              <label>预算偏好<select name="budget_preference" defaultValue=""><option value="">暂不限定</option><option value="经济实用">经济实用</option><option value="均衡舒适">均衡舒适</option><option value="品质优先">品质优先</option></select></label>
              <label>旅行节奏<select name="pace" defaultValue="轻松节奏"><option>轻松节奏</option><option>适中节奏</option><option>紧凑节奏</option></select></label>
              <fieldset><legend>兴趣偏好</legend><label><input type="checkbox" name="interests" value="亲子" defaultChecked />亲子</label><label><input type="checkbox" name="interests" value="文化" defaultChecked />文化</label><label><input type="checkbox" name="interests" value="自然" defaultChecked />自然</label></fieldset>
              {createError && <p className="form-inline-error" role="alert">{createError}</p>}
              <button className="product-primary" disabled={creating}>{creating ? "正在创建…" : currentUsername ? "创建正式旅程" : "登录后创建旅程"}</button>
            </form>
          ) : (
            <div className="coming-notice"><strong>完整体验尚未开放</strong><p>你可以查看基础线路资料；正式规划不会被启动。</p></div>
          )}
        </aside>
      </section>
    </main>
  );
}

function ProductRunProgress({ run }) {
  const index = Math.max(0, Number(run?.journey_step_index ?? 0));
  return (
    <section className="product-run-progress" aria-live="polite">
      <ProductStatus availability={run?.status === "succeeded" ? "ready" : "preview"} />
      <h1>{run?.status === "waiting_user" ? "旅程需要你确认" : run?.status === "succeeded" ? "行程已经准备好" : "正在准备你的主题旅程"}</h1>
      {!["succeeded", "failed", "cancelled", "waiting_user"].includes(run?.status) && (
        <JourneyLoading steps={JOURNEY_STEPS} activeNode={JOURNEY_STEPS[index]?.key} doneNodes={JOURNEY_STEPS.slice(0, index).map(item => item.key)} />
      )}
      <p>{run?.latest_progress_label || ChatState.RUN_PRESENTATIONS[run?.status]?.copy}</p>
    </section>
  );
}

function ProductItinerarySection({ itinerary, username }) {
  const plan = adaptPlan({ ...itinerary.plan, plan_id: itinerary.id }, username);
  const [dayIndex, setDayIndex] = React.useState(0);
  const day = plan.days[dayIndex];
  if (!day) return <div className="package-empty"><h2>行程暂无日程</h2><p>正式 itinerary 已存在，但没有可展示的时间轴。</p></div>;
  return (
    <section className="trip-layer itinerary-layer" aria-labelledby="itinerary-title">
      <div className="layer-heading"><div><p>去哪</p><h2 id="itinerary-title">今日路线</h2></div><span>{plan.destination} · {plan.date_range}</span></div>
      {plan.weather.length > 0 && <div className="product-weather">{plan.weather.map((item, index) => <div key={index}><strong>{item.day}</strong><span>{item.icon} {item.text}</span><span>{item.lo}°–{item.hi}°</span></div>)}</div>}
      {plan.days.length > 1 && <div className="product-day-tabs">{plan.days.map((item, index) => <button key={index} className={index === dayIndex ? "active" : ""} onClick={() => setDayIndex(index)}>Day {index + 1}<span>{item.date}</span></button>)}</div>}
      <div className="product-itinerary-grid">
        <ol className="product-timeline">
          {day.items.map((item, index) => (
            <li key={`${item.type}-${index}`} className={item.type === "attraction" ? "stop-attraction" : "stop-meal"}>
              <div className="timeline-time">{item.start || (item.type === "lunch" ? "午餐" : item.type === "dinner" ? "晚餐" : "")}</div>
              <div className="timeline-content">
                <div className="timeline-title"><h3>{item.name || "该时段暂无可靠餐饮"}</h3>{item.isMandatory && <span className="mandatory-badge">主题核心地点</span>}{item.spatialLocationLabel && <span className="mandatory-badge">{item.spatialLocationLabel}</span>}</div>
                {item.end && <p className="timeline-meta">{item.start}–{item.end}</p>}
                {item.roadDistanceKm != null && <p className="road-metric">驾车道路距离 {Number(item.roadDistanceKm).toFixed(1)} km{item.drivingMinutes != null ? ` · 约 ${Number(item.drivingMinutes).toFixed(1)} 分钟` : ""}</p>}
                {item.address || item.addr ? <p className="timeline-meta">{item.address || item.addr}</p> : null}
                {item.locationDisclosure && <div className="location-disclosure" role="note"><strong>位置说明</strong><p>{item.locationDisclosure}</p></div>}
                {item.note && <p className="spot-tip">出行提示：{item.note}</p>}
                {item.reason && <p className="resource-reason">{item.reason}</p>}
                {item.mealCoverageNote && <p className="unknown-note">{item.mealCoverageNote}</p>}
              </div>
            </li>
          ))}
        </ol>
        <div className="product-map-wrap"><MapPanel day={day} dayIdx={dayIndex} /></div>
      </div>
      {plan.tips.length > 0 && <div className="trip-notices"><strong>天气与路线提示</strong><ul>{plan.tips.map((tip, index) => <li key={index}>{tip}</li>)}</ul></div>}
    </section>
  );
}

function CitationDetails({ citations }) {
  if (!citations?.length) return null;
  return (
    <details className="citation-details">
      <summary>查看资料来源（{citations.length}）</summary>
      {citations.map(citation => (
        <article key={`${citation.evidence_id}-${citation.claim_id}`}>
          <strong>{citation.source_title}</strong>
          <p>{citation.quote_excerpt}</p>
          <div className="citation-meta"><span>{citation.claim_type}</span>{citation.locator?.chapter && <span>{citation.locator.chapter}</span>}{citation.locator?.paragraph && <span>段落 {citation.locator.paragraph}</span>}</div>
          {citation.required_qualifier && <p className="claim-qualifier">限定说明：{citation.required_qualifier}</p>}
          {citation.url && <a href={citation.url} target="_blank" rel="noreferrer">打开来源</a>}
        </article>
      ))}
    </details>
  );
}

function ProductStorySection({ snapshot, onRetry }) {
  if (snapshot.status !== "available") return <PackageStageState layer="story" snapshot={snapshot} onRetry={onRetry} />;
  const story = snapshot.package;
  const bindingByChapter = Object.fromEntries((story.chapter_bindings || []).map(item => [item.chapter_id, item]));
  return (
    <section className="trip-layer story-layer" aria-labelledby="story-title" data-package-id={story.package_id} data-snapshot-hash={snapshot.snapshot_hash}>
      <div className="layer-heading"><div><p>为什么来</p><h2 id="story-title">神话故事</h2></div><span>{story.chapters.length} 章 · {story.audience}</span></div>
      <div className="story-chapters">
        {story.chapters.map((chapter, index) => {
          const binding = bindingByChapter[chapter.chapter_id];
          return <article className="story-chapter" key={chapter.chapter_id}>
            <div className="chapter-index">{String(index + 1).padStart(2, "0")}</div>
            <div><div className="chapter-meta"><span>{binding?.trigger_hint || "journey"}</span><span>{binding?.recommended_playback_duration ? `${Math.ceil(binding.recommended_playback_duration / 60)} 分钟` : ""}</span></div><h3>{chapter.title}</h3><div className="chapter-narration">{chapter.narration || [chapter.opening_text, ...(chapter.factual_content || []).map(item => item.text), chapter.transition_text, chapter.closing_text].filter(Boolean).join("\n")}</div>{chapter.qualifiers_used?.map(value => <p className="qualifier-visible" key={value}>{value}</p>)}<p className="chapter-takeaway"><strong>带走一个想法</strong>{chapter.visitor_takeaway}</p><CitationDetails citations={chapter.citations} /></div>
          </article>;
        })}
      </div>
    </section>
  );
}

function ProductExperienceSection({ snapshot, onRetry }) {
  if (snapshot.status !== "available") return <PackageStageState layer="experience" snapshot={snapshot} onRetry={onRetry} />;
  const experience = snapshot.package;
  const bindingByActivity = Object.fromEntries((experience.activity_bindings || []).map(item => [item.activity_id, item]));
  return (
    <section className="trip-layer experience-layer" aria-labelledby="experience-title" data-package-id={experience.package_id} data-snapshot-hash={snapshot.snapshot_hash}>
      <div className="layer-heading"><div><p>到了做什么</p><h2 id="experience-title">现场互动</h2></div><span>{experience.activities.length} 项 · 约 {Math.ceil(experience.activities.reduce((sum, item) => sum + Number(item.estimated_duration_sec || 0), 0) / 60)} 分钟</span></div>
      <div className="experience-list">
        {experience.activities.map((activity, index) => {
          const binding = bindingByActivity[activity.activity_id];
          return <article className="experience-item" key={activity.activity_id}>
            <div className="experience-number">{index + 1}</div>
            <div><div className="chapter-meta"><span>{binding?.trigger_hint || "现场"}</span><span>{Math.ceil(activity.estimated_duration_sec / 60)} 分钟</span></div><h3>{activity.title}</h3>{activity.observation_text && <p className="trusted-observation"><strong>观察目标</strong>{activity.observation_text}</p>}<p>{activity.instruction}</p><div className="activity-prompt"><strong>请想一想</strong>{activity.prompt}</div>{activity.optional_hint && <p className="activity-hint">提示：{activity.optional_hint}</p>}<div className="safety-notice"><strong>安全提示</strong>{activity.safety_notice}</div><p className="completion-mode">完成方式：{activity.visitor_output_type} · 可选择跳过</p><CitationDetails citations={activity.citations} /></div>
          </article>;
        })}
      </div>
    </section>
  );
}

function formatResourcePrice(price) {
  if (!price || price.price_status === "unknown") return "价格未知";
  if (price.price_status === "free") return "免费";
  if (price.price_status === "range") return `${price.min_amount}–${price.max_amount} ${price.currency || ""}`;
  return `${price.amount} ${price.currency || ""}${price.unit === "person" ? "/人" : ""}`;
}

function ProductResourcesSection({ snapshot, onRetry }) {
  if (snapshot.status !== "available") return <PackageStageState layer="resources" snapshot={snapshot} onRetry={onRetry} />;
  const resources = snapshot.package;
  if (snapshot.empty) return <PackageEmpty title="当前没有已验证的附近资源" copy="Provider 查询已完成，没有符合当前真实性与绕行规则的推荐。" />;
  const candidates = Object.fromEntries((resources.resources || []).map(item => [item.resource_id, item]));
  return (
    <section className="trip-layer resources-layer" aria-labelledby="resources-title" data-package-id={resources.resource_package_id} data-snapshot-hash={snapshot.snapshot_hash}>
      <div className="layer-heading"><div><p>顺路有什么</p><h2 id="resources-title">附近资源</h2></div><span>{resources.recommendations.length} 个可选推荐</span></div>
      <p className="resource-boundary">以下资源均为可选信息，不影响行程、故事或互动体验。实时营业状态请在出发前再次确认。</p>
      <div className="resource-list">
        {resources.recommendations.map(recommendation => {
          const candidate = candidates[recommendation.resource_id] || {};
          return <article className="resource-item" key={recommendation.resource_id}>
            <div className="resource-item-head"><div><span>{recommendation.resource_type}</span><h3>{recommendation.name}</h3></div><span className="optional-badge">可选</span></div>
            <p>{recommendation.match_reasons.map(reason => reason.replaceAll("_", " ")).join(" · ")}</p>
            <dl className="resource-facts"><div><dt>道路总路程</dt><dd>{recommendation.distance_m == null ? "未知" : `${(recommendation.distance_m / 1000).toFixed(1)} km`}</dd></div><div><dt>相比原路线额外绕行</dt><dd>{recommendation.detour_minutes == null ? "未知" : `${recommendation.detour_minutes.toFixed(1)} 分钟`}</dd></div><div><dt>价格</dt><dd>{formatResourcePrice(recommendation.price_info)}</dd></div><div><dt>营业状态</dt><dd>{recommendation.operational_status === "unknown" ? "未知" : recommendation.operational_status}</dd></div><div><dt>数据新鲜度</dt><dd>{recommendation.resource_freshness || candidate.freshness_status || "未知"}</dd></div><div><dt>身份状态</dt><dd>{candidate.verification_status === "candidate" ? "Provider 候选" : candidate.verification_status || "未知"}</dd></div></dl>
            {recommendation.commercial_relationship === "partner" || recommendation.commercial_relationship === "sponsored" ? <p className="commercial-disclosure">{recommendation.disclosure}</p> : <p className="commercial-neutral">商业关系：{recommendation.commercial_relationship === "unknown" ? "未知，非合作标识" : recommendation.commercial_relationship}</p>}
          </article>;
        })}
      </div>
    </section>
  );
}

function PackageEmpty({ title, copy = "页面不会使用临时内容或在浏览器中重新生成。" }) {
  return <div className="package-empty"><h2>{title}</h2><p>{copy}</p></div>;
}

function PackageStageState({ layer, snapshot, onRetry }) {
  const messages = {
    story: {
      pending: ["等待生成故事", "行程已经可用，主题故事正在排队。"],
      generating: ["正在生成你的主题故事…", "故事会经过资料、引文和限定语校验。"],
      failed: ["故事生成未完成", snapshot.message || "已保留正式行程，可以显式重试。"],
      blocked: ["故事生成暂时受阻", "请先处理上游生成问题。"],
    },
    experience: {
      pending: ["互动将在主题故事完成后生成", "系统会在故事快照完成后继续。"],
      generating: ["正在准备现场互动…", "互动内容正在通过安全与位置真实性校验。"],
      failed: ["互动生成未完成", snapshot.message || "故事仍然可用，可以显式重试互动。"],
      blocked: ["互动将在主题故事完成后生成", "上游故事未完成，系统不会伪造互动内容。"],
    },
    resources: {
      pending: ["等待核验沿途资源", "系统将在故事与互动完成后继续。"],
      generating: ["正在核验沿途资源…", "只会展示具有 Provider 身份的可选资源。"],
      failed: ["附近资源暂时无法核验", snapshot.message || "行程、故事和互动仍然可用。"],
      blocked: ["附近资源核验尚未开始", "上游产品层未完成。"],
      skipped: ["本线路暂未提供附近资源推荐", "其它旅程内容不受影响。"],
      not_applicable: ["本线路暂未提供附近资源推荐", "其它旅程内容不受影响。"],
    },
  };
  const [title, copy] = messages[layer]?.[snapshot.status] || ["内容尚未生成", "页面不会使用临时内容。"];
  return <div className="package-empty" data-stage={layer} data-status={snapshot.status}><h2>{title}</h2><p>{copy}</p>{snapshot.status === "failed" && <button className="product-primary" onClick={onRetry}>重试未完成阶段</button>}</div>;
}

function FulfillmentProgress({ data }) {
  const label = status => status === "available" ? "✓" : ["failed", "blocked"].includes(status) ? "!" : ["skipped", "not_applicable"].includes(status) ? "–" : "…";
  return <div className="fulfillment-progress" aria-live="polite"><strong>{ProductState.isFulfillmentTerminal(data) ? "主题旅程内容已处理完成" : "行程已准备好，正在生成故事与互动"}</strong><div><span>Planning ✓</span><span>Story {label(data.story.status)}</span><span>Experience {label(data.experience.status)}</span><span>Resources {label(data.resources.status)}</span></div></div>;
}

function ProductTripExperience({ runId, username }) {
  const [state, setState] = React.useState({ kind: "loading" });
  const [tab, setTab] = React.useState("itinerary");
  const load = React.useCallback((silent = false) => {
    if (!silent) setState({ kind: "loading" });
    getProductTrip(runId).then(data => setState({ kind: "ready", data })).catch(error => setState({ kind: "error", error }));
  }, [runId]);
  React.useEffect(() => { load(false); }, [load]);
  React.useEffect(() => {
    if (state.kind !== "ready" || !ProductState.shouldPollFulfillment(state.data, !document.hidden)) return;
    const timer = setInterval(() => {
      if (!document.hidden) load(true);
    }, 2500);
    const onVisibility = () => {
      if (!document.hidden && ProductState.shouldPollFulfillment(state.data, true)) load(true);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [state.kind, state.data, load]);
  const retryFulfillment = React.useCallback(() => {
    retryProductFulfillment(runId).then(() => load(true)).catch(error => setState({ kind: "error", error }));
  }, [runId, load]);
  if (state.kind === "loading") return <CatalogLoadState kind="loading" />;
  if (state.kind === "error") return <div className="product-state" role="alert"><h2>正式旅程内容暂时无法读取</h2><p>{state.error?.message}</p><button onClick={load}>重新读取</button></div>;
  const data = state.data;
  const context = data.run.request_snapshot?.catalog_context || {};
  const tabs = [{ key: "itinerary", label: "行程" }, { key: "story", label: "故事" }, { key: "experience", label: "互动" }, { key: "resources", label: "附近资源" }];
  return (
    <section className="unified-trip" data-run-id={data.run.id} data-itinerary-id={data.itinerary.id}>
      <header className="unified-trip-head"><p className="product-kicker">完整神话旅程</p><h1>{context.route_name || data.itinerary.plan.destination}</h1><div className="trip-identity"><span>Run {data.run.id}</span><span>Itinerary {data.itinerary.id}</span><span>Catalog {context.content_version || "未记录"}</span></div></header>
      <FulfillmentProgress data={data} />
      <nav className="trip-tabs" aria-label="旅程内容">{tabs.map(item => <button key={item.key} className={tab === item.key ? "active" : ""} aria-selected={tab === item.key} onClick={() => setTab(item.key)}>{item.label}<span>{item.key === "itinerary" ? "去哪" : item.key === "story" ? "为什么来" : item.key === "experience" ? "做什么" : "顺路有什么"}</span></button>)}</nav>
      {tab === "itinerary" && <ProductItinerarySection itinerary={data.itinerary} username={username} />}
      {tab === "story" && <ProductStorySection snapshot={data.story} onRetry={retryFulfillment} />}
      {tab === "experience" && <ProductExperienceSection snapshot={data.experience} onRetry={retryFulfillment} />}
      {tab === "resources" && <ProductResourcesSection snapshot={data.resources} onRetry={retryFulfillment} />}
    </section>
  );
}

function ProductTripRuntimePage({ runId, currentUsername, onRequestLogin, onReplaceRun }) {
  const [state, setState] = React.useState({ kind: "loading", run: null, cursor: 0 });
  const runRef = React.useRef(null);
  const reconnectRef = React.useRef(null);
  const hydrate = React.useCallback(async () => {
    if (!currentUsername) return;
    setState(previous => ({ ...previous, kind: "loading" }));
    try {
      const [run, events] = await Promise.all([getRun(runId), getRunEvents(runId, 0)]);
      const restored = ProductState.restoreRun(run, events);
      runRef.current = restored.run;
      setState({ kind: "ready", ...restored });
    } catch (error) {
      setState({ kind: "error", error, run: null, cursor: 0 });
    }
  }, [runId, currentUsername]);
  React.useEffect(() => { hydrate(); }, [hydrate]);

  React.useEffect(() => {
    if (state.kind !== "ready" || !ProductState.shouldReconnect(state.run?.status)) return;
    let disposed = false;
    let abort = null;
    const connect = () => {
      const cursor = Number(localStorage.getItem(`run-cursor:${runId}`) || state.cursor || 0);
      streamRuntimeRun(runId, cursor, {
        onAbort: fn => { abort = fn; },
        onEvent: event => {
          setState(previous => {
            if (!previous.run) return previous;
            const restored = ProductState.applyRunEvent(previous.run, previous.cursor, event);
            const nextCursor = Math.max(previous.cursor || 0, restored.cursor || 0, Number(event.sequence || 0));
            localStorage.setItem(`run-cursor:${runId}`, String(nextCursor));
            runRef.current = restored.run;
            return { ...previous, run: restored.run, cursor: nextCursor };
          });
        },
        onError: () => {
          if (!disposed && ProductState.shouldReconnect(runRef.current?.status)) reconnectRef.current = setTimeout(connect, 1000);
        },
        onClose: () => {
          if (!disposed && ProductState.shouldReconnect(runRef.current?.status)) reconnectRef.current = setTimeout(connect, 1000);
        },
      });
    };
    connect();
    return () => {
      disposed = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      abort?.();
    };
  }, [runId, state.kind]); // reconnect only after initial recovery or run replacement

  if (!currentUsername) return <main className="product-trip-page"><div className="product-state"><h1>登录后恢复旅程</h1><p>Run ID 已保留，登录不会重新创建任务。</p><button onClick={onRequestLogin}>登录</button></div></main>;
  if (state.kind === "loading") return <main className="product-trip-page"><CatalogLoadState kind="loading" /></main>;
  if (state.kind === "error") return <main className="product-trip-page"><div className="product-state" role="alert"><h1>无法恢复这次旅程</h1><p>{state.error?.message || "请检查访问权限或网络连接。"}</p><button onClick={hydrate}>重新连接</button></div></main>;
  const run = state.run;
  const resume = async (value) => {
    const updated = await resumeRuntimeRun(run.id, run.pending_interaction.interaction_id, value);
    runRef.current = { ...run, ...updated, pending_interaction: null };
    setState(previous => ({ ...previous, run: runRef.current }));
  };
  const retry = async () => {
    const next = await retryRuntimeRun(run.id);
    onReplaceRun(next.id);
  };
  return (
    <main className="product-trip-page page-fade">
      <ProductRunProgress run={run} />
      {run.status === "waiting_user" && run.pending_interaction && (
        <section className="product-run-action"><h2>请确认后继续</h2><p>{run.pending_interaction.question}</p><StructuredInteractionInput interaction={run.pending_interaction} onSubmit={resume} /></section>
      )}
      {run.status === "failed" && <section className="product-run-action"><h2>这次规划没有完成</h2><p>{run.error_public?.message || "正式需求仍已保留，可以重新尝试。"}</p><button className="product-primary" onClick={retry}>重新尝试</button></section>}
      {run.status === "cancelled" && <section className="product-run-action"><h2>规划已停止</h2><button className="product-primary" onClick={retry}>重新尝试</button></section>}
      {run.status === "succeeded" && <ProductTripExperience runId={run.id} username={currentUsername} />}
    </main>
  );
}

Object.assign(window, { ProductHomePage, MythJourneysPage, ThemeRoutePreviewPage, ProductTripRuntimePage });
