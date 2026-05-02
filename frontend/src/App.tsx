import { useEffect, useMemo, useState } from "react";

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

type PipelineTrack = {
  pipelineId: string;
  uploadId?: string;
  sourceLabel: string;
  currentStage: StageName;
  startedAt: string;
  completedStages: Set<StageName>;
  failed: boolean;
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
  CHAOS: "Raw material swirls before structure appears.",
  DATA: "Chaos compresses into isolated datapoints.",
  INFORMATION: "Datapoints are classified, tagged, and clustered.",
  KNOWLEDGE: "Meaningful edges form across clusters.",
  INSIGHT: "Local pathways light up and reveal opportunities.",
  WISDOM: "Long arcs connect distant regions of the graph.",
  IMPACT: "Central innovation nuclei form and pull the network inward.",
  PROPOSAL: "Impact condenses into venture hypotheses.",
  ENTREPRENEUR: "Ideas face market and execution reality.",
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

function App() {
  const [events, setEvents] = useState<StudioEvent[]>([]);
  const [status, setStatus] = useState<StudioStatus>(emptyStatus);
  const [graph, setGraph] = useState<GraphSnapshot>(emptyGraph);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [view, setView] = useState<ViewMode>("theater");
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>("all");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    void refreshStatus();
    void refreshGraph();

    const interval = window.setInterval(() => {
      void refreshStatus();
      void refreshGraph();
    }, 5000);

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.hostname}:8000/api/ui/events`);
    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as StudioEvent;
      setEvents((current) => [...current.slice(-499), event]);
      if (!selectedPipelineId && event.pipeline_id) {
        setSelectedPipelineId(event.pipeline_id);
      }
      void refreshStatus();
      if (
        event.type === "stage_completed" ||
        event.type === "pipeline_completed" ||
        event.type === "threshold_crossed" ||
        event.type === "chaos_note_created"
      ) {
        void refreshGraph();
      }
    };

    return () => {
      window.clearInterval(interval);
      ws.close();
    };
  }, [selectedPipelineId]);

  async function refreshStatus() {
    const response = await fetch("/api/ui/status");
    const payload = (await response.json()) as StudioStatus;
    setStatus(payload);
  }

  async function refreshGraph() {
    const response = await fetch("/api/ui/graph");
    const payload = (await response.json()) as GraphSnapshot;
    setGraph(payload);
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
      await fetch("/api/ui/uploads", { method: "POST", body: form });
    } finally {
      setUploading(false);
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
    const scoped = events.filter((event) => event.pipeline_id === selectedPipelineId);
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
          <Metric label="Queue" value={String(status.queue.total ?? 0)} />
          <Metric label="Active Pipelines" value={String(status.active_pipelines.length)} />
          <Metric label="Active Uploads" value={String(status.active_uploads.length)} />
        </div>
      </header>

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
                <ThinkingStageCanvas track={activeTrack} />
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
              </div>
              <div className="judgment-grid">
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
                {!judgmentSignals.length && (
                  <p className="empty-state">
                    No proposal review signals yet. Once Reactor and Entrepreneur events deepen,
                    this room will populate automatically.
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
                <Panel title="Graph Counts" subtitle="Persistent knowledge">
                  <KeyValueMap items={status.graph} />
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

function ThinkingStageCanvas(props: { track: PipelineTrack | null }) {
  if (!props.track) {
    return <div className="theater-canvas empty-canvas">No active pipeline</div>;
  }
  const track = props.track;

  const currentStageIndex = Math.max(0, STAGES.findIndex((stage) => stage === track.currentStage));

  return (
    <div className={`theater-canvas ${track.spark ? "sparked" : ""}`}>
      <div className="theater-lane">
        {STAGES.map((stage, index) => {
          const completed = track.completedStages.has(stage);
          const active = stage === track.currentStage;
          return (
            <div key={stage} className="stage-column">
              <div className={`stage-core ${completed ? "completed" : ""} ${active ? "active" : ""}`}>
                {stage === "CHAOS" && <div className="chaos-cloud" />}
                {stage !== "CHAOS" && stage !== "PROPOSAL" && stage !== "ENTREPRENEUR" && (
                  <div className={`node-swarm stage-${stage.toLowerCase()}`}>
                    {Array.from({ length: Math.max(3, Math.min(index + 2, 7)) }).map((_, particle) => (
                      <span key={particle} className="mini-node" />
                    ))}
                  </div>
                )}
                {stage === "PROPOSAL" && <div className="proposal-stack" />}
                {stage === "ENTREPRENEUR" && <div className="verdict-gate" />}
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

function Metric(props: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function deriveWorkerCards(status: StudioStatus) {
  return [
    ...Object.entries(status.daemons).map(([label, ok]) => ({ group: "daemon", label, ok })),
    ...Object.entries(status.minds).map(([label, ok]) => ({ group: "mind", label, ok })),
  ];
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
    const pipelineId = event.pipeline_id;
    if (!pipelineId) continue;
    const current =
      byPipeline.get(pipelineId) ??
      {
        pipelineId,
        uploadId: event.upload_id,
        sourceLabel: String(
          event.filename ??
            (typeof event.upload_id === "string" ? uploadNames.get(event.upload_id) : undefined) ??
            event.upload_id ??
            "Untitled upload",
        ),
        currentStage: "CHAOS" as StageName,
        startedAt: event.timestamp,
        completedStages: new Set<StageName>(),
        failed: false,
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
      current.currentStage = "IMPACT";
    }
    if (event.type === "proposal_review_started") {
      current.currentStage = "ENTREPRENEUR";
    }
    if (event.type === "proposal_review_completed") {
      current.completedStages.add("ENTREPRENEUR");
      current.currentStage = "ENTREPRENEUR";
    }
    if (event.type === "pipeline_failed") {
      current.failed = true;
    }
    byPipeline.set(pipelineId, current);
  }

  return Array.from(byPipeline.values()).sort((a, b) => b.startedAt.localeCompare(a.startedAt));
}

function deriveJudgmentSignals(events: StudioEvent[], tracks: PipelineTrack[]): JudgmentSignal[] {
  const tracksById = new Map(tracks.map((track) => [track.pipelineId, track]));
  const signals: JudgmentSignal[] = [];

  for (const event of events) {
    if (!event.pipeline_id) continue;
    const track = tracksById.get(event.pipeline_id);
    if (event.type === "threshold_crossed") {
      signals.push({
        id: event.id,
        pipelineId: event.pipeline_id,
        title: track?.sourceLabel ?? event.pipeline_id,
        state: "warming",
        rationale: `Threshold crossed${typeof event.incremental_ratio === "number" ? ` at ${(event.incremental_ratio * 100).toFixed(1)}% graph growth` : ""}. Higher-order synthesis activated.`,
        provider: track?.provider,
        model: track?.model,
        timestamp: event.timestamp,
      });
    }
    if (event.type === "proposal_review_started") {
      signals.push({
        id: event.id,
        pipelineId: event.pipeline_id,
        title: track?.sourceLabel ?? event.pipeline_id,
        state: "under_review",
        rationale: "Entrepreneur evaluation has started for this cognition chain.",
        provider: typeof event.provider === "string" ? event.provider : track?.provider,
        model: typeof event.model === "string" ? event.model : track?.model,
        timestamp: event.timestamp,
      });
    }
    if (event.type === "proposal_review_completed") {
      signals.push({
        id: event.id,
        pipelineId: event.pipeline_id,
        title: track?.sourceLabel ?? event.pipeline_id,
        state: "completed",
        rationale: "Entrepreneur evaluation finished. Use the live console and downstream notes for full reasoning.",
        provider: track?.provider,
        model: track?.model,
        timestamp: event.timestamp,
      });
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
