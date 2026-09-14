import { useEffect, useMemo, useState } from "react";
import { loadLocalApiStatus, type ApiStatus } from "./api";
import { mockDashboard, type ConnectionStatus, type FlowEvent, type Position } from "./mock";

type Page = "Overview" | "Alert rules" | "Positions" | "Suggestions" | "History" | "Settings";
const pages: Page[] = ["Overview", "Alert rules", "Positions", "Suggestions", "History", "Settings"];

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function HealthRow({ item }: { item: ConnectionStatus }) {
  const label = item.state === "healthy" ? "Healthy" : item.state === "degraded" ? "Degraded" : "Unavailable";
  const tone = item.state === "healthy" ? "good" : item.state === "degraded" ? "warn" : "bad";
  return <div className="health-row"><div><strong>{item.name}</strong><span>{item.detail}</span></div><Badge tone={tone}>{label}</Badge></div>;
}

function FlowRow({ event, onInspect }: { event: FlowEvent; onInspect: () => void }) {
  return <article className="flow-row"><div className="event-avatar" aria-hidden="true">{event.symbol.slice(0, 1)}</div><div className="flow-copy"><div className="flow-title"><strong>{event.symbol}</strong><Badge tone={event.asset === "Option" ? "warn" : "neutral"}>{event.asset}</Badge><span>{event.instrument}</span></div><p>{event.quantity} <span>· {event.quality}</span></p><div className="flow-meta"><span>{event.id}</span><span>{event.observed}</span><span>{event.delay}</span><Badge tone="good">{event.relevance}</Badge></div></div><div className="flow-action"><strong>{event.value}</strong><button onClick={onInspect}>Inspect</button></div></article>;
}

function Overview({ onNavigate, deliveryPaused, onPause, events, connections, live }: { onNavigate: (page: Page) => void; deliveryPaused: boolean; onPause: () => void; events: FlowEvent[]; connections: ConnectionStatus[]; live: boolean }) {
  return <><section className="page-heading"><div><p className="eyebrow">YOUR MARKET WORKSPACE</p><h1>See the trade.<br /><span>Understand the exposure.</span></h1><p className="lede">Large reported executions, useful context, and a clear view of what you already hold.</p></div><button className="primary">+ Create alert rule</button></section>
    <section className="metrics" aria-label="Dashboard summary"><article><span>Monitored universe</span><strong>{live ? "—" : "20"} <small>stocks</small> / {live ? "—" : "6"} <small>options</small></strong><p>{live ? "Waiting for configured market scope" : "Mock coverage · options every 10 seconds"}</p></article><article><span>Enabled rules</span><strong>{live ? "—" : "3"}</strong><p>{live ? "Rule API is not yet available" : "Large prints · repeat activity · held names"}</p></article><article><span>Exposure</span><strong>{live ? "—" : "$31,500"}</strong><p>{live ? "Import or refresh a reviewed position book" : "Illustrative Greeks · snapshot v12"}</p></article></section>
    <section className="dashboard-grid"><article className="card flow-card"><div className="card-header"><div><h2>Flow that matters</h2><p>Reported executions in your monitored universe</p></div><button className="quiet" onClick={onPause}>{deliveryPaused ? "Resume delivery" : "Pause delivery"}</button></div><div className="filter-line"><Badge>{live ? "LIVE API" : "MOCK EVENTS"}</Badge><span>Held names first</span><span>Newest first ↓</span></div><div className="flow-list">{events.length ? events.map((event) => <FlowRow key={event.id} event={event} onInspect={() => onNavigate("Suggestions")} />) : <p className="empty-flow">The local service is connected. No market events have been recorded yet.</p>}</div><footer>Direction is an inference. Large does not mean bullish.</footer></article>
      <aside className="right-rail"><article className="card exposure-card"><div className="card-header"><h2>Your exposure</h2><Badge>{live ? "AWAITING BOOK" : "DEMO"}</Badge></div><strong className="exposure-number">{live ? "—" : "31.5%"}<small>{live ? "Import or refresh positions to calculate exposure" : "NVDA delta / illustrative equity"}</small></strong><div className="meter" aria-label="Exposure awaiting a reviewed position book"><span style={{ width: live ? "0%" : undefined }} /></div><p>{live ? "No reviewed position snapshot is available from the local API." : "100 shares + 2 long calls. Long calls add directional exposure."}</p><button className="secondary" onClick={() => onNavigate("Suggestions")}>Review alternatives →</button></article><article className="card"><div className="card-header"><h2>Monitoring status</h2><Badge tone={deliveryPaused ? "warn" : "good"}>{deliveryPaused ? "DELIVERY PAUSED" : "MONITORING"}</Badge></div>{connections.map((item) => <HealthRow key={item.name} item={item} />)}</article></aside>
    </section></>;
}

