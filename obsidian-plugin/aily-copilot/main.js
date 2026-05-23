const { ItemView, MarkdownRenderer, Notice, Plugin, PluginSettingTab, Setting } = require("obsidian");

const VIEW_TYPE_AILY_COPILOT = "aily-copilot-view";

const DEFAULT_SETTINGS = {
  apiBaseUrl: "http://127.0.0.1:8000",
  apiToken: "",
  useLlm: true,
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

  async callAily(path, payload) {
    const headers = { "Content-Type": "application/json" };
    if (this.settings.apiToken) {
      headers.Authorization = `Bearer ${this.settings.apiToken}`;
    }
    const response = await fetch(`${this.settings.apiBaseUrl.replace(/\/$/, "")}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
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
    dossierButton.disabled = !this.lastAnswer;

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
        limit: 8,
        use_llm: this.plugin.settings.useLlm,
      };
      const answer = await this.plugin.callAily("/api/copilot/chat", payload);
      this.lastAnswer = answer;
      this.messages.push({ role: "assistant", content: answer.answer || "No answer returned." });
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
  }
}

function stripMarkdown(text) {
  return String(text || "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[[\]_*`>#-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
