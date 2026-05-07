import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

type ViewMode = "theater" | "graph" | "judgment" | "operations";

type StudioEvent = {
  id: string;
  type: string;
  timestamp: string;
  pipeline_id?: string;
  upload_id?: string;
  stage?: string;
  provider?: string;
  model?: string;
  filename?: string;
  error?: string;
  success?: boolean;
  incremental_ratio?: number;
  [key: string]: unknown;
};

type StudioStatus = {
  queue: Record<string, number>;
  source_jobs?: Record<string, number>;
  provider_pressure?: Record<string, Record<string, number>>;
  graph: Record<string, number>;
  active_pipelines: string[];
  active_uploads: string[];
  daemons: Record<string, boolean>;
  minds: Record<string, boolean>;
};

type GraphNode = {
  id: string;
  type: string;
  label: string;
  source: string;
  created_at: string;
};

type GraphEdge = {
  id: string;
  source_node_id: string;
  target_node_id: string;
  relation_type: string;
  weight: number;
  source: string;
  created_at: string;
};

type GraphSnapshot = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

type RunSummary = {
  run_id: string;
  scenario?: string;
  completed_at?: string;
  exit_code?: number;
  source_count: number;
  mocked: boolean;
  fake_components: string[];
  real_llm: boolean;
  failures_count: number;
  ui_event_count: number;
  graph_edge_count_after: number;
  vault_counts_after: Record<string, number>;
  business_skipped_reason?: string;
};

type RunListResponse = {
  root_dir: string;
  total: number;
  runs: RunSummary[];
};

type SourceSummary = {
  source_id: string;
  kind: string;
  filename?: string;
  normalized_source: string;
  content_type?: string;
  size_bytes: number;
  status: string;
  created_at: string;
  updated_at: string;
};

type SourceListResponse = {
  total: number;
  sources: SourceSummary[];
};

type SourceJobSummary = {
  job_id: string;
  source_id: string;
  job_type: string;
  status: string;
  priority: number;
  attempt_count: number;
  available_at: string;
  locked_by?: string | null;
  locked_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
  filename?: string | null;
  normalized_source?: string | null;
  source_kind?: string | null;
  content_type?: string | null;
  size_bytes?: number | null;
  source_status?: string | null;
};

type SourceJobListResponse = {
  total: number;
  jobs: SourceJobSummary[];
};

type VaultNote = {
  title: string;
  note_path: string;
  relative_path: string;
  size_bytes: number;
  updated_at: number;
  preview: string;
};

type VaultNoteListResponse = {
  stage: string;
  total: number;
  items: VaultNote[];
  graph_reactor_proposal_count?: number;
  graph_business_count?: number;
};

type PipelineTrack = {
  pipelineId: string;
  uploadId?: string;
  sourceLabel: string;
  currentStage: StageName;
  startedAt: string;
  completedStages: Set<StageName>;
  failed: boolean;
  completed: boolean;
  spark: boolean;
  provider?: string;
  model?: string;
};

type JudgmentSignal = {
  id: string;
  pipelineId: string;
  title: string;
  state: "warming" | "under_review" | "completed";
  rationale: string;
  provider?: string;
  model?: string;
  timestamp: string;
};

type GraphViewNode = GraphNode & {
  x: number;
  y: number;
  r: number;
  showLabel: boolean;
  degree: number;
};

type GraphViewEdge = {
  id: string;
  relation: string;
  source: GraphViewNode;
  target: GraphViewNode;
  weight: number;
};

type GraphView = {
  width: number;
  height: number;
  nodes: GraphViewNode[];
  edges: GraphViewEdge[];
};

const VIEWS: { id: ViewMode; label: string; description: string }[] = [
  { id: "theater", label: "Thinking Theater", description: "Watch DIKIWI cognition happen live." },
  { id: "graph", label: "Brain Graph", description: "Inspect the persistent vault network." },
  { id: "judgment", label: "Judgment Room", description: "Track proposal and entrepreneur motion." },
  { id: "operations", label: "Operations", description: "Inspect daemons, queues, and raw runtime state." },
];

const STAGES = [
  "CHAOS",
  "DATA",
  "INFORMATION",
  "KNOWLEDGE",
  "INSIGHT",
  "WISDOM",
  "IMPACT",
  "PROPOSAL",
  "ENTREPRENEUR",
] as const;

type StageName = (typeof STAGES)[number];

const STAGE_LABELS: Record<StageName, string> = {
  CHAOS: "00-Chaos",
  DATA: "01-Data",
  INFORMATION: "02-Information",
  KNOWLEDGE: "03-Knowledge",
  INSIGHT: "04-Insight",
  WISDOM: "05-Wisdom",
  IMPACT: "06-Impact",
  PROPOSAL: "07-Proposal",
  ENTREPRENEUR: "08-Entrepreneurship",
};

const STAGE_NARRATIVE: Record<StageName, string> = {
  CHAOS: "Unsorted fragments arrive with no hierarchy: files, links, media, screenshots, and noise.",
  DATA: "The raw stream is split into accountable datapoints: one claim, observation, figure, or artifact at a time.",
  INFORMATION: "Datapoints gain tags and clusters, turning isolated facts into searchable context.",
  KNOWLEDGE: "Clusters connect into a graph, exposing relationships that were not visible inside any single source.",
  INSIGHT: "A short meaningful path lights up: this is the first usable pattern, tension, or opportunity.",
  WISDOM: "Long arcs connect distant regions, forcing tradeoffs, constraints, and second-order consequences into view.",
  IMPACT: "A high-gravity center appears: many paths point at one innovation nucleus with practical leverage.",
  PROPOSAL: "Impact becomes multiple venture hypotheses, not one premature answer.",
  ENTREPRENEUR: "Guru judgment turns each accepted or denied idea into a business and technical development brief.",
};

const STAGE_AXIOMS: Record<StageName, string> = {
  CHAOS: "fragments",
  DATA: "atomic evidence",
  INFORMATION: "classified signals",
  KNOWLEDGE: "linked context",
  INSIGHT: "short path",
  WISDOM: "long arc",
  IMPACT: "gravity center",
  PROPOSAL: "option set",
  ENTREPRENEUR: "CEO/CTO brief",
};

const emptyStatus: StudioStatus = {
  queue: {},
  graph: {},
  active_pipelines: [],
  active_uploads: [],
  daemons: {},
  minds: {},
};

const emptyGraph: GraphSnapshot = { nodes: [], edges: [] };
const emptyRuns: RunListResponse = { root_dir: "", total: 0, runs: [] };
const emptySources: SourceListResponse = { total: 0, sources: [] };
const emptySourceJobs: SourceJobListResponse = { total: 0, jobs: [] };
const emptyVaultNotes: VaultNoteListResponse = { stage: "", total: 0, items: [] };
const AUTH_STORAGE_KEY = "aily_studio_token";
const MAX_STUDIO_EVENTS = 2000;

