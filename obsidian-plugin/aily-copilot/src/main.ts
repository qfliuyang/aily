import {
  App,
  ItemView,
  MarkdownRenderer,
  Notice,
  Plugin,
  PluginSettingTab,
  requestUrl,
  Setting,
  TFile,
  WorkspaceLeaf,
} from "obsidian";

const VIEW_TYPE_AILY_COPILOT = "aily-copilot-view";

interface AilyCopilotSettings {
  apiBaseUrl: string;
  apiToken: string;
  useLlm: boolean;
  activeProjectId: string;
}

const DEFAULT_SETTINGS: AilyCopilotSettings = {
  apiBaseUrl: "http://127.0.0.1:8000",
  apiToken: "",
  useLlm: true,
  activeProjectId: "",
};

type ChatMessage = { role: "user" | "assistant" | "system"; content: string };

type AilyResponse<T> = T & { detail?: string };

export default class AilyCopilotPlugin extends Plugin {
  settings: AilyCopilotSettings;

  async onload(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    this.registerView(VIEW_TYPE_AILY_COPILOT, (leaf) => new AilyCopilotView(leaf, this));

    this.addRibbonIcon("bot-message-square", "Open Aily Copilot", () => {
      void this.activateView();
    });

    this.addCommand({
      id: "open-aily-copilot",
      name: "Open Aily Copilot",
      callback: () => void this.activateView(),
    });

    this.addCommand({
      id: "ask-aily-about-active-note",
      name: "Ask Aily about active note",
      callback: async () => {
        await this.activateView();
        const view = this.getAilyView();
        view?.seedFromActiveNote();
      },
    });

    this.addSettingTab(new AilyCopilotSettingTab(this.app, this));
  }

  onunload(): void {
    this.app.workspace.detachLeavesOfType(VIEW_TYPE_AILY_COPILOT);
  }

  async activateView(): Promise<void> {
    const existing = this.app.workspace.getLeavesOfType(VIEW_TYPE_AILY_COPILOT)[0];
    if (existing) {
      this.app.workspace.revealLeaf(existing);
      return;
    }
    const leaf = this.app.workspace.getRightLeaf(false) ?? this.app.workspace.getLeaf(true);
    await leaf.setViewState({ type: VIEW_TYPE_AILY_COPILOT, active: true });
    this.app.workspace.revealLeaf(leaf);
  }

  getAilyView(): AilyCopilotView | null {
    const leaf = this.app.workspace.getLeavesOfType(VIEW_TYPE_AILY_COPILOT)[0];
    return leaf?.view instanceof AilyCopilotView ? leaf.view : null;
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }

  async getAily<T>(path: string): Promise<AilyResponse<T>> {
    return this.callAily<T>(path, undefined, "GET");
  }

  async postAily<T>(path: string, payload: unknown): Promise<AilyResponse<T>> {
    return this.callAily<T>(path, payload, "POST");
  }

  private async callAily<T>(path: string, payload: unknown, method: "GET" | "POST"): Promise<AilyResponse<T>> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (method === "POST") headers["Content-Type"] = "application/json";
    if (this.settings.apiToken) headers.Authorization = `Bearer ${this.settings.apiToken}`;

    const url = `${this.settings.apiBaseUrl.replace(/\/$/, "")}${path}`;
    const response = await requestUrl({
      url,
      method,
      headers,
      body: method === "POST" ? JSON.stringify(payload ?? {}) : undefined,
      throw: false,
    });
    const json = parseJson(response.text) as AilyResponse<T>;
    if (response.status < 200 || response.status >= 300) {
      const detail = typeof json.detail === "string" ? json.detail : response.text || `HTTP ${response.status}`;
      throw new Error(`Aily API ${response.status}: ${detail}`);
    }
    return json;
  }
}

class AilyCopilotView extends ItemView {
  private plugin: AilyCopilotPlugin;
  private messages: ChatMessage[] = [];
  private statusText = "Checking Aily backend...";
  private inputEl?: HTMLTextAreaElement;
  private askButton?: HTMLButtonElement;
  private lastAnswer: any = null;
  private relevantNotes: any[] = [];
  private pendingProposal: any = null;

  constructor(leaf: WorkspaceLeaf, plugin: AilyCopilotPlugin) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType(): string {
    return VIEW_TYPE_AILY_COPILOT;
  }

  getDisplayText(): string {
    return "Aily Copilot";
  }

  getIcon(): string {
    return "bot-message-square";
  }

  async onOpen(): Promise<void> {
    this.render();
    await this.checkBackend();
  }