function Table({ positions }: { positions: Position[] }) {
  return <div className="table-scroll"><table><thead><tr><th>Instrument</th><th>Position</th><th>Price</th><th>Delta</th><th>Delta dollars</th><th>Source</th></tr></thead><tbody>{positions.map((position) => <tr key={position.instrument}><td><strong>{position.instrument}</strong><span>{position.detail}</span></td><td>{position.quantity}</td><td>{position.price}</td><td>{position.delta}</td><td>{position.deltaDollars}</td><td>{position.source}</td></tr>)}</tbody></table></div>;
}

function GenericPage({ page, live }: { page: Exclude<Page, "Overview">; live: boolean }) {
  const content = useMemo(() => ({
    "Alert rules": ["Alert rules", "Create, test, pause, duplicate, or archive versioned rule revisions.", "Rule management is awaiting its local API."],
    Positions: ["Positions", "Reviewed holdings, exposure completeness, and position snapshot history.", "Partial screenshot imports must keep unshown holdings unchanged."],
    Suggestions: ["Review alternatives", "Validated candidate cards will appear here after fresh positions and policy checks.", "No brokerage order execution is available."],
    History: ["Activity history", "Trace a rule, event, suppression, and delivery outcome from one local timeline.", "This MVP has no persisted event journal yet."],
    Settings: ["Connections & settings", "Webull, Telegram, AI privacy, runtime, and risk policy health live here.", "Credentials are never sent to the browser bundle."],
  } as const)[page], [page]);
  return <section><div className="page-heading compact"><div><p className="eyebrow">LOCAL WORKSPACE</p><h1>{content[0]}</h1><p className="lede">{content[1]}</p></div><Badge tone={live ? "good" : "warn"}>{live ? "LOCAL API" : "MOCK MODE"}</Badge></div>{page === "Positions" ? <article className="card"><Table positions={live ? [] : mockDashboard.positions} /><footer>{live ? "The local API is connected; position display is awaiting the positions endpoint." : content[2]}</footer></article> : <article className="card empty-state"><div className="empty-mark">◇</div><h2>{content[2]}</h2><p>The visual shell uses same-origin API requests and does not expose credentials to the browser bundle.</p></article>}</section>;
}

export function App() {
  const [page, setPage] = useState<Page>("Overview");
  const [deliveryPaused, setDeliveryPaused] = useState(false);
  const [api, setApi] = useState<ApiStatus | null>(null);
  useEffect(() => { void loadLocalApiStatus().then(setApi); }, []);
  const live = api?.mode === "live";
  const fallback = api?.mode === "fallback";
  const events = live ? [] : fallback ? mockDashboard.events : [];
  const connections = live ? api.connections : fallback ? mockDashboard.connections : [{ name: "Local service", detail: "Connecting to loopback API", state: "degraded" as const }];
  const generatedAt = live ? api.generatedAt : fallback ? mockDashboard.generatedAt : "Connecting…";
  const modeText = live ? "LOCAL API CONNECTED" : fallback ? "MOCK FALLBACK" : "CONNECTING";
  const detail = fallback ? api.reason : live ? "Same-origin local service" : "Checking local service";
  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#overview" onClick={(event) => { event.preventDefault(); setPage("Overview"); }}><span className="brand-mark">W</span><span>Whale Rider<small>FLOW &amp; EXPOSURE</small></span></a><p className="nav-label">WORKSPACE</p><nav aria-label="Primary navigation">{pages.map((item) => <button key={item} className={page === item ? "nav-item active" : "nav-item"} aria-current={page === item ? "page" : undefined} onClick={() => setPage(item)}>{item}</button>)}</nav><div className="sidebar-footer"><span className="status-dot" /> {modeText}<p>{detail}</p></div></aside><div className="content"><header className="topbar"><div><span className="account-mark">P</span> Personal workspace <span className="subtle-text">/ {live ? "Local service" : "Demo account"}</span></div><div><Badge tone={live ? "good" : "warn"}>{modeText}</Badge><span className="clock">{generatedAt}</span></div></header><main>{page === "Overview" ? <Overview onNavigate={setPage} deliveryPaused={deliveryPaused} onPause={() => setDeliveryPaused((value) => !value)} events={events} connections={connections} live={live} /> : <GenericPage page={page} live={live} />}</main><footer className="app-footer">WHALE RIDER <span>Local MVP shell · manual trading only</span></footer></div></div>;
}
