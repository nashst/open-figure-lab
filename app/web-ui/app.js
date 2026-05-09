class OpenFigureLabApp {
    constructor() {
        this.apiBase = "";
        this.isRunning = false;
        this.projects = [];
        this.projectName = "soc_proxy_fig2";
        this.selectedProject = "soc_proxy_fig2";
        this.agents = [];
        this.selectedAgentId = null;
        this.selectedModel = "default";
        this.selectedReasoning = "default";
        // Skills state
        this.skills = [];
        this.selectedSkillIds = new Set();
        // Agent run polling state
        this.activeRunId = null;
        this.lastEventId = 0;
        this.pollTimer = null;
        this.pollRetries = 0;
        this.MAX_POLL_RETRIES = 3;
        this.POLL_INTERVAL_MS = 1000;
    }

    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadSessionAndProjects();
    }

    cacheElements() {
        this.entryView = document.getElementById("entryView");
        this.labView = document.getElementById("labView");
        this.agentSetupForm = document.getElementById("agentSetupForm");
        this.agentList = document.getElementById("agentList");
        this.btnRescanAgents = document.getElementById("btnRescanAgents");
        this.btnLaunchLab = document.getElementById("btnLaunchLab");
        this.projectSelect = document.getElementById("projectSelect");
        this.modelSelect = document.getElementById("modelSelect");
        this.reasoningSelect = document.getElementById("reasoningSelect");
        this.reasoningField = document.getElementById("reasoningField");
        this.setupHint = document.getElementById("setupHint");
        this.setupProjectName = document.getElementById("setupProjectName");
        this.setupProjectDesc = document.getElementById("setupProjectDesc");
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
        this.commandInput = document.getElementById("commandInput");
        this.btnSendPrompt = document.getElementById("btnSendPrompt");
        this.btnCancelRun = document.getElementById("btnCancelRun");
        this.agentThread = document.querySelector(".agent-thread");
        this.skillsList = document.getElementById("skillsList");
        this.navItems = document.querySelectorAll("[data-nav]");
        this.plannedButtons = document.querySelectorAll("[data-planned]");
        this.buildStateSummary = document.getElementById("buildStateSummary");
        this.capSpec = document.getElementById("capSpec");
        this.capData = document.getElementById("capData");
        this.capPreview = document.getElementById("capPreview");
        this.capQA = document.getElementById("capQA");
        this.capSkills = document.getElementById("capSkills");
        this.capAgentRuns = document.getElementById("capAgentRuns");
    }

    bindEvents() {
        this.agentSetupForm.addEventListener("submit", (event) => {
            event.preventDefault();
            this.launchLab();
        });
        this.btnRescanAgents.addEventListener("click", () => this.scanAgents(true));
        this.projectSelect.addEventListener("change", () => {
            this.selectedProject = this.projectSelect.value || "soc_proxy_fig2";
            this.projectName = this.selectedProject;
            this.updateSetupSummary();
            this.saveSessionConfig();
        });
        this.modelSelect.addEventListener("change", () => {
            this.selectedModel = this.modelSelect.value || "default";
            this.updateSelectedAgentSummary();
            this.saveSessionConfig();
        });
        this.reasoningSelect.addEventListener("change", () => {
            this.selectedReasoning = this.reasoningSelect.value || "default";
            this.updateSelectedAgentSummary();
            this.saveSessionConfig();
        });
        this.btnValidate.addEventListener("click", () => this.executeCommand("validate"));
        this.btnRender.addEventListener("click", () => this.executeCommand("render"));
        this.btnQA.addEventListener("click", () => this.executeCommand("qa"));
        this.btnRefresh.addEventListener("click", () => this.loadPreview());
        this.btnClearLog.addEventListener("click", () => this.clearLog());
        this.tabs.forEach((tab) => {
            tab.addEventListener("click", () => this.switchTab(tab));
        });
        this.commandInput.addEventListener("input", () => {
            this.btnSendPrompt.disabled = !this.commandInput.value.trim();
        });
        this.btnSendPrompt.addEventListener("click", () => this.sendAgentPrompt());
        this.btnCancelRun.addEventListener("click", () => this.cancelAgentRun());
        this.navItems.forEach((item) => {
            item.addEventListener("click", () => this.handleNav(item));
        });
        this.plannedButtons.forEach((button) => {
            button.addEventListener("click", () => this.showPlanned(button.dataset.planned));
        });
        this.commandInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (this.commandInput.value.trim()) {
                    this.sendAgentPrompt();
                }
            }
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

    async loadSessionAndProjects() {
        try {
            const [projectsRes, configRes] = await Promise.all([
                fetch(`${this.apiBase}/api/projects`),
                fetch(`${this.apiBase}/api/session-config`),
            ]);
            const projectsData = await projectsRes.json();
            const config = await configRes.json();
            this.projects = Array.isArray(projectsData.projects) ? projectsData.projects : [];
            this.selectedProject = config.project || "soc_proxy_fig2";
            this.projectName = this.selectedProject;
            this.renderProjectPicker();
            this.updateSetupSummary();
        } catch (err) {
            console.error("Failed to load session/projects:", err);
        }
        this.scanAgents();
        this.loadSkills();
    }

    async loadSkills() {
        try {
            const res = await fetch(`${this.apiBase}/api/skills`);
            const data = await res.json();
            this.skills = Array.isArray(data.skills) ? data.skills : [];
            // Initialize selected skills from enabled defaults
            this.selectedSkillIds = new Set(
                this.skills.filter(s => s.enabled).map(s => s.id)
            );
            this.renderSkills();
            this.updateCapability("skills", this.skills.length > 0 ? `${this.skills.length} loaded` : "Missing", this.skills.length > 0);
        } catch (err) {
            console.error("Failed to load skills:", err);
            this.updateCapability("skills", "Failed", false);
        }
    }

    renderSkills() {
        if (!this.skillsList) return;
        this.skillsList.innerHTML = "";
        for (const skill of this.skills) {
            const toggle = document.createElement("div");
            toggle.className = `skill-toggle ${this.selectedSkillIds.has(skill.id) ? "active" : ""}`;

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.id = `skill-${skill.id}`;
            checkbox.checked = this.selectedSkillIds.has(skill.id);
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) {
                    this.selectedSkillIds.add(skill.id);
                    toggle.classList.add("active");
                } else {
                    this.selectedSkillIds.delete(skill.id);
                    toggle.classList.remove("active");
                }
            });

            const label = document.createElement("label");
            label.htmlFor = `skill-${skill.id}`;
            label.textContent = skill.title;
            label.title = skill.description;

            toggle.appendChild(checkbox);
            toggle.appendChild(label);
            this.skillsList.appendChild(toggle);
        }
    }

    renderProjectPicker() {
        this.projectSelect.innerHTML = "";
        for (const proj of this.projects) {
            const option = document.createElement("option");
            option.value = proj.name;
            option.textContent = proj.name;
            if (proj.name === this.selectedProject) {
                option.selected = true;
            }
            this.projectSelect.appendChild(option);
        }
        if (this.projects.length === 0) {
            const option = document.createElement("option");
            option.value = this.selectedProject;
            option.textContent = this.selectedProject;
            this.projectSelect.appendChild(option);
        }
    }

    updateSetupSummary() {
        if (this.setupProjectName) {
            this.setupProjectName.textContent = this.selectedProject;
        }
        if (this.setupProjectDesc) {
            this.setupProjectDesc.textContent = "Figure project";
        }
    }

    async saveSessionConfig() {
        try {
            await fetch(`${this.apiBase}/api/session-config`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project: this.selectedProject,
                    agentId: this.selectedAgentId,
                    model: this.selectedModel,
                    reasoning: this.selectedReasoning,
                }),
            });
        } catch (err) {
            console.error("Failed to save session config:", err);
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

    async launchLab() {
        const selected = this.getSelectedAgent();
        if (!selected) {
            return;
        }
        this.projectName = this.selectedProject;
        await this.saveSessionConfig();
        this.entryView.classList.add("hidden");
        this.labView.classList.remove("hidden");
        document.getElementById("projectName").textContent = this.projectName;
        this.updateSelectedAgentSummary();
        this.loadInitialData();
        this.addLogEntry("Workbench initialized", "output");
        this.addLogEntry(`Project: ${this.projectName}`, "command");
        this.addLogEntry(`Agent runtime: ${selected.name} / ${this.selectedModel}`, "command");
        this.refreshCapabilitySummary();
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
            this.updateCapability("spec", res.ok && data.content ? "Loaded" : "Missing", res.ok && data.content);
        } catch (err) {
            this.specContent.textContent = `# Failed to load spec: ${err.message}`;
            this.updateCapability("spec", "Failed", false);
        }
    }

    async fetchDataManifest() {
        try {
            const res = await fetch(`${this.apiBase}/api/data-manifest`);
            const data = await res.json();
            this.dataContent.textContent = res.ok && data.content ? data.content : `# ${data.error || "No data manifest found"}`;
            this.updateCapability("data", res.ok && data.content ? "Loaded" : "Missing", res.ok && data.content);
        } catch (err) {
            this.dataContent.textContent = `# Failed to load data manifest: ${err.message}`;
            this.updateCapability("data", "Failed", false);
        }
    }

    async fetchQAReport() {
        try {
            const res = await fetch(`${this.apiBase}/api/qa-report`);
            const data = await res.json();
            if (res.ok && data.content) {
                this.renderQAReport(data.content);
                this.updateCapability("qa", "Loaded", true);
            } else {
                this.qaContent.innerHTML = '<p class="qa-line">No QA report. Run QA first.</p>';
                this.updateCapability("qa", "Not run", false);
            }
        } catch (err) {
            this.qaContent.innerHTML = `<p class="qa-error">Failed to load: ${this.escapeHtml(err.message)}</p>`;
            this.updateCapability("qa", "Failed", false);
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
            this.updateCapability("preview", "Loaded", true);
        };
        this.previewImage.onerror = () => {
            this.previewImage.style.display = "none";
            this.previewEmpty.style.display = "flex";
            this.previewInfo.textContent = "No output loaded";
            this.updateCapability("preview", "Missing", false);
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

    async sendAgentPrompt() {
        const prompt = this.commandInput.value.trim();
        if (!prompt || this.activeRunId) {
            return;
        }

        this.setAgentUIState(true);
        this.appendAgentMessage(prompt, "user");
        this.commandInput.value = "";

        try {
            this.setStatus("running", "Starting agent");
            const skillIds = Array.from(this.selectedSkillIds);
            const res = await fetch(`${this.apiBase}/api/agent-runs`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    agentId: this.selectedAgentId,
                    model: this.selectedModel,
                    reasoning: this.selectedReasoning,
                    project: this.projectName,
                    prompt: prompt,
                    skillIds: skillIds,
                }),
            });
            const data = await res.json();

            if (!res.ok) {
                this.appendAgentMessage(`Error: ${data.error || "Request failed"}`, "system");
                this.addLogEntry(`Agent run rejected: ${data.error || res.status}`, "error");
                this.setStatus("error", "Failed");
                this.setAgentUIState(false);
                return;
            }

            this.activeRunId = data.id;
            this.lastEventId = 0;
            this.pollRetries = 0;
            this.addLogEntry(`Run ${data.id} created — ${data.status}`, "command");
            this.updateCapability("agentRuns", "Running", true);
            this.setStatus("running", `Agent running (${data.id})`);

            // Start polling
            this.pollEvents();
        } catch (err) {
            this.appendAgentMessage(`Error: ${err.message}`, "system");
            this.addLogEntry(`Agent run error: ${err.message}`, "error");
            this.setStatus("error", "Failed");
            this.setAgentUIState(false);
        }
    }

    async pollEvents() {
        if (!this.activeRunId) {
            return;
        }

        try {
            const url = `${this.apiBase}/api/agent-runs/${this.activeRunId}/events?after=${this.lastEventId}`;
            const res = await fetch(url);

            if (!res.ok) {
                this.pollRetries++;
                if (this.pollRetries >= this.MAX_POLL_RETRIES) {
                    this.addLogEntry(`Poll failed ${this.pollRetries} times — stopping`, "error");
                    this.appendAgentMessage("Error: lost connection to agent run", "system");
                    this.stopPolling("error");
                    return;
                }
                // Retry after interval
                this.pollTimer = setTimeout(() => this.pollEvents(), this.POLL_INTERVAL_MS);
                return;
            }

            // Reset retry counter on success
            this.pollRetries = 0;

            const text = await res.text();
            const events = this.parseSSE(text);

            for (const evt of events) {
                this.lastEventId = Math.max(this.lastEventId, evt.id);
                this.handleAgentEvent(evt);
            }
        } catch (err) {
            this.pollRetries++;
            if (this.pollRetries >= this.MAX_POLL_RETRIES) {
                this.addLogEntry(`Poll error ${this.pollRetries} times — stopping: ${err.message}`, "error");
                this.appendAgentMessage(`Error: ${err.message}`, "system");
                this.stopPolling("error");
                return;
            }
        }

        // Schedule next poll if still active
        if (this.activeRunId) {
            this.pollTimer = setTimeout(() => this.pollEvents(), this.POLL_INTERVAL_MS);
        }
    }

    parseSSE(text) {
        const events = [];
        let currentId = 0;
        let currentType = "message";
        let currentData = "";

        for (const line of text.split("\n")) {
            if (line.startsWith("id: ")) {
                currentId = parseInt(line.slice(4), 10) || 0;
            } else if (line.startsWith("event: ")) {
                currentType = line.slice(7);
            } else if (line.startsWith("data: ")) {
                currentData = line.slice(6);
            } else if (line === "") {
                // End of event block
                if (currentData) {
                    let parsed = null;
                    try {
                        parsed = JSON.parse(currentData);
                    } catch {
                        // Not JSON, use raw
                    }
                    events.push({
                        id: currentId,
                        type: currentType,
                        data: parsed,
                        detail: parsed ? parsed.detail : currentData,
                    });
                }
                currentId = 0;
                currentType = "message";
                currentData = "";
            }
        }

        // Handle trailing event without final blank line
        if (currentData) {
            let parsed = null;
            try {
                parsed = JSON.parse(currentData);
            } catch {
                // Not JSON
            }
            events.push({
                id: currentId,
                type: currentType,
                data: parsed,
                detail: parsed ? parsed.detail : currentData,
            });
        }

        return events;
    }

    handleAgentEvent(evt) {
        const detail = evt.detail || "";

        switch (evt.type) {
            case "created":
                // Already logged on POST response
                break;

            case "running":
                this.addLogEntry(`Run started`, "command");
                this.setStatus("running", `Agent running (${this.activeRunId})`);
                break;

            case "stdout":
                if (detail) {
                    this.appendAgentMessage(detail, "system");
                }
                break;

            case "stderr":
                if (detail) {
                    this.appendAgentMessage(detail, "system");
                }
                break;

            case "completed":
                this.addLogEntry(`Run ${this.activeRunId} completed (exit 0)`, "success");
                this.setStatus("ready", "Ready");
                this.stopPolling("completed");
                this.refreshAfterAgentRun();
                break;

            case "failed":
                this.addLogEntry(`Run ${this.activeRunId} failed${detail ? ` — ${detail}` : ""}`, "error");
                this.setStatus("error", "Failed");
                this.stopPolling("failed");
                this.refreshAfterAgentRun();
                break;

            case "cancelled":
                this.addLogEntry(`Run ${this.activeRunId} cancelled`, "command");
                this.setStatus("ready", "Cancelled");
                this.stopPolling("cancelled");
                this.refreshAfterAgentRun();
                break;

            case "verification_started":
                this.addLogEntry("Verification started: validate -> render -> qa", "command");
                this.setStatus("running", "Verifying...");
                break;

            case "verification_step":
                if (evt.data) {
                    const step = evt.data.step || "unknown";
                    const stepStatus = evt.data.status || "unknown";
                    if (stepStatus === "running") {
                        this.addLogEntry(`  Running ${step}...`, "output");
                    } else if (stepStatus === "passed") {
                        this.addLogEntry(`  ${step} passed`, "success");
                    } else if (stepStatus === "failed") {
                        this.addLogEntry(`  ${step} failed (exit ${evt.data.returncode || "?"})`, "error");
                    }
                }
                break;

            case "verification_passed":
                this.addLogEntry("Verification passed: validate/render/qa", "success");
                this.setStatus("ready", "Verified");
                // Refresh QA report and preview after verification
                this.fetchQAReport();
                this.loadPreview();
                break;

            case "verification_failed":
                this.addLogEntry("Verification failed", "error");
                if (evt.data && evt.data.steps) {
                    const failedSteps = evt.data.steps.filter(s => !s.success);
                    for (const step of failedSteps) {
                        this.appendAgentMessage(`Verification failed at: ${step.name}`, "system");
                    }
                }
                this.setStatus("error", "Verification failed");
                // Still refresh QA report to show partial results
                this.fetchQAReport();
                break;

            default:
                // Unknown event type, log it
                if (detail) {
                    this.addLogEntry(`[${evt.type}] ${detail}`, "output");
                }
                break;
        }
    }

    stopPolling(reason) {
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
        // Store runId before clearing for fileChanges fetch
        this._lastCompletedRunId = this.activeRunId;
        this.activeRunId = null;
        this.lastEventId = 0;
        this.pollRetries = 0;
        this.setAgentUIState(false);
        this.updateCapability("agentRuns", reason === "completed" ? "Ready" : reason, reason !== "error" && reason !== "failed");
    }

    async cancelAgentRun() {
        if (!this.activeRunId) {
            return;
        }

        const runId = this.activeRunId;
        this.btnCancelRun.disabled = true;

        try {
            const res = await fetch(`${this.apiBase}/api/agent-runs/${runId}/cancel`, {
                method: "POST",
            });
            const data = await res.json();

            if (!res.ok) {
                this.addLogEntry(`Cancel failed: ${data.error || res.status}`, "error");
                this.btnCancelRun.disabled = false;
                return;
            }

            this.addLogEntry(`Cancel requested for ${runId}`, "command");
            // Polling will pick up the cancelled event
        } catch (err) {
            this.addLogEntry(`Cancel error: ${err.message}`, "error");
            this.btnCancelRun.disabled = false;
        }
    }

    setAgentUIState(running) {
        this.btnSendPrompt.disabled = running;
        this.commandInput.disabled = running;
        if (running) {
            this.btnCancelRun.classList.remove("hidden");
            this.btnCancelRun.disabled = false;
        } else {
            this.btnCancelRun.classList.add("hidden");
            this.btnCancelRun.disabled = true;
            this.commandInput.focus();
        }
    }

    truncateOutput(text, maxChars) {
        if (text.length <= maxChars) {
            return text;
        }
        return text.slice(0, maxChars) + "\n\n[truncated — output exceeds " + maxChars + " characters]";
    }

    handleNav(item) {
        this.navItems.forEach((nav) => nav.classList.remove("active"));
        item.classList.add("active");
        const target = item.dataset.nav;
        if (target === "workspace") {
            this.addLogEntry("Workspace focused", "output");
            return;
        }
        if (target === "figures") {
            this.loadPreview();
            this.addLogEntry("Figure preview focused", "output");
            return;
        }
        if (target === "data") {
            const tab = document.querySelector('.tab[data-tab="data"]');
            if (tab) this.switchTab(tab);
            this.addLogEntry("Data manifest focused", "output");
            return;
        }
        if (target === "skills") {
            this.addLogEntry(`Skills active: ${Array.from(this.selectedSkillIds).join(", ") || "none"}`, "output");
        }
    }

    showPlanned(message) {
        const text = message || "This control is planned but not implemented yet.";
        this.addLogEntry(text, "output");
        this.setStatus("ready", "Planned");
    }

    updateCapability(key, text, ok) {
        const node = {
            spec: this.capSpec,
            data: this.capData,
            preview: this.capPreview,
            qa: this.capQA,
            skills: this.capSkills,
            agentRuns: this.capAgentRuns,
        }[key];
        if (!node) return;
        node.textContent = text;
        node.className = ok ? "cap-ok" : "cap-warn";
        this.refreshCapabilitySummary();
    }

    refreshCapabilitySummary() {
        if (!this.buildStateSummary) return;
        const values = [this.capSpec, this.capData, this.capPreview, this.capQA, this.capSkills].filter(Boolean);
        const okCount = values.filter((node) => node.className === "cap-ok").length;
        this.buildStateSummary.textContent = `${okCount}/${values.length} project surfaces loaded`;
    }

    async refreshAfterAgentRun() {
        // Fetch full run record for fileChanges, skillIds, and verification
        if (this.activeRunId || this._lastCompletedRunId) {
            const runId = this.activeRunId || this._lastCompletedRunId;
            try {
                const res = await fetch(`${this.apiBase}/api/agent-runs/${runId}`);
                if (res.ok) {
                    const run = await res.json();
                    this.displayFileChanges(run);
                    this.displayUsedSkills(run);
                    this.displayVerificationStatus(run);
                }
            } catch (err) {
                console.error("Failed to fetch run record:", err);
            }
            this._lastCompletedRunId = null;
        }

        await Promise.all([
            this.fetchSpec(),
            this.fetchDataManifest(),
            this.fetchQAReport(),
        ]);
        this.loadPreview();
    }

    appendAgentMessage(text, role) {
        // Check if last message is same role — append to it for streaming effect
        const last = this.agentThread.lastElementChild;
        if (last && last.classList.contains(role) && role === "system") {
            last.textContent += "\n" + text;
            this.agentThread.scrollTop = this.agentThread.scrollHeight;
            return;
        }

        const msg = document.createElement("div");
        msg.className = `agent-message ${role}`;
        msg.textContent = text;
        this.agentThread.appendChild(msg);
        this.agentThread.scrollTop = this.agentThread.scrollHeight;
    }

    displayFileChanges(run) {
        const changes = run.fileChanges || [];
        const count = changes.length;

        // Run Log: count summary
        if (count > 0) {
            this.addLogEntry(`${count} file${count === 1 ? "" : "s"} changed`, "success");
        } else {
            this.addLogEntry("No project files changed", "output");
        }

        // Agent Console: detailed file list
        const container = document.createElement("div");
        container.className = "file-changes";

        const header = document.createElement("div");
        header.className = "file-changes-header";
        header.textContent = count > 0
            ? `Changed files (${count})`
            : "No project files changed";
        container.appendChild(header);

        if (count > 0) {
            const list = document.createElement("div");
            list.className = "file-changes-list";
            for (const change of changes) {
                const item = document.createElement("div");
                item.className = "file-change-item";

                const badge = document.createElement("span");
                badge.className = `file-badge file-badge-${change.status}`;
                badge.textContent = change.status;

                const path = document.createElement("span");
                path.className = "file-path";
                path.textContent = change.path;

                item.appendChild(badge);
                item.appendChild(path);
                list.appendChild(item);
            }
            container.appendChild(list);
        }

        this.agentThread.appendChild(container);
        this.agentThread.scrollTop = this.agentThread.scrollHeight;
    }

    displayUsedSkills(run) {
        const skillIds = run.skillIds || [];
        if (skillIds.length === 0) return;

        const container = document.createElement("div");
        container.className = "skills-used";

        const header = document.createElement("div");
        header.className = "skills-used-header";
        header.textContent = `Skills used (${skillIds.length}):`;
        container.appendChild(header);

        const list = document.createElement("div");
        list.className = "skills-used-list";
        for (const skillId of skillIds) {
            const skill = this.skills.find(s => s.id === skillId);
            const badge = document.createElement("span");
            badge.className = "skill-badge";
            badge.textContent = skill ? skill.title : skillId;
            badge.title = skill ? skill.description : "";
            list.appendChild(badge);
        }
        container.appendChild(list);

        this.agentThread.appendChild(container);
        this.agentThread.scrollTop = this.agentThread.scrollHeight;
    }

    displayVerificationStatus(run) {
        const verStatus = run.verificationStatus || "not_run";
        if (verStatus === "not_run") return;

        const container = document.createElement("div");
        container.className = "verification-status";

        const header = document.createElement("div");
        header.className = `verification-header verification-${verStatus}`;
        if (verStatus === "passed") {
            header.textContent = "Verification passed: validate/render/qa";
        } else if (verStatus === "failed") {
            header.textContent = "Verification failed";
        } else if (verStatus === "running") {
            header.textContent = "Verification running...";
        }
        container.appendChild(header);

        const steps = run.verificationSteps || [];
        if (steps.length > 0) {
            const stepsList = document.createElement("div");
            stepsList.className = "verification-steps";
            for (const step of steps) {
                const stepEl = document.createElement("div");
                stepEl.className = `verification-step ${step.success ? "step-pass" : "step-fail"}`;

                const icon = document.createElement("span");
                icon.className = "step-icon";
                icon.textContent = step.success ? "PASS" : "FAIL";

                const name = document.createElement("span");
                name.className = "step-name";
                name.textContent = step.name;

                stepEl.appendChild(icon);
                stepEl.appendChild(name);
                stepsList.appendChild(stepEl);

                // Show stderr summary for failed steps
                if (!step.success && step.stderr) {
                    const errSummary = document.createElement("div");
                    errSummary.className = "step-error";
                    errSummary.textContent = this.truncateOutput(step.stderr, 500);
                    stepsList.appendChild(errSummary);
                }
            }
            container.appendChild(stepsList);
        }

        this.agentThread.appendChild(container);
        this.agentThread.scrollTop = this.agentThread.scrollHeight;
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