  render(): void {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("aily-copilot-root");

    const header = container.createDiv({ cls: "aily-header" });
    header.createEl("h2", { text: "Aily Copilot" });
    header.createEl("div", { cls: "aily-status", text: this.statusText });

    const toolbar = container.createDiv({ cls: "aily-toolbar" });
    const checkButton = toolbar.createEl("button", { text: "Check Backend" });
    const dossierButton = toolbar.createEl("button", { text: "Generate Dossier" });
    const draftButton = toolbar.createEl("button", { text: "Create Draft" });
    dossierButton.disabled = !this.lastAnswer;
    draftButton.disabled = !this.lastAnswer;
    checkButton.onclick = () => void this.checkBackend();
    dossierButton.onclick = () => void this.generateDossier();
    draftButton.onclick = () => void this.createDraft();

    const active = this.app.workspace.getActiveFile();
    container.createDiv({ cls: "aily-active-note", text: active ? `Active note: ${active.path}` : "No active note selected" });

    const transcript = container.createDiv({ cls: "aily-transcript" });
    for (const message of this.messages) {
      const bubble = transcript.createDiv({ cls: `aily-message aily-message-${message.role}` });
      bubble.createDiv({ cls: "aily-message-role", text: message.role === "user" ? "You" : "Aily" });
      const body = bubble.createDiv({ cls: "aily-message-body" });
      void MarkdownRenderer.renderMarkdown(message.content, body, "", this);
    }

    if (this.relevantNotes.length > 0) {
      const relevant = container.createDiv({ cls: "aily-panel" });
      relevant.createEl("h3", { text: "Relevant Notes" });
      for (const note of this.relevantNotes.slice(0, 8)) {
        const item = relevant.createDiv({ cls: "aily-relevant-note" });
        item.createEl("strong", { text: note.title || note.relative_path });
        item.createEl("span", { text: note.relative_path || "" });
        const reason = note.relationship_explanations?.[0];
        if (reason) item.createEl("small", { text: reason.explanation || reason.relationship || "Related by content" });
      }
    }

    if (this.pendingProposal) {
      const proposal = container.createDiv({ cls: "aily-panel" });
      proposal.createEl("h3", { text: `Draft Preview: ${this.pendingProposal.target_path}` });
      proposal.createEl("pre", { text: this.pendingProposal.diff || this.pendingProposal.preview || "" });
      const actions = proposal.createDiv({ cls: "aily-toolbar" });
      const apply = actions.createEl("button", { text: "Apply Draft" });
      const reject = actions.createEl("button", { text: "Reject Draft" });
      apply.onclick = () => void this.applyProposal();
      reject.onclick = () => void this.rejectProposal();
    }

    const composer = container.createDiv({ cls: "aily-composer" });
    this.inputEl = composer.createEl("textarea", {
      attr: { placeholder: "Ask Aily about this vault, active note, dossier, product strategy, or evidence chain..." },
    });
    this.inputEl.rows = 5;
    this.inputEl.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        void this.askFromInput();
      }
    });
    this.askButton = composer.createEl("button", { text: "Ask Aily" });
    this.askButton.onclick = () => void this.askFromInput();
  }

  seedFromActiveNote(): void {
    const active = this.app.workspace.getActiveFile();
    const prompt = active
      ? `Explain the strongest evidence, weak assumptions, and product implications in @note ${active.path}`
      : "Explain the strongest evidence and product implications in this vault.";
    void this.ask(prompt);
  }

  private async checkBackend(): Promise<void> {
    try {
      const status = await this.plugin.getAily<any>("/api/copilot/status");
      const features = status.features ? Object.keys(status.features).filter((key) => status.features[key]).join(", ") : "unknown features";
      this.statusText = `Connected: ${status.vault_path}. Features: ${features}`;
    } catch (error) {
      this.statusText = `Backend unavailable: ${(error as Error).message}`;
      new Notice(this.statusText);
    }
    this.render();
  }

  private async askFromInput(): Promise<void> {
    const text = this.inputEl?.value.trim() ?? "";
    if (!text) {
      new Notice("Type a question for Aily first.");
      return;
    }
    if (this.inputEl) this.inputEl.value = "";
    await this.ask(text);
  }

  private async ask(text: string): Promise<void> {
    this.messages.push({ role: "user", content: text });
    this.statusText = "Aily is thinking...";
    this.render();
    try {
      const active = this.app.workspace.getActiveFile();
      const answer = await this.plugin.postAily<any>("/api/copilot/chat", {
        message: text,
        search_query: active ? `${text} ${active.basename}` : text,
        project_id: this.plugin.settings.activeProjectId,
        limit: 8,
        use_llm: this.plugin.settings.useLlm,
      });
      this.lastAnswer = answer;
      this.messages.push({ role: "assistant", content: answer.answer || "Aily returned an empty answer." });
      this.statusText = `Answer grounded: ${answer.grounding_status || "unknown"}; citations: ${(answer.citations || []).length}`;
      await this.loadRelevantNotes(text, active);
    } catch (error) {
      const message = `Aily request failed: ${(error as Error).message}`;
      this.messages.push({ role: "assistant", content: message });
      this.statusText = message;
      new Notice(message, 8000);
    }
    this.render();
  }

  private async loadRelevantNotes(query: string, active: TFile | null): Promise<void> {
    try {
      const response = await this.plugin.postAily<any>("/api/copilot/vault/relevant", {
        query,
        seed_paths: active ? [active.path] : [],
        project_id: this.plugin.settings.activeProjectId,
        limit: 8,
      });
      this.relevantNotes = response.recommendations || [];
    } catch {
      this.relevantNotes = [];
    }
  }

  private async generateDossier(): Promise<void> {
    const active = this.app.workspace.getActiveFile();
    const topic = active?.basename || "Aily Copilot dossier";
    try {
      const response = await this.plugin.postAily<any>("/api/copilot/dossiers/generate", {
        topic,
        project_id: this.plugin.settings.activeProjectId,
        query_terms: [topic],
        seed_claims: this.lastAnswer?.answer ? [stripMarkdown(this.lastAnswer.answer).slice(0, 900)] : [],
      });
      this.messages.push({ role: "assistant", content: `Dossier generated: [[${response.relative_path}|${response.title}]]` });
      this.statusText = `Dossier generated: ${response.relative_path}`;
    } catch (error) {
      this.statusText = `Dossier failed: ${(error as Error).message}`;
      new Notice(this.statusText, 8000);
    }
    this.render();
  }

  private async createDraft(): Promise<void> {
    if (!this.lastAnswer?.answer) return;
    const active = this.app.workspace.getActiveFile();
    const base = active?.basename || "Aily Copilot Answer";
    const title = `${base} - Aily Copilot Brief`;
    const content = [`# ${title}`, "", "Origin: Generated by Aily-Copilot Obsidian plugin after user preview request.", "", this.lastAnswer.answer].join("\n");
    try {
      const response = await this.plugin.postAily<any>("/api/copilot/proposals/create", {
        title,
        target_path: `10-Dossiers/${slugify(title)}.md`,
        content,
        mode: "create",
        rationale: "User requested a preview-first Aily-Copilot draft from the latest grounded answer.",
        source_citations: this.lastAnswer.citations || [],
      });
      this.pendingProposal = response.proposal;
      this.statusText = `Draft staged: ${response.proposal.target_path}`;
    } catch (error) {
      this.statusText = `Draft preview failed: ${(error as Error).message}`;
      new Notice(this.statusText, 8000);
    }
    this.render();
  }

  private async applyProposal(): Promise<void> {
    if (!this.pendingProposal?.id) return;
    try {
      const response = await this.plugin.postAily<any>("/api/copilot/proposals/apply", { proposal_id: this.pendingProposal.id });
      this.pendingProposal = response.proposal;
      this.messages.push({ role: "assistant", content: `Draft applied: [[${response.proposal.target_path}]]` });
      this.statusText = `Draft applied: ${response.proposal.target_path}`;
    } catch (error) {
      this.statusText = `Apply failed: ${(error as Error).message}`;
      new Notice(this.statusText, 8000);
    }
    this.render();
  }

  private async rejectProposal(): Promise<void> {
    if (!this.pendingProposal?.id) return;
    try {
      await this.plugin.postAily<any>("/api/copilot/proposals/reject", { proposal_id: this.pendingProposal.id });
      this.pendingProposal = null;
      this.messages.push({ role: "assistant", content: "Draft rejected. No vault note was changed." });
      this.statusText = "Draft rejected.";
    } catch (error) {
      this.statusText = `Reject failed: ${(error as Error).message}`;
      new Notice(this.statusText, 8000);
    }
    this.render();
  }
}

