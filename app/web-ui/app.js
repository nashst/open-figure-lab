class OpenFigureLabApp {
    constructor() {
        this.apiBase = "";
        this.isRunning = false;
        this.projectName = "soc_proxy_fig2";
        this.agents = [];
        this.selectedAgentId = null;
        this.selectedModel = "default";
        this.selectedReasoning = "default";
    }

    init() {
        this.cacheElements();
        this.bindEvents();
        this.scanAgents();
    }

    cacheElements() {
        this.entryView = document.getElementById("entryView");
        this.labView = document.getElementById("labView");
        this.agentSetupForm = document.getElementById("agentSetupForm");
        this.agentList = document.getElementById("agentList");
        this.btnRescanAgents = document.getElementById("btnRescanAgents");
        this.btnLaunchLab = document.getElementById("btnLaunchLab");
        this.modelSelect = document.getElementById("modelSelect");
        this.reasoningSelect = document.getElementById("reasoningSelect");
        this.reasoningField = document.getElementById("reasoningField");
        this.setupHint = document.getElementById("setupHint");
        this.selectedAgentName = document.getElementById("selectedAgentName");
        this.selectedModelName = document.getElementById("selectedModelName");
        this.btnValidate = document.getElementById("btnValidate");
        this.btnRender = document.getElementById("btnRender");
        this.btnQA = document.getElementById("btnQA");
        this.btnRefresh = document.getElementById("btnRefresh");
        this.btnClearLog = document.getElementById("btnClearLog");
        this.statusPill = document.getElementById("statusPill");
        this.previewImage = document.getElementById("previewImage");
        this.previewEmpty = document.getElementById("previewEmpty");
        this.previewInfo = document.getElementById("previewInfo");
        this.specContent = document.getElementById("specContent");
        this.dataContent = document.getElementById("dataContent");
        this.qaContent = document.getElementById("qaContent");
        this.runLog = document.getElementById("runLog");
        this.tabs = document.querySelectorAll(".tab");
    }

    bindEvents() {
        this.agentSetupForm.addEventListener("submit", (event) => {
            event.preventDefault();
            this.launchLab();
        });
        this.btnRescanAgents.addEventListener("click", () => this.scanAgents(true));
        this.modelSelect.addEventListener("change", () => {
            this.selectedModel = this.modelSelect.value || "default";
            this.updateSelectedAgentSummary();
        });
        this.reasoningSelect.addEventListener("change", () => {
            this.selectedReasoning = this.reasoningSelect.value || "default";
            this.updateSelectedAgentSummary();
        });
        this.btnValidate.addEventListener("click", () => this.executeCommand("validate"));
        this.btnRender.addEventListener("click", () => this.executeCommand("render"));
        this.btnQA.addEventListener("click", () => this.executeCommand("qa"));
        this.btnRefresh.addEventListener("click", () => this.loadPreview());
        this.btnClearLog.addEventListener("click", () => this.clearLog());
        this.tabs.forEach((tab) => {
            tab.addEventListener("click", () => this.switchTab(tab));
        });
    }

    async scanAgents(force = false) {
        this.agentList.innerHTML = '<div class="agent-loading">Scanning local PATH for agent CLIs...</div>';
        this.btnLaunchLab.disabled = true;
        this.setupHint.textContent = "Checking local CLI adapters...";
        try {
            const res = await fetch(`${this.apiBase}/api/agents${force ? "?refresh=1" : ""}`);
            const data = await res.json();
            this.agents = Array.isArray(data.agents) ? data.agents : [];
            const firstAvailable = this.agents.find((agent) => agent.available);
            this.selectedAgentId = firstAvailable ? firstAvailable.id : null;
            this.renderAgentPicker();
        } catch (err) {
            this.agentList.innerHTML = `<div class="agent-loading error">Failed to scan agents: ${this.escapeHtml(err.message)}</div>`;
            this.setupHint.textContent = "The local API server could not return agent information.";
        }
    }

    renderAgentPicker() {
        if (this.agents.length === 0) {
            this.agentList.innerHTML = '<div class="agent-loading">No adapter definitions loaded.</div>';
            this.setupHint.textContent = "No local agents were detected.";
            return;
        }

        this.agentList.innerHTML = "";
        for (const agent of this.agents) {
            const row = document.createElement("button");
            row.type = "button";
            row.className = `agent-option ${agent.available ? "available" : "missing"} ${agent.id === this.selectedAgentId ? "active" : ""}`;
            row.disabled = !agent.available;
            row.innerHTML = `
                <span>
                    <strong>${this.escapeHtml(agent.name)}</strong>
                    <small>${this.escapeHtml(agent.version || agent.path || "Not detected")}</small>
                </span>
                <em>${agent.available ? "Available" : "Missing"}</em>
            `;
            row.addEventListener("click", () => {
                this.selectedAgentId = agent.id;
                this.renderAgentPicker();
            });
            this.agentList.appendChild(row);
        }

        const selected = this.getSelectedAgent();
        this.btnLaunchLab.disabled = !selected;
        this.setupHint.textContent = selected
            ? "Agent selected. Choose a model or keep the CLI default."
            : "Install OpenCode, Claude Code, Codex, Cursor Agent, or Gemini CLI if no agent is available.";
        this.renderModelPicker(selected);
    }

    renderModelPicker(agent) {
        const models = agent && Array.isArray(agent.models) && agent.models.length > 0
            ? agent.models
            : [{ id: "default", label: "Default (CLI config)" }];
        this.modelSelect.innerHTML = "";
        for (const model of models) {
            const option = document.createElement("option");
            option.value = model.id;
            option.textContent = model.label || model.id;
            this.modelSelect.appendChild(option);
        }
        this.selectedModel = models[0].id;

        const reasoningOptions = agent && Array.isArray(agent.reasoningOptions) ? agent.reasoningOptions : [];
        this.reasoningSelect.innerHTML = "";
        for (const optionDef of reasoningOptions) {
            const option = document.createElement("option");
            option.value = optionDef.id;
            option.textContent = optionDef.label || optionDef.id;
            this.reasoningSelect.appendChild(option);
        }
        this.reasoningField.classList.toggle("hidden", reasoningOptions.length === 0);
        this.selectedReasoning = reasoningOptions.length > 0 ? reasoningOptions[0].id : "default";
    }

    launchLab() {
        const selected = this.getSelectedAgent();
        if (!selected) {
            return;
        }
        this.entryView.classList.add("hidden");
        this.labView.classList.remove("hidden");
        this.updateSelectedAgentSummary();
        this.loadInitialData();
        this.addLogEntry("Workbench initialized", "output");
        this.addLogEntry(`Agent runtime: ${selected.name} / ${this.selectedModel}`, "command");
    }

    getSelectedAgent() {
        return this.agents.find((agent) => agent.id === this.selectedAgentId && agent.available) || null;
    }

    updateSelectedAgentSummary() {
        const selected = this.getSelectedAgent();
        if (!selected) {
            return;
        }
        this.selectedAgentName.textContent = selected.name;
        const reasoning = this.selectedReasoning && this.selectedReasoning !== "default" ? ` / ${this.selectedReasoning}` : "";
        this.selectedModelName.textContent = `${this.selectedModel || "default"}${reasoning}`;
    }

    async loadInitialData() {
        await Promise.all([
            this.fetchSpec(),
            this.fetchDataManifest(),
            this.fetchQAReport()
        ]);
        this.loadPreview();
    }

    async fetchSpec() {
        try {
            const res = await fetch(`${this.apiBase}/api/spec`);
            const data = await res.json();
            this.specContent.textContent = res.ok && data.content ? data.content : `# ${data.error || "No spec found"}`;
        } catch (err) {
            this.specContent.textContent = `# Failed to load spec: ${err.message}`;
        }
    }

    async fetchDataManifest() {
        try {
            const res = await fetch(`${this.apiBase}/api/data-manifest`);
            const data = await res.json();
            this.dataContent.textContent = res.ok && data.content ? data.content : `# ${data.error || "No data manifest found"}`;
        } catch (err) {
            this.dataContent.textContent = `# Failed to load data manifest: ${err.message}`;
        }
    }

    async fetchQAReport() {
        try {
            const res = await fetch(`${this.apiBase}/api/qa-report`);
            const data = await res.json();
            if (res.ok && data.content) {
                this.renderQAReport(data.content);
            } else {
                this.qaContent.innerHTML = '<p class="qa-line">No QA report. Run QA first.</p>';
            }
        } catch (err) {
            this.qaContent.innerHTML = `<p class="qa-error">Failed to load: ${this.escapeHtml(err.message)}</p>`;
        }
    }

    renderQAReport(content) {
        const lines = content.split("\n");
        let html = "";
        for (const line of lines) {
            if (line.startsWith("# ")) {
                html += `<h3>${this.escapeHtml(line.slice(2))}</h3>`;
            } else if (line.startsWith("## ")) {
                html += `<h4>${this.escapeHtml(line.slice(3))}</h4>`;
            } else if (line.startsWith("- PASS:")) {
                html += `<div class="qa-pass">PASS: ${this.escapeHtml(line.slice(7).trim())}</div>`;
            } else if (line.startsWith("- ERROR:")) {
                html += `<div class="qa-error">ERROR: ${this.escapeHtml(line.slice(8).trim())}</div>`;
            } else if (line.startsWith("- WARNING:")) {
                html += `<div class="qa-warning">WARNING: ${this.escapeHtml(line.slice(10).trim())}</div>`;
            } else if (line.trim()) {
                html += `<div class="qa-line">${this.escapeHtml(line)}</div>`;
            }
        }
        this.qaContent.innerHTML = html;
    }

    loadPreview() {
        const imgUrl = `${this.apiBase}/outputs/${this.projectName}.png?t=${Date.now()}`;
        this.previewImage.onload = () => {
            this.previewImage.style.display = "block";
            this.previewEmpty.style.display = "none";
            this.previewInfo.textContent = `${this.projectName}.png`;
        };
        this.previewImage.onerror = () => {
            this.previewImage.style.display = "none";
            this.previewEmpty.style.display = "flex";
            this.previewInfo.textContent = "No output loaded";
        };
        this.previewImage.src = imgUrl;
    }

    async executeCommand(command) {
        if (this.isRunning) {
            return;
        }

        this.isRunning = true;
        this.setStatus("running", `Running ${command}`);
        this.disableButtons(true);
        this.addLogEntry(`$ ofl ${command} examples/${this.projectName}`, "command");

        try {
            const res = await fetch(`${this.apiBase}/api/${command}`, { method: "POST" });
            const data = await res.json();

            if (data.success === true) {
                this.addLogEntry(data.stdout || `${command} completed`, "success");
            } else {
                if (data.stderr) {
                    this.addLogEntry(data.stderr, "error");
                }
                if (data.stdout) {
                    this.addLogEntry(data.stdout, "output");
                }
            }

            await this.refreshAfterCommand(command);
            this.setStatus(data.success === true ? "ready" : "error", data.success === true ? "Ready" : "Failed");
        } catch (err) {
            this.addLogEntry(`Error: ${err.message}`, "error");
            this.setStatus("error", "Failed");
        } finally {
            this.isRunning = false;
            this.disableButtons(false);
        }
    }

    async refreshAfterCommand(command) {
        if (command === "render") {
            this.loadPreview();
        }
        if (command === "qa") {
            await this.fetchQAReport();
        }
    }

    setStatus(className, text) {
        this.statusPill.className = `status-pill ${className === "running" ? "running" : ""} ${className === "error" ? "error" : ""}`.trim();
        this.statusPill.textContent = text;
    }

    disableButtons(disabled) {
        this.btnValidate.disabled = disabled;
        this.btnRender.disabled = disabled;
        this.btnQA.disabled = disabled;
    }

    switchTab(selectedTab) {
        this.tabs.forEach((tab) => tab.classList.remove("active"));
        selectedTab.classList.add("active");

        const tabName = selectedTab.dataset.tab;
        this.specContent.classList.toggle("hidden", tabName !== "spec");
        this.dataContent.classList.toggle("hidden", tabName !== "data");
        this.qaContent.classList.toggle("hidden", tabName !== "qa");
    }

    addLogEntry(message, type = "output") {
        const entry = document.createElement("div");
        entry.className = `log-entry log-${type}`;

        const time = document.createElement("span");
        time.className = "log-time";
        time.textContent = new Date().toLocaleTimeString();

        const msg = document.createElement("span");
        msg.className = "log-msg";
        msg.textContent = message;

        entry.appendChild(time);
        entry.appendChild(msg);
        this.runLog.appendChild(entry);
        this.runLog.scrollTop = this.runLog.scrollHeight;
    }

    clearLog() {
        this.runLog.innerHTML = "";
    }

    escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const app = new OpenFigureLabApp();
    app.init();
});