function initialAuthToken() {
  const urlToken = new URLSearchParams(window.location.search).get("token")?.trim();
  if (urlToken) {
    window.sessionStorage.setItem(AUTH_STORAGE_KEY, urlToken);
    return urlToken;
  }
  return window.sessionStorage.getItem(AUTH_STORAGE_KEY) ?? "";
}

function responseError(response: Response, fallback: string): Promise<Error> {
  return response
    .text()
    .then((body) => new Error(body || fallback))
    .catch(() => new Error(fallback));
}

function mergeStudioEvents(current: StudioEvent[], incoming: StudioEvent[]): StudioEvent[] {
  if (!incoming.length) return current;
  const byId = new Map<string, StudioEvent>();
  for (const event of current) {
    byId.set(event.id, event);
  }
  for (const event of incoming) {
    byId.set(event.id, event);
  }
  return Array.from(byId.values())
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .slice(-MAX_STUDIO_EVENTS);
}

function App() {
  const [events, setEvents] = useState<StudioEvent[]>([]);
  const [status, setStatus] = useState<StudioStatus>(emptyStatus);
  const [graph, setGraph] = useState<GraphSnapshot>(emptyGraph);
  const [runs, setRuns] = useState<RunListResponse>(emptyRuns);
  const [sources, setSources] = useState<SourceListResponse>(emptySources);
  const [sourceJobs, setSourceJobs] = useState<SourceJobListResponse>(emptySourceJobs);
  const [proposals, setProposals] = useState<VaultNoteListResponse>(emptyVaultNotes);
  const [entrepreneurship, setEntrepreneurship] = useState<VaultNoteListResponse>(emptyVaultNotes);
  const [vaultNotes, setVaultNotes] = useState<VaultNoteListResponse>(emptyVaultNotes);
  const [mode, setMode] = useState<"live" | "replay">("live");
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [submittingUrl, setSubmittingUrl] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [authToken, setAuthToken] = useState(initialAuthToken);
  const [pendingAuthToken, setPendingAuthToken] = useState(authToken);
  const [wsConnected, setWsConnected] = useState(false);
  const [eventPollConnected, setEventPollConnected] = useState(false);
  const [view, setView] = useState<ViewMode>("theater");
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>("all");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.has("token")) {
      url.searchParams.delete("token");
      window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
    void refreshGraph();
    void refreshRuns();
    void refreshSources();
    void refreshSourceJobs();
    void refreshJudgmentArtifacts();
    void refreshVaultNotes();
    void refreshRecentEvents();

    const interval = window.setInterval(() => {
      void refreshStatus();
      void refreshGraph();
      void refreshRuns();
      void refreshSources();
      void refreshSourceJobs();
      void refreshJudgmentArtifacts();
      void refreshVaultNotes();
      void refreshRecentEvents();
    }, 5000);

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let cancelled = false;

    const connect = () => {
      const tokenQuery = authToken ? `?token=${encodeURIComponent(authToken)}` : "";
      ws = new WebSocket(`${protocol}://${window.location.host}/api/ui/events${tokenQuery}`);
      ws.onopen = () => {
        setWsConnected(true);
        setStreamError(null);
      };
      ws.onmessage = (message) => {
        const event = JSON.parse(message.data) as StudioEvent;
        setEvents((current) => mergeStudioEvents(current, [event]));
        if (event.pipeline_id) {
          setSelectedPipelineId((current) => current ?? event.pipeline_id ?? null);
        }
        void refreshStatus();
        if (
          event.type === "stage_completed" ||
          event.type === "pipeline_completed" ||
          event.type === "proposal_review_completed" ||
          event.type === "threshold_crossed" ||
          event.type === "chaos_note_created"
        ) {
          void refreshGraph();
          void refreshJudgmentArtifacts();
          void refreshVaultNotes();
        }
      };
      ws.onerror = () => {
        setStreamError("Live event stream encountered an error.");
      };
      ws.onclose = () => {
        setWsConnected(false);
        if (cancelled) return;
        setStreamError("Live event stream disconnected.");
        reconnectTimer = window.setTimeout(connect, 1500);
      };
    };

    connect();

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      ws?.close();
    };
  }, [authToken]);

  function authHeaders(extra: Record<string, string> = {}) {
    return authToken ? { ...extra, "x-aily-token": authToken } : extra;
  }

  async function apiFetch(input: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers ?? {});
    if (authToken) {
      headers.set("x-aily-token", authToken);
    }
    return fetch(input, { ...init, headers });
  }

  function saveAuthToken() {
    const token = pendingAuthToken.trim();
    if (token) {
      window.sessionStorage.setItem(AUTH_STORAGE_KEY, token);
    } else {
      window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
    }
    setAuthToken(token);
    setApiError(null);
    setStreamError(null);
  }

  async function clearAuthToken() {
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
    try {
      await fetch("/api/ui/logout", { method: "POST" });
    } catch {
      // Local state is still cleared; the server endpoint clears HttpOnly cookies when reachable.
    }
    setAuthToken("");
    setPendingAuthToken("");
    setApiError(null);
    setStreamError(null);
  }

  async function refreshStatus() {
    try {
      const response = await apiFetch("/api/ui/status");
      if (!response.ok) {
        throw await responseError(response, "Failed to fetch studio status.");
      }
      const payload = (await response.json()) as StudioStatus;
      setStatus(payload);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to fetch studio status.");
    }
  }

  async function refreshRecentEvents() {
    if (mode === "replay") return;
    try {
      const response = await apiFetch(`/api/ui/events/query?limit=${MAX_STUDIO_EVENTS}`);
      if (!response.ok) {
        throw await responseError(response, "Failed to fetch persisted UI events.");
      }
      const payload = (await response.json()) as { events: StudioEvent[] };
      setEvents((current) => mergeStudioEvents(current, payload.events));
      setSelectedPipelineId((current) => {
        if (current) return current;
        return payload.events.find((event) => event.pipeline_id)?.pipeline_id ?? null;
      });
      setEventPollConnected(true);
    } catch {
      setEventPollConnected(false);
    }
  }

  async function refreshGraph() {
    try {
      const response = await apiFetch("/api/ui/graph");
      if (!response.ok) {
        throw await responseError(response, "Failed to fetch graph snapshot.");
      }
      const payload = (await response.json()) as GraphSnapshot;
      setGraph(payload);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to fetch graph snapshot.");
    }
  }

  async function refreshRuns() {
    try {
      const response = await apiFetch("/api/ui/runs?limit=8");
      if (!response.ok) {
        throw await responseError(response, "Failed to fetch evidence runs.");
      }
      const payload = (await response.json()) as RunListResponse;
      setRuns(payload);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to fetch evidence runs.");
    }
  }

  async function refreshSources() {
    try {
      const response = await apiFetch("/api/ui/sources?limit=8");
      if (!response.ok) {
        throw await responseError(response, "Failed to fetch source store.");
      }
      const payload = (await response.json()) as SourceListResponse;
      setSources(payload);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to fetch source store.");
    }
  }

  async function refreshSourceJobs() {
    try {
      const response = await apiFetch("/api/ui/source-jobs?limit=24");
      if (!response.ok) {
        throw await responseError(response, "Failed to fetch source job ledger.");
      }
      const payload = (await response.json()) as SourceJobListResponse;
      setSourceJobs(payload);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to fetch source job ledger.");
    }
  }

  async function refreshJudgmentArtifacts() {
    try {
      const [proposalResponse, entrepreneurshipResponse] = await Promise.all([
        apiFetch("/api/ui/proposals?limit=12"),
        apiFetch("/api/ui/entrepreneurship?limit=12"),
      ]);
      if (!proposalResponse.ok) {
        throw await responseError(proposalResponse, "Failed to fetch proposals.");
      }
      if (!entrepreneurshipResponse.ok) {
        throw await responseError(entrepreneurshipResponse, "Failed to fetch entrepreneurship notes.");
      }
      setProposals((await proposalResponse.json()) as VaultNoteListResponse);
      setEntrepreneurship((await entrepreneurshipResponse.json()) as VaultNoteListResponse);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to fetch judgment artifacts.");
    }
  }

  async function refreshVaultNotes() {
    try {
      const response = await apiFetch("/api/ui/vault-notes/05-Wisdom?limit=8");
      if (!response.ok) {
        throw await responseError(response, "Failed to fetch vault notes.");
      }
      setVaultNotes((await response.json()) as VaultNoteListResponse);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to fetch vault notes.");
    }
  }

  async function uploadFiles(files: FileList | File[]) {
    const items = Array.from(files);
    if (!items.length) return;
    const form = new FormData();
    for (const file of items) {
      form.append("files", file);
    }
    setUploading(true);
    try {
      const response = await apiFetch("/api/ui/uploads", { method: "POST", body: form });
      if (!response.ok) {
        throw await responseError(response, "Upload failed.");
      }
      setApiError(null);
      await refreshStatus();
      await refreshSourceJobs();
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function submitUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const url = urlInput.trim();
    if (!url) return;
    setSubmittingUrl(true);
    try {
      const response = await apiFetch("/api/ui/sources/urls", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ url }),
      });
      if (!response.ok) {
        throw await responseError(response, "URL intake failed.");
      }
      setUrlInput("");
      setApiError(null);
      await refreshSources();
      await refreshSourceJobs();
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "URL intake failed.");
    } finally {
      setSubmittingUrl(false);
    }
  }

  async function sendControl(action: string, payload: Record<string, unknown> = {}) {
    try {
      const response = await apiFetch("/api/ui/control", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ action, ...payload }),
      });
      if (!response.ok) {
        throw await responseError(response, "Control action failed.");
      }
      setApiError(null);
      await refreshStatus();
      await refreshSources();
      await refreshSourceJobs();
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Control action failed.");
    }
  }

  async function loadRunReplay(runId: string) {
    try {
      const response = await apiFetch(
        `/api/ui/events/query?run_id=${encodeURIComponent(runId)}&limit=${MAX_STUDIO_EVENTS}`,
      );
      if (!response.ok) {
        throw await responseError(response, "Failed to load run replay.");
      }
      const payload = (await response.json()) as { events: StudioEvent[] };
      setEvents(payload.events);
      setMode("replay");
      setSelectedPipelineId(payload.events.find((event) => event.pipeline_id)?.pipeline_id ?? null);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to load run replay.");
    }
  }

  const pipelineTracks = useMemo(() => derivePipelineTracks(events), [events]);
  const activeTrack = useMemo(() => {
    if (!pipelineTracks.length) return null;
    const track = pipelineTracks.find((item) => item.pipelineId === selectedPipelineId);
    return track ?? pipelineTracks[0];
  }, [pipelineTracks, selectedPipelineId]);

  const filteredEvents = useMemo(() => {
    if (!selectedPipelineId) {
      return events.slice(-24).reverse();
    }
    const scoped = events.filter((event) => event.pipeline_id === selectedPipelineId || !event.pipeline_id);
    return scoped.slice(-24).reverse();
  }, [events, selectedPipelineId]);

  const graphTypes = useMemo(
    () => ["all", ...Array.from(new Set(graph.nodes.map((node) => node.type))).sort()],
    [graph.nodes],
  );
  const graphView = useMemo(() => buildGraphView(graph, nodeTypeFilter), [graph, nodeTypeFilter]);
  const selectedNode = useMemo(
    () => graphView.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graphView.nodes, selectedNodeId],
  );
  const selectedNodeEdges = useMemo(
    () =>
      graphView.edges.filter(
        (edge) => edge.source.id === selectedNodeId || edge.target.id === selectedNodeId,
      ),
    [graphView.edges, selectedNodeId],
  );
  const workerCards = useMemo(() => deriveWorkerCards(status), [status]);
  const judgmentSignals = useMemo(
    () => deriveJudgmentSignals(events, pipelineTracks),
    [events, pipelineTracks],
  );
  const recentMilestones = useMemo(() => deriveMilestones(events), [events]);
  const eventBackedPipelineCount = pipelineTracks.filter((track) => !track.failed && !track.completed).length;
  const displayedQueueTotal = Math.max(status.queue.total ?? 0, eventBackedPipelineCount);
  const displayedActivePipelines = Math.max(status.active_pipelines.length, eventBackedPipelineCount);
  const displayedSources = Math.max(sources.total, pipelineTracks.length);

  useEffect(() => {
    if (!selectedPipelineId && pipelineTracks[0]) {
      setSelectedPipelineId(pipelineTracks[0].pipelineId);
    }
  }, [pipelineTracks, selectedPipelineId]);

  useEffect(() => {
    if (!selectedNodeId && graphView.nodes[0]) {
      setSelectedNodeId(graphView.nodes[0].id);
    }
  }, [graphView.nodes, selectedNodeId]);

  return (
    <main className="studio-shell">
      <header className="hero-bar">
        <div className="hero-copy">
          <p className="eyebrow">Aily Studio</p>
          <h1>Thinking Theater</h1>
          <p className="hero-subtitle">
            A live sensemaking environment for DIKIWI, graph growth, innovation,
            and entrepreneur review.
          </p>
        </div>
        <div className="hero-metrics">
          <Metric label="Queue" value={String(displayedQueueTotal)} />
          <Metric label="Active Pipelines" value={String(displayedActivePipelines)} />
          <Metric label="Active Uploads" value={String(status.active_uploads.length)} />
          <Metric label="Sources" value={String(displayedSources)} />
          <Metric label="Evidence Runs" value={String(runs.total)} />
          <Metric
            label="Event Stream"
            value={
              mode === "replay"
                ? "replay"
                : wsConnected && eventPollConnected
                  ? "live+poll"
                  : eventPollConnected
                    ? "polling"
                    : wsConnected
                      ? "connected"
                      : "down"
            }
          />
        </div>
      </header>

      {(streamError || apiError) && (
        <section className="alert-banner" role="alert">
          <strong>Studio warning</strong>
          <span>{streamError ?? apiError}</span>
        </section>
      )}

      <section className="auth-strip" aria-label="Private Studio token">
        <div>
          <span className="eyebrow">Private Access</span>
          <strong>{authToken ? "Token attached to Studio requests" : "Local mode or token not set"}</strong>
        </div>
        <div className="auth-controls">
          <input
            type="password"
            value={pendingAuthToken}
            onChange={(event) => setPendingAuthToken(event.target.value)}
            placeholder="UI_AUTH_TOKEN for hosted mode"
            aria-label="Aily Studio authentication token"
          />
          <button type="button" className="control-button" onClick={saveAuthToken}>
            Save token
          </button>
          {authToken && (
            <button
              type="button"
              className="control-button ghost"
              onClick={() => {
                void clearAuthToken();
              }}
            >
              Clear
            </button>
          )}
        </div>
      </section>

      <nav className="view-nav" aria-label="Studio views">
        {VIEWS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`view-pill ${view === item.id ? "active" : ""}`}
            onClick={() => setView(item.id)}
          >
            <span>{item.label}</span>
            <small>{item.description}</small>
          </button>
        ))}
      </nav>

      <section className="command-deck">
        <aside className="left-rail">
          <section
            className={`dropzone ${dragActive ? "drag-active" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragActive(false);
              void uploadFiles(event.dataTransfer.files);
            }}
          >
            <div className="dropzone-copy">
              <p className="eyebrow">Intake Dock</p>
              <h2>Drop files into Aily</h2>
              <p>
                Browser uploads enter the real pipeline. The theater and graph update
                from actual backend events, not mocked progress bars.
              </p>
              <label className="file-button">
                <input
                  type="file"
                  multiple
                  onChange={(event) => {
                    if (event.target.files) {
                      void uploadFiles(event.target.files);
                    }
                  }}
                />
                {uploading ? "Uploading..." : "Choose files"}
              </label>
              <form className="url-intake" onSubmit={submitUrl}>
                <input
                  type="url"
                  value={urlInput}
                  onChange={(event) => setUrlInput(event.target.value)}
                  placeholder="https://example.com/research"
                  aria-label="Submit URL to Aily"
                />
                <button type="submit" disabled={submittingUrl || !urlInput.trim()}>
                  {submittingUrl ? "Queueing..." : "Process link"}
                </button>
              </form>
              <p className="intake-note">Links are stored first, then fetched and routed through the same DIKIWI processing path.</p>
            </div>
          </section>

          <Panel title="Workers" subtitle="Daemon and mind fabric">
            <div className="worker-strip">
              {workerCards.map((worker) => (
                <article key={worker.label} className={`worker-card ${worker.ok ? "ok" : "bad"}`}>
                  <span>{worker.group}</span>
                  <strong>{worker.label}</strong>
                  <em>{worker.ok ? "live" : "offline"}</em>
                </article>
              ))}
            </div>
          </Panel>

                <Panel title="Pipeline Queue" subtitle="Tracked cognition runs">
            {mode === "replay" && (
              <button type="button" className="control-button" onClick={() => setMode("live")}>
                Return to live stream
              </button>
            )}
            <div className="track-list compact">
              {pipelineTracks.slice(0, 8).map((track) => (
                <button
                  key={track.pipelineId}
                  type="button"
                  className={`track-card selectable ${selectedPipelineId === track.pipelineId ? "selected" : ""}`}
                  onClick={() => setSelectedPipelineId(track.pipelineId)}
                >
                  <div>
                    <strong>{track.sourceLabel}</strong>
                    <p className="mono">{track.pipelineId}</p>
                  </div>
                  <div className="track-meta">
                    <span className="pill">{track.currentStage}</span>
                    {track.provider && <span className="pill muted">{track.provider}</span>}
                  </div>
                </button>
              ))}
              {!pipelineTracks.length && (
                <p className="empty-state">No tracked pipelines yet.</p>
              )}
            </div>
          </Panel>
        </aside>

        <section className="main-stage">
          {view === "theater" && (
            <div className="main-stack">
              <section className="theater-panel">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Stage Theater</p>
                    <h2>Live DIKIWI Flow</h2>
                  </div>
                  {activeTrack && (
                    <div className="brain-stats">
                      <span>{activeTrack.currentStage}</span>
                      {activeTrack.provider && <span>{activeTrack.provider}</span>}
                      {activeTrack.model && <span>{activeTrack.model}</span>}
                    </div>
                  )}
                </div>
                <ThinkingStageCanvas
                  track={activeTrack}
                  proposalArtifactCount={proposals.total}
                  entrepreneurshipArtifactCount={entrepreneurship.total}
                />
              </section>

              <section className="milestone-panel">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Milestones</p>
                    <h2>Recent Cognition Events</h2>
                  </div>
                </div>
                <div className="milestone-list">
                  {recentMilestones.map((item) => (
                    <article key={item.id} className="milestone-row">
                      <div className={`milestone-pulse type-${item.kind}`} />
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.description}</p>
                      </div>
                      <span>{item.time}</span>
                    </article>
                  ))}
                  {!recentMilestones.length && (
                    <p className="empty-state">The pipeline has not emitted milestones yet.</p>
                  )}
                </div>
              </section>
            </div>
          )}

          {view === "graph" && (
            <section className="brain-panel expanded">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Brain Graph</p>
                  <h2>Persistent Vault Map</h2>
                </div>
                <div className="graph-toolbar">
                  <label className="select-wrap">
                    <span>Node layer</span>
                    <select value={nodeTypeFilter} onChange={(e) => setNodeTypeFilter(e.target.value)}>
                      {graphTypes.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="brain-stats">
                    <span>{graphView.nodes.length} nodes</span>
                    <span>{graphView.edges.length} edges</span>
                  </div>
                </div>
              </div>
              <BrainGraph
                snapshot={graphView}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
              />
            </section>
          )}

          {view === "judgment" && (
            <section className="judgment-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Judgment Room</p>
                  <h2>Proposal and Entrepreneur Motion</h2>
                </div>
                <button type="button" className="control-button" onClick={() => void refreshJudgmentArtifacts()}>
                  Refresh vault artifacts
                </button>
              </div>
              <div className="judgment-grid">
                {proposals.items.map((note) => (
                  <article key={note.note_path} className="judgment-card state-warming">
                    <div className="judgment-head">
                      <span className="pill">proposal note</span>
                      <span>{new Date(note.updated_at * 1000).toLocaleTimeString()}</span>
                    </div>
                    <h3>{note.title}</h3>
                    <p>{note.preview}</p>
                    <div className="judgment-meta">
                      <span className="mono">{note.relative_path}</span>
                      <span>{formatBytes(note.size_bytes)}</span>
                    </div>
                  </article>
                ))}
                {entrepreneurship.items.map((note) => (
                  <article key={note.note_path} className="judgment-card state-completed">
                    <div className="judgment-head">
                      <span className="pill">entrepreneur note</span>
                      <span>{new Date(note.updated_at * 1000).toLocaleTimeString()}</span>
                    </div>
                    <h3>{note.title}</h3>
                    <p>{note.preview}</p>
                    <div className="judgment-meta">
                      <span className="mono">{note.relative_path}</span>
                      <span>{formatBytes(note.size_bytes)}</span>
                    </div>
                  </article>
                ))}
                {vaultNotes.items.map((note) => (
                  <article key={note.note_path} className="judgment-card state-processing">
                    <div className="judgment-head">
                      <span className="pill">wisdom note</span>
                      <span>{new Date(note.updated_at * 1000).toLocaleTimeString()}</span>
                    </div>
                    <h3>{note.title}</h3>
                    <p>{note.preview}</p>
                    <div className="judgment-meta">
                      <span className="mono">{note.relative_path}</span>
                      <span>{formatBytes(note.size_bytes)}</span>
                    </div>
                  </article>
                ))}
                {judgmentSignals.map((signal) => (
                  <article key={signal.id} className={`judgment-card state-${signal.state}`}>
                    <div className="judgment-head">
                      <span className="pill">{signal.state.replace("_", " ")}</span>
                      <span>{new Date(signal.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <h3>{signal.title}</h3>
                    <p>{signal.rationale}</p>
                    <div className="judgment-meta">
                      <span className="mono">{signal.pipelineId}</span>
                      {signal.provider && <span>{signal.provider}</span>}
                      {signal.model && <span>{signal.model}</span>}
                    </div>
                  </article>
                ))}
                {!judgmentSignals.length && !proposals.items.length && !entrepreneurship.items.length && !vaultNotes.items.length && (
                  <p className="empty-state">
                    No proposal, entrepreneur, or wisdom artifacts found. Cards here are loaded from vault/API artifacts, not demo data.
                  </p>
                )}
              </div>
            </section>
          )}

          {view === "operations" && (
            <section className="operations-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Operations</p>
                  <h2>Runtime State</h2>
                </div>
              </div>
              <Panel title="Control Desk" subtitle="Admin actions">
                <div className="control-row">
                  <button type="button" className="control-button" onClick={() => void sendControl("retry_failed_sources")}>
                    Retry failed sources
                  </button>
                  <button type="button" className="control-button danger" onClick={() => void sendControl("cancel_all_uploads")}>
                    Cancel active uploads
                  </button>
                </div>
              </Panel>
              <div className="studio-grid operations-grid">
                <Panel title="Daemon Status" subtitle="Runtime health">
                  <KeyValueMap items={status.daemons} boolean />
                </Panel>
                <Panel title="Mind Status" subtitle="Cognition services">
                  <KeyValueMap items={status.minds} boolean />
                </Panel>
                <Panel title="Queue Status" subtitle="Background jobs">
                  <KeyValueMap items={status.queue} />
                </Panel>
                <Panel title="Source Jobs" subtitle="Durable intake backlog">
                  <KeyValueMap items={status.source_jobs ?? {}} />
                </Panel>
                <Panel title="Processing Ledger" subtitle={`${sourceJobs.total} durable jobs`}>
                  <div className="source-list">
                    {sourceJobs.jobs.map((job) => (
                      <article key={job.job_id} className={`source-card state-${job.status}`}>
                        <div className="run-head">
                          <strong>{job.filename ?? job.normalized_source ?? job.source_id}</strong>
                          <span className="pill">{job.status}</span>
                        </div>
                        <p className="mono">{job.job_id}</p>
                        <div className="run-meta">
                          <span>{job.job_type}</span>
                          <span>attempt {job.attempt_count}</span>
                          <span>source {job.source_status ?? "unknown"}</span>
                          <span>{formatBytes(Number(job.size_bytes ?? 0))}</span>
                        </div>
                        <div className="run-meta">
                          <span>available {new Date(job.available_at).toLocaleString()}</span>
                          {job.locked_by && <span>locked by {job.locked_by}</span>}
                        </div>
                        {job.last_error && <p className="error-text">{job.last_error}</p>}
                      </article>
                    ))}
                    {!sourceJobs.jobs.length && (
                      <p className="empty-state">No durable source jobs found.</p>
                    )}
                  </div>
                </Panel>
                <Panel title="Provider Pressure" subtitle="Global LLM budgets">
                  <KeyValueMap items={flattenProviderPressure(status.provider_pressure ?? {})} />
                </Panel>
                <Panel title="Graph Counts" subtitle="Persistent knowledge">
                  <KeyValueMap items={status.graph} />
                </Panel>
                <Panel title="Source Store" subtitle="Durable intake records">
                  <div className="source-list">
                    {sources.sources.map((source) => (
                      <article key={source.source_id} className={`source-card state-${source.status}`}>
                        <div className="run-head">
                          <strong>{source.filename ?? source.normalized_source}</strong>
                          <span className="pill">{source.status}</span>
                        </div>
                        <p className="mono">{source.source_id}</p>
                        <div className="run-meta">
                          <span>{source.kind}</span>
                          <span>{source.content_type ?? "unknown type"}</span>
                          <span>{formatBytes(source.size_bytes)}</span>
                        </div>
                        <time>{new Date(source.updated_at).toLocaleString()}</time>
                      </article>
                    ))}
                    {!sources.sources.length && (
                      <p className="empty-state">No source records found yet.</p>
                    )}
                  </div>
                </Panel>
                <Panel title="Evidence Runs" subtitle={runs.root_dir || "logs/runs"}>
                  <div className="run-list">
                    {runs.runs.map((run) => (
                      <article key={run.run_id} className={`run-card ${run.exit_code === 0 ? "ok" : "bad"}`}>
                        <div className="run-head">
                          <strong>{run.scenario ?? "unknown scenario"}</strong>
                          <span className="pill">{run.exit_code === 0 ? "passed" : `exit ${run.exit_code ?? "?"}`}</span>
                        </div>
                        <p className="mono">{run.run_id}</p>
                        <div className="run-meta">
                          <span>{run.source_count} sources</span>
                          <span>{run.ui_event_count} events</span>
                          <span>{run.graph_edge_count_after} edges</span>
                          <span>{run.real_llm ? "real LLM" : "no LLM proof"}</span>
                        </div>
                        {run.mocked || run.fake_components.length > 0 ? (
                          <p className="error-text">Not acceptance proof: mocked or fake components declared.</p>
                        ) : null}
                        {run.business_skipped_reason ? (
                          <p className="muted-copy">Business skipped: {run.business_skipped_reason}</p>
                        ) : null}
                        {run.completed_at ? (
                          <time>{new Date(run.completed_at).toLocaleString()}</time>
                        ) : null}
                        <button type="button" className="control-button" onClick={() => void loadRunReplay(run.run_id)}>
                          Replay run events
                        </button>
                      </article>
                    ))}
                    {!runs.runs.length && (
                      <p className="empty-state">No evidence runs found yet.</p>
                    )}
                  </div>
                </Panel>
              </div>
            </section>
          )}
        </section>

        <aside className="right-rail">
          <Panel title="Inspector" subtitle="Selected context">
            {view === "graph" ? (
              selectedNode ? (
                <div className="inspector-body">
                  <strong className="inspector-title">{selectedNode.label}</strong>
                  <dl className="inspector-list">
                    <div><dt>Type</dt><dd>{selectedNode.type}</dd></div>
                    <div><dt>Source</dt><dd>{selectedNode.source}</dd></div>
                    <div><dt>Degree</dt><dd>{selectedNode.degree}</dd></div>
                    <div><dt>Created</dt><dd>{new Date(selectedNode.created_at).toLocaleString()}</dd></div>
                    <div><dt>Visible edges</dt><dd>{selectedNodeEdges.length}</dd></div>
                  </dl>
                </div>
              ) : (
                <p className="empty-state">Select a node to inspect it.</p>
              )
            ) : activeTrack ? (
              <div className="inspector-body">
                <strong className="inspector-title">{activeTrack.sourceLabel}</strong>
                <p>{STAGE_NARRATIVE[activeTrack.currentStage]}</p>
                <dl className="inspector-list">
                  <div><dt>Pipeline</dt><dd>{activeTrack.pipelineId}</dd></div>
                  <div><dt>Stage</dt><dd>{activeTrack.currentStage}</dd></div>
                  <div><dt>Provider</dt><dd>{activeTrack.provider ?? "unknown"}</dd></div>
                  <div><dt>Model</dt><dd>{activeTrack.model ?? "unknown"}</dd></div>
                  <div><dt>Spark</dt><dd>{String(activeTrack.spark)}</dd></div>
                </dl>
              </div>
            ) : (
              <p className="empty-state">Upload a file or select a pipeline.</p>
            )}
          </Panel>

          <section className="log-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Live Console</p>
                <h2>Execution Stream</h2>
              </div>
            </div>
            <div className="event-list">
              {filteredEvents.map((event) => (
                <article key={event.id} className="event-row">
                  <div className="event-meta">
                    <span className="event-type">{event.type}</span>
                    <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="event-body">
                    {event.stage && <span className="pill">{String(event.stage)}</span>}
                    {event.provider && <span className="pill">{String(event.provider)}</span>}
                    {event.model && <span className="pill muted">{String(event.model)}</span>}
                    {event.pipeline_id && <span className="mono">{String(event.pipeline_id)}</span>}
                    {event.error && <p className="error-text">{String(event.error)}</p>}
                  </div>
                </article>
              ))}
              {!filteredEvents.length && <p className="empty-state">No events yet.</p>}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function ThinkingStageCanvas(props: {
  track: PipelineTrack | null;
  proposalArtifactCount?: number;
  entrepreneurshipArtifactCount?: number;
}) {
  if (!props.track) {
    return <div className="theater-canvas empty-canvas">No active pipeline</div>;
  }
  const track = props.track;

  const currentStageIndex = Math.max(0, STAGES.findIndex((stage) => stage === track.currentStage));
  const revealedStages = new Set<StageName>(["CHAOS", track.currentStage, ...track.completedStages]);
  if ((props.proposalArtifactCount ?? 0) > 0) {
    revealedStages.add("PROPOSAL");
  }
  if ((props.entrepreneurshipArtifactCount ?? 0) > 0) {
    revealedStages.add("ENTREPRENEUR");
  }

  return (
    <div className={`theater-canvas ${track.spark ? "sparked" : ""}`}>
      <div className="theater-lane">
        {STAGES.map((stage, index) => {
          const completed = track.completedStages.has(stage);
          const active = stage === track.currentStage;
          const revealed = revealedStages.has(stage);
          return (
            <div key={stage} className="stage-column">
              <div
                className={`stage-core stage-${stage.toLowerCase()} ${completed ? "completed" : ""} ${active ? "active" : ""} ${revealed ? "" : "locked"}`}
              >
                {revealed ? <StageGlyph stage={stage} active={active} /> : <LockedStageGlyph />}
                <span className="stage-axiom">{revealed ? STAGE_AXIOMS[stage] : "locked until real event"}</span>
              </div>
              <span className="stage-label">{STAGE_LABELS[stage]}</span>
            </div>
          );
        })}
      </div>
      <div className="theater-overlay">
        <div className="overlay-copy">
          <span className="eyebrow">Active Narrative</span>
          <strong>{track.currentStage}</strong>
          <p>{STAGE_NARRATIVE[track.currentStage]}</p>
        </div>
      </div>
      <div className="traveler" style={{ left: `${(currentStageIndex / (STAGES.length - 1)) * 100}%` }} />
    </div>
  );
}

function LockedStageGlyph() {
  return (
    <div className="stage-glyph glyph-locked" aria-hidden="true">
      <span className="lock-ring" />
      <span className="lock-bar" />
    </div>
  );
}

function StageGlyph(props: { stage: StageName; active: boolean }) {
  const { stage, active } = props;
  const glyphClass = `stage-glyph glyph-${stage.toLowerCase()} ${active ? "active" : ""}`;
  if (stage === "CHAOS") {
    return (
      <div className={glyphClass} aria-hidden="true">
        {Array.from({ length: 12 }).map((_, index) => (
          <span key={index} className={`fragment fragment-${index + 1}`} />
        ))}
      </div>
    );
  }
  if (stage === "DATA") {
    return (
      <div className={glyphClass} aria-hidden="true">
        {Array.from({ length: 8 }).map((_, index) => (
          <span key={index} className="data-dot" />
        ))}
      </div>
    );
  }
  if (stage === "INFORMATION") {
    return (
      <div className={glyphClass} aria-hidden="true">
        {["EDA", "cost", "risk", "flow", "proof", "market"].map((tag) => (
          <span key={tag} className="tag-chip">{tag}</span>
        ))}
      </div>
    );
  }
  if (stage === "KNOWLEDGE") {
    return (
      <div className={glyphClass} aria-hidden="true">
        <svg viewBox="0 0 120 120">
          <path d="M25 74 L52 36 L88 48 L98 86 L60 94 Z" />
          {[["25", "74"], ["52", "36"], ["88", "48"], ["98", "86"], ["60", "94"]].map(([cx, cy]) => (
            <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="6" />
          ))}
        </svg>
      </div>
    );
  }
  if (stage === "INSIGHT") {
    return (
      <div className={glyphClass} aria-hidden="true">
        <span className="path-node start" />
        <span className="path-line" />
        <span className="path-node end" />
      </div>
    );
  }
  if (stage === "WISDOM") {
    return (
      <div className={glyphClass} aria-hidden="true">
        <svg viewBox="0 0 140 110">
          <path d="M18 78 C42 10, 92 102, 122 28" />
          <path d="M26 88 C62 44, 82 62, 114 18" />
          <circle cx="18" cy="78" r="5" />
          <circle cx="122" cy="28" r="7" />
        </svg>
      </div>
    );
  }
  if (stage === "IMPACT") {
    return (
      <div className={glyphClass} aria-hidden="true">
        <span className="impact-core" />
        {Array.from({ length: 6 }).map((_, index) => (
          <span key={index} className={`orbit orbit-${index + 1}`} />
        ))}
      </div>
    );
  }
  if (stage === "PROPOSAL") {
    return (
      <div className={glyphClass} aria-hidden="true">
        {Array.from({ length: 5 }).map((_, index) => (
          <span key={index} className="proposal-card" />
        ))}
      </div>
    );
  }
  return (
    <div className={glyphClass} aria-hidden="true">
      <span className="brief-sheet business">CEO</span>
      <span className="brief-sheet technical">CTO</span>
      <span className="guru-lens" />
    </div>
  );
}

function BrainGraph(props: {
  snapshot: GraphView;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}) {
  const { snapshot, selectedNodeId, onSelectNode } = props;
  const { width, height, nodes, edges } = snapshot;
  return (
    <div className="brain-canvas">
      <svg viewBox={`0 0 ${width} ${height}`} className="brain-svg" role="img" aria-label="Aily graph">
        <g className="brain-grid">
          {Array.from({ length: 6 }).map((_, idx) => (
            <line
              key={`grid-v-${idx}`}
              x1={(idx / 5) * width}
              y1={0}
              x2={(idx / 5) * width}
              y2={height}
            />
          ))}
        </g>
        <g className="brain-edges">
          {edges.map((edge) => (
            <line
              key={edge.id}
              x1={edge.source.x}
              y1={edge.source.y}
              x2={edge.target.x}
              y2={edge.target.y}
              className={`edge edge-${edge.relation}`}
            />
          ))}
        </g>
        <g className="brain-nodes">
          {nodes.map((node) => (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onSelectNode(node.id)}
              className="brain-node-hit"
              role="button"
              tabIndex={0}
            >
              <circle
                r={node.r}
                className={`graph-node type-${node.type} ${selectedNodeId === node.id ? "selected" : ""}`}
              />
              {node.showLabel && (
                <text y={node.r + 12} className="graph-label">
                  {node.label}
                </text>
              )}
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}

function Panel(props: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{props.subtitle}</p>
          <h2>{props.title}</h2>
        </div>
      </div>
      {props.children}
    </section>
  );
}

function KeyValueMap(props: { items: Record<string, unknown>; boolean?: boolean }) {
  return (
    <div className="kv-grid">
      {Object.entries(props.items).map(([key, value]) => (
        <div key={key} className="kv-item">
          <span className="kv-key">{key}</span>
          <span className={`kv-value ${props.boolean ? (value ? "ok" : "bad") : ""}`}>
            {String(value)}
          </span>
        </div>
      ))}
    </div>
  );
}

function flattenProviderPressure(items: Record<string, Record<string, number>>) {
  const flattened: Record<string, number> = {};
  Object.entries(items).forEach(([provider, metrics]) => {
    Object.entries(metrics).forEach(([metric, value]) => {
      flattened[`${provider}.${metric}`] = value;
    });
  });
  return flattened;
}

function Metric(props: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function deriveWorkerCards(status: StudioStatus) {
  return [
    ...Object.entries(status.daemons).map(([label, ok]) => ({ group: "daemon", label, ok })),
    ...Object.entries(status.minds).map(([label, ok]) => ({ group: "mind", label, ok })),
  ];
}

function pipelineIdsForEvent(event: StudioEvent): string[] {
  if (typeof event.pipeline_id === "string" && event.pipeline_id) {
    return [event.pipeline_id];
  }
  if (Array.isArray(event.pipeline_ids)) {
    return event.pipeline_ids.filter((id): id is string => typeof id === "string" && Boolean(id));
  }
  return [];
}

function derivePipelineTracks(events: StudioEvent[]): PipelineTrack[] {
  const byPipeline = new Map<string, PipelineTrack>();
  const uploadNames = new Map<string, string>();

  for (const event of events) {
    if (event.type === "source_uploaded" && typeof event.upload_id === "string") {
      uploadNames.set(event.upload_id, String(event.filename ?? event.upload_id));
    }
  }

  for (const event of events) {
    for (const pipelineId of pipelineIdsForEvent(event)) {
      const current =
        byPipeline.get(pipelineId) ??
        {
          pipelineId,
          uploadId: event.upload_id,
          sourceLabel: String(
            event.filename ??
              (typeof event.upload_id === "string" ? uploadNames.get(event.upload_id) : undefined) ??
              event.upload_id ??
              pipelineId,
          ),
          currentStage: "CHAOS" as StageName,
          startedAt: event.timestamp,
          completedStages: new Set<StageName>(),
          failed: false,
          completed: false,
          spark: false,
          provider: undefined,
          model: undefined,
        };

      if (event.type === "source_uploaded" || event.type === "chaos_note_created") {
        current.currentStage = "CHAOS";
        current.sourceLabel = String(event.filename ?? current.sourceLabel);
      }
      if (typeof event.filename === "string" && event.filename) {
        current.sourceLabel = event.filename;
      }
      if (event.type === "stage_started" && typeof event.stage === "string") {
        current.currentStage = normalizeStage(event.stage);
        current.provider = typeof event.provider === "string" ? event.provider : current.provider;
        current.model = typeof event.model === "string" ? event.model : current.model;
      }
      if (event.type === "stage_completed" && typeof event.stage === "string") {
        const stage = normalizeStage(event.stage);
        current.completedStages.add(stage);
        current.currentStage = stage;
      }
      if (event.type === "threshold_crossed") {
        current.spark = true;
      }
      if (event.type === "proposal_generation_started") {
        current.currentStage = "PROPOSAL";
      }
      if (event.type === "proposal_review_started") {
        current.currentStage = "ENTREPRENEUR";
      }
      if (event.type === "proposal_review_completed") {
        current.completedStages.add("ENTREPRENEUR");
        current.currentStage = "ENTREPRENEUR";
        current.completed = true;
      }
      if (event.type === "pipeline_completed") {
        if (typeof event.final_stage === "string") {
          current.currentStage = normalizeStage(event.final_stage);
          current.completedStages.add(current.currentStage);
        }
        current.completed = true;
      }
      if (event.type === "pipeline_failed") {
        current.failed = true;
        current.completed = true;
      }
      byPipeline.set(pipelineId, current);
    }
  }

  return Array.from(byPipeline.values()).sort((a, b) => b.startedAt.localeCompare(a.startedAt));
}

function deriveJudgmentSignals(events: StudioEvent[], tracks: PipelineTrack[]): JudgmentSignal[] {
  const tracksById = new Map(tracks.map((track) => [track.pipelineId, track]));
  const signals: JudgmentSignal[] = [];

  for (const event of events) {
    for (const pipelineId of pipelineIdsForEvent(event)) {
      const track = tracksById.get(pipelineId);
      if (event.type === "threshold_crossed") {
        signals.push({
          id: `${event.id}-${pipelineId}`,
          pipelineId,
          title: track?.sourceLabel ?? pipelineId,
          state: "warming",
          rationale: `Threshold crossed${typeof event.incremental_ratio === "number" ? ` at ${(event.incremental_ratio * 100).toFixed(1)}% graph growth` : ""}. Higher-order synthesis activated.`,
          provider: track?.provider,
          model: track?.model,
          timestamp: event.timestamp,
        });
      }
      if (event.type === "proposal_review_started") {
        signals.push({
          id: `${event.id}-${pipelineId}`,
          pipelineId,
          title: track?.sourceLabel ?? pipelineId,
          state: "under_review",
          rationale: "Entrepreneur evaluation has started for this cognition chain.",
          provider: typeof event.provider === "string" ? event.provider : track?.provider,
          model: typeof event.model === "string" ? event.model : track?.model,
          timestamp: event.timestamp,
        });
      }
      if (event.type === "proposal_review_completed") {
        signals.push({
          id: `${event.id}-${pipelineId}`,
          pipelineId,
          title: track?.sourceLabel ?? pipelineId,
          state: "completed",
          rationale: "Entrepreneur evaluation finished. Use the live console and downstream notes for full reasoning.",
          provider: track?.provider,
          model: track?.model,
          timestamp: event.timestamp,
        });
      }
    }
  }

  return signals.reverse().slice(0, 12);
}

function deriveMilestones(events: StudioEvent[]) {
  return events
    .filter((event) =>
      ["chaos_note_created", "threshold_crossed", "stage_completed", "proposal_review_started", "proposal_review_completed"].includes(event.type),
    )
    .slice(-8)
    .reverse()
    .map((event) => ({
      id: event.id,
      kind:
        event.type === "threshold_crossed"
          ? "spark"
          : event.type.startsWith("proposal_review")
            ? "review"
            : event.type === "chaos_note_created"
              ? "chaos"
              : "stage",
      title:
        event.type === "chaos_note_created"
          ? `Chaos formed for ${String(event.filename ?? event.upload_id ?? "upload")}`
          : event.type === "threshold_crossed"
            ? "Graph threshold crossed"
            : event.type === "proposal_review_started"
              ? "Entrepreneur review started"
              : event.type === "proposal_review_completed"
                ? "Entrepreneur review completed"
                : `${String(event.stage ?? "Stage")} completed`,
      description:
        event.type === "threshold_crossed"
          ? "The graph changed enough to trigger higher-order cognition."
          : event.type.startsWith("proposal_review")
            ? "Business evaluation is now part of the visible cognition loop."
            : "Runtime progress is flowing through the live theater.",
      time: new Date(event.timestamp).toLocaleTimeString(),
    }));
}

function normalizeStage(stage: string): StageName {
  const normalized = stage.toUpperCase();
  if (normalized in STAGE_LABELS) {
    return normalized as StageName;
  }
  if (normalized === "RESIDUAL" || normalized === "PROPOSAL") {
    return "PROPOSAL";
  }
  if (normalized === "ENTREPRENEURSHIP" || normalized === "ENTREPRENEUR") {
    return "ENTREPRENEUR";
  }
  return "CHAOS";
}

function buildGraphView(snapshot: GraphSnapshot, nodeTypeFilter: string): GraphView {
  const width = 960;
  const height = 460;
  const stageOrder = new Map<string, number>([
    ["data", 0],
    ["information", 1],
    ["knowledge", 2],
    ["insight", 3],
    ["wisdom", 4],
    ["impact", 5],
    ["proposal", 6],
    ["business", 7],
  ]);

  const rawNodes =
    nodeTypeFilter === "all"
      ? snapshot.nodes.slice(0, 260)
      : snapshot.nodes.filter((node) => node.type === nodeTypeFilter).slice(0, 260);

  const degreeCount = new Map<string, number>();
  for (const edge of snapshot.edges) {
    degreeCount.set(edge.source_node_id, (degreeCount.get(edge.source_node_id) ?? 0) + 1);
    degreeCount.set(edge.target_node_id, (degreeCount.get(edge.target_node_id) ?? 0) + 1);
  }

  const typeBuckets = new Map<string, number>();
  const nodes: GraphViewNode[] = rawNodes.map((node) => {
    const column = stageOrder.get(node.type) ?? 0;
    const bucketIndex = typeBuckets.get(node.type) ?? 0;
    typeBuckets.set(node.type, bucketIndex + 1);
    const x = 74 + column * 110 + ((bucketIndex % 4) - 1.5) * 10;
    const y = 56 + (bucketIndex % 16) * 24 + Math.floor(bucketIndex / 16) * 7;
    const degree = degreeCount.get(node.id) ?? 0;
    return {
      ...node,
      x,
      y,
      degree,
      r: node.type === "impact" ? 8 + Math.min(4, degree * 0.35) : 4 + Math.min(3, degree * 0.18),
      showLabel: node.type === "impact" || node.type === "wisdom" || degree > 6,
    };
  });

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edges: GraphViewEdge[] = snapshot.edges
    .slice(0, 360)
    .map((edge) => {
      const source = nodeById.get(edge.source_node_id);
      const target = nodeById.get(edge.target_node_id);
      if (!source || !target) return null;
      return {
        id: edge.id,
        relation: edge.relation_type,
        source,
        target,
        weight: edge.weight,
      };
    })
    .filter(Boolean) as GraphViewEdge[];

  return { width, height, nodes, edges };
}

export default App;