class AilyCopilotSettingTab extends PluginSettingTab {
  plugin: AilyCopilotPlugin;

  constructor(app: App, plugin: AilyCopilotPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "Aily Copilot" });

    new Setting(containerEl)
      .setName("Aily API base URL")
      .setDesc("FastAPI server URL. Default: http://127.0.0.1:8000")
      .addText((text) =>
        text.setValue(this.plugin.settings.apiBaseUrl).onChange(async (value) => {
          this.plugin.settings.apiBaseUrl = value.trim() || DEFAULT_SETTINGS.apiBaseUrl;
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName("Aily API token")
      .setDesc("Optional token if Aily UI authentication is enabled.")
      .addText((text) =>
        text
          .setPlaceholder("Leave empty for local backend")
          .setValue(this.plugin.settings.apiToken)
          .onChange(async (value) => {
            this.plugin.settings.apiToken = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Use LLM for chat")
      .setDesc("When disabled, Aily returns deterministic extractive answers from vault evidence.")
      .addToggle((toggle) =>
        toggle.setValue(this.plugin.settings.useLlm).onChange(async (value) => {
          this.plugin.settings.useLlm = value;
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName("Active project ID")
      .setDesc("Optional Aily project scope. Leave empty for whole vault.")
      .addText((text) =>
        text.setValue(this.plugin.settings.activeProjectId).onChange(async (value) => {
          this.plugin.settings.activeProjectId = value.trim();
          await this.plugin.saveSettings();
        })
      );
  }
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text || "{}");
  } catch {
    return {};
  }
}

function stripMarkdown(text: string): string {
  return String(text || "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[\[\]_*`>#-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function slugify(text: string): string {
  return (
    String(text || "aily-copilot-brief")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80) || "aily-copilot-brief"
  );
}
