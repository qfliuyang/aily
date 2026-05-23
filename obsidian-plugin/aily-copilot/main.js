const { ItemView, MarkdownRenderer, Notice, Plugin, PluginSettingTab, Setting } = require("obsidian");

const VIEW_TYPE_AILY_COPILOT = "aily-copilot-view";

const DEFAULT_SETTINGS = {
  apiBaseUrl: "http://127.0.0.1:8000",
  apiToken: "",
  useLlm: true,
  activeProjectId: "",
};

module.exports = class AilyCopilotPlugin extends Plugin {
  async onload() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    this.registerView(VIEW_TYPE_AILY_COPILOT, (leaf) => new AilyCopilotView(leaf, this));
    this.addRibbonIcon("sparkles", "Open Aily Copilot", () => this.activateView());
    this.addCommand({
      id: "open-aily-copilot",
      name: "Open Aily Copilot",
      callback: () => this.activateView(),
    });
    this.addCommand({
      id: "ask-aily-about-active-note",
      name: "Ask Aily about active note",
      callback: async () => {
        await this.activateView();
        const view = this.getActiveAilyView();
        if (view) {
          view.seedFromActiveNote();
        }
      },
    });
    this.addSettingTab(new AilyCopilotSettingTab(this.app, this));
  }

  onunload() {
    this.app.workspace.detachLeavesOfType(VIEW_TYPE_AILY_COPILOT);
  }

  async activateView() {
    const existing = this.app.workspace.getLeavesOfType(VIEW_TYPE_AILY_COPILOT)[0];
    if (existing) {
      this.app.workspace.revealLeaf(existing);
      return;
    }
    const leaf = this.app.workspace.getRightLeaf(false);
    await leaf.setViewState({ type: VIEW_TYPE_AILY_COPILOT, active: true });
    this.app.workspace.revealLeaf(leaf);
  }

  getActiveAilyView() {
    const leaf = this.app.workspace.getLeavesOfType(VIEW_TYPE_AILY_COPILOT)[0];
    return leaf && leaf.view instanceof AilyCopilotView ? leaf.view : null;
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async callAily(path, payload = {}, method = "POST") {
    const headers = { "Content-Type": "application/json" };
    if (this.settings.apiToken) {
      headers.Authorization = `Bearer ${this.settings.apiToken}`;
    }
    const response = await fetch(`${this.settings.apiBaseUrl.replace(/\/$/, "")}${path}`, {
      method,
      headers,
      body: method === "GET" ? undefined : JSON.stringify(payload),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Aily API ${response.status}: ${text}`);
    }
    return response.json();
  }
};

class AilyCopilotView extends ItemView {
  constructor(leaf, plugin) {
    super(leaf);
    this.plugin = plugin;
    this.messages = [];
    this.lastAnswer = null;
    this.projects = [];
    this.relevantNotes = [];
    this.pendingProposal = null;
  }

  getViewType() {
    return VIEW_TYPE_AILY_COPILOT;
  }

  getDisplayText() {
    return "Aily Copilot";
  }

  getIcon() {
    return "sparkles";
  }

  async onOpen() {
    await this.refreshProjects();
    this.render();
  }

  async onClose() {}

  render() {
    const container = this.containerEl.children[1];
    container.empty();
    container.addClass("aily-copilot");

    const header = container.createDiv({ cls: "aily-copilot__header" });
    header.createEl("h2", { text: "Aily Copilot" });
    header.createEl("p", { text: "Vault-grounded reasoning, citations, and dossiers." });

    const context = container.createDiv({ cls: "aily-copilot__context" });
    const active = this.app.workspace.getActiveFile();
    context.createSpan({ text: active ? `Active note: ${active.path}` : "No active note" });

    const projectBar = container.createDiv({ cls: "aily-copilot__project" });
    const projectSelect = projectBar.createEl("select");
    projectSelect.createEl("option", { text: "Whole vault", value: "" });
    for (const project of this.projects) {
      projectSelect.createEl("option", { text: project.name || project.id, value: project.id });
    }
    projectSelect.value = this.plugin.settings.activeProjectId || "";
    projectSelect.onchange = async () => {
      this.plugin.settings.activeProjectId = projectSelect.value;
      await this.plugin.saveSettings();
    };
    const refreshButton = projectBar.createEl("button", { text: "Refresh" });
    const createProjectButton = projectBar.createEl("button", { text: "Project From Folder" });
    refreshButton.onclick = async () => {
      await this.refreshProjects();
      this.render();
    };
    createProjectButton.onclick = async () => this.createProjectFromActiveFolder();

    const transcript = container.createDiv({ cls: "aily-copilot__transcript" });
    for (const message of this.messages) {
      const bubble = transcript.createDiv({ cls: `aily-copilot__message aily-copilot__message--${message.role}` });
      bubble.createDiv({ cls: "aily-copilot__role", text: message.role === "user" ? "You" : "Aily" });
      const body = bubble.createDiv({ cls: "aily-copilot__body" });
      MarkdownRenderer.render(this.app, message.content, body, "", this);
    }

    const actions = container.createDiv({ cls: "aily-copilot__actions" });
    const askButton = actions.createEl("button", { text: "Ask" });
    const dossierButton = actions.createEl("button", { text: "Generate Dossier" });
    const draftButton = actions.createEl("button", { text: "Create Draft" });
    dossierButton.disabled = !this.lastAnswer;
    draftButton.disabled = !this.lastAnswer;

    if (this.relevantNotes.length) {
      const relevant = container.createDiv({ cls: "aily-copilot__relevant" });
      relevant.createEl("h3", { text: "Relevant notes" });
      for (const note of this.relevantNotes.slice(0, 6)) {
        const row = relevant.createDiv({ cls: "aily-copilot__source" });
        row.createEl("strong", { text: note.title || note.relative_path });
        row.createEl("span", { text: note.relative_path });
        const reason = (note.relationship_explanations || [])[0];
        if (reason) {
          row.createEl("small", { text: reason.explanation || reason.relationship });
        }
      }
    }

    if (this.pendingProposal) {
      const proposal = container.createDiv({ cls: "aily-copilot__proposal" });
      proposal.createEl("h3", { text: `Draft preview: ${this.pendingProposal.target_path}` });
      proposal.createEl("pre", { text: this.pendingProposal.diff || this.pendingProposal.preview || "" });
      const proposalActions = proposal.createDiv({ cls: "aily-copilot__actions" });
      const applyButton = proposalActions.createEl("button", { text: "Apply" });
      const rejectButton = proposalActions.createEl("button", { text: "Reject" });
      applyButton.onclick = async () => this.applyProposal();
      rejectButton.onclick = async () => this.rejectProposal();
    }

    const input = container.createEl("textarea", {
      cls: "aily-copilot__input",
      attr: { placeholder: "Ask Aily about your vault, active note, or product reasoning..." },
    });
    input.rows = 5;

    askButton.onclick = async () => {
      const text = input.value.trim();
      if (!text) {
        new Notice("Ask Aily a question first.");
        return;
      }
      input.value = "";
      await this.ask(text);
    };
    dossierButton.onclick = async () => {
      await this.generateDossier();
    };
    draftButton.onclick = async () => {
      await this.createDraft();
    };
  }

  seedFromActiveNote() {
    const active = this.app.workspace.getActiveFile();
    const prompt = active
      ? `Explain the strongest evidence and product implications in @note ${active.path}`
      : "Explain the strongest evidence and product implications in this vault.";
    this.ask(prompt);
  }

  async ask(text) {
    const active = this.app.workspace.getActiveFile();
    const searchQuery = active ? `${text} ${active.basename}` : text;
    this.messages.push({ role: "user", content: text });
    this.render();
    try {
      const payload = {
        message: text,
        search_query: searchQuery,
        project_id: this.plugin.settings.activeProjectId || "",
        limit: 8,
        use_llm: this.plugin.settings.useLlm,
      };
      const answer = await this.plugin.callAily("/api/copilot/chat", payload);
      this.lastAnswer = answer;
      this.messages.push({ role: "assistant", content: answer.answer || "No answer returned." });
      await this.refreshRelevantNotes(text);
    } catch (error) {
      this.messages.push({ role: "assistant", content: `Aily request failed: ${error.message}` });
      new Notice("Aily request failed. Check backend and settings.");
    }
    this.render();
  }

  async generateDossier() {
    const active = this.app.workspace.getActiveFile();
    const topic = active ? active.basename : "Aily Copilot dossier";
    try {
      const payload = {
        topic,
        project_id: this.plugin.settings.activeProjectId || "",
        query_terms: [topic],
        seed_claims: this.lastAnswer ? [stripMarkdown(this.lastAnswer.answer || "").slice(0, 800)] : [],
      };
      const dossier = await this.plugin.callAily("/api/copilot/dossiers/generate", payload);
      this.messages.push({
        role: "assistant",
        content: `Dossier generated: [[${dossier.relative_path}|${dossier.title}]]`,
      });
    } catch (error) {
      this.messages.push({ role: "assistant", content: `Dossier generation failed: ${error.message}` });
      new Notice("Dossier generation failed.");
    }
    this.render();
  }

  async refreshProjects() {
    try {
      const payload = await this.plugin.callAily("/api/copilot/projects", {}, "GET");
      this.projects = payload.projects || [];
    } catch (error) {
      this.projects = [];
    }
  }

  async createProjectFromActiveFolder() {
    const active = this.app.workspace.getActiveFile();
    if (!active) {
      new Notice("Open a note first.");
      return;
    }
    const folder = active.parent && active.parent.path ? active.parent.path : "";
    const name = folder ? `Folder: ${folder}` : "Vault project";
    try {
      const payload = await this.plugin.callAily("/api/copilot/projects/upsert", {
        name,
        include_dirs: folder ? [folder] : [],
        source_terms: [active.basename],
      });
      this.plugin.settings.activeProjectId = payload.project.id;
      await this.plugin.saveSettings();
      await this.refreshProjects();
      this.render();
    } catch (error) {
      new Notice(`Project creation failed: ${error.message}`);
    }
  }

  async refreshRelevantNotes(query) {
    const active = this.app.workspace.getActiveFile();
    try {
      const payload = await this.plugin.callAily("/api/copilot/vault/relevant", {
        query,
        seed_paths: active ? [active.path] : [],
        project_id: this.plugin.settings.activeProjectId || "",
        limit: 8,
      });
      this.relevantNotes = payload.recommendations || [];
    } catch (error) {
      this.relevantNotes = [];
    }
  }

  async createDraft() {
    if (!this.lastAnswer) {
      return;
    }
    const active = this.app.workspace.getActiveFile();
    const base = active ? active.basename : "Aily Copilot Answer";
    const title = `${base} - Aily Copilot Brief`;
    const body = [
      `# ${title}`,
      "",
      "Origin: Generated by Aily-Copilot Obsidian plugin after user preview request.",
      "",
      this.lastAnswer.answer || "",
    ].join("\n");
    try {
      const payload = await this.plugin.callAily("/api/copilot/proposals/create", {
        title,
        target_path: `10-Dossiers/${slugify(title)}.md`,
        content: body,
        mode: "create",
        rationale: "User requested a preview-first Aily-Copilot draft from the latest grounded answer.",
        source_citations: this.lastAnswer.citations || [],
      });
      this.pendingProposal = payload.proposal;
    } catch (error) {
      new Notice(`Draft preview failed: ${error.message}`);
    }
    this.render();
  }

  async applyProposal() {
    if (!this.pendingProposal) {
      return;
    }
    try {
      const payload = await this.plugin.callAily("/api/copilot/proposals/apply", {
        proposal_id: this.pendingProposal.id,
      });
      this.pendingProposal = payload.proposal;
      this.messages.push({ role: "assistant", content: `Draft applied: [[${this.pendingProposal.target_path}]]` });
    } catch (error) {
      new Notice(`Apply failed: ${error.message}`);
    }
    this.render();
  }

  async rejectProposal() {
    if (!this.pendingProposal) {
      return;
    }
    try {
      await this.plugin.callAily("/api/copilot/proposals/reject", {
        proposal_id: this.pendingProposal.id,
      });
      this.pendingProposal = null;
      this.messages.push({ role: "assistant", content: "Draft rejected. No vault note was changed." });
    } catch (error) {
      new Notice(`Reject failed: ${error.message}`);
    }
    this.render();
  }
}

class AilyCopilotSettingTab extends PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display() {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "Aily Copilot" });

    new Setting(containerEl)
      .setName("Aily API base URL")
      .setDesc("FastAPI server URL, usually http://127.0.0.1:8000")
      .addText((text) =>
        text
          .setValue(this.plugin.settings.apiBaseUrl)
          .onChange(async (value) => {
            this.plugin.settings.apiBaseUrl = value.trim() || DEFAULT_SETTINGS.apiBaseUrl;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Aily API token")
      .setDesc("Optional token if Aily UI authentication is enabled.")
      .addText((text) =>
        text
          .setPlaceholder("Leave empty for local unauthenticated backend")
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
        toggle
          .setValue(this.plugin.settings.useLlm)
          .onChange(async (value) => {
            this.plugin.settings.useLlm = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Active project ID")
      .setDesc("Optional default project scope used by the Aily Copilot panel.")
      .addText((text) =>
        text
          .setPlaceholder("Leave empty for whole vault")
          .setValue(this.plugin.settings.activeProjectId)
          .onChange(async (value) => {
            this.plugin.settings.activeProjectId = value.trim();
            await this.plugin.saveSettings();
          })
      );
  }
}

function stripMarkdown(text) {
  return String(text || "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[[\]_*`>#-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function slugify(text) {
  return String(text || "aily-copilot-brief")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "aily-copilot-brief";
}
