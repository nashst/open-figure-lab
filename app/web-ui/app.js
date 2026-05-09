class OpenFigureLabApp {
    constructor() {
        this.apiBase = "";
        this.isRunning = false;
        this.projectName = "soc_proxy_fig2";
    }

    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadInitialData();
        this.addLogEntry("Workbench initialized", "output");
    }

    cacheElements() {
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
        this.btnValidate.addEventListener("click", () => this.executeCommand("validate"));
        this.btnRender.addEventListener("click", () => this.executeCommand("render"));
        this.btnQA.addEventListener("click", () => this.executeCommand("qa"));
        this.btnRefresh.addEventListener("click", () => this.loadPreview());
        this.btnClearLog.addEventListener("click", () => this.clearLog());
        this.tabs.forEach((tab) => {
            tab.addEventListener("click", () => this.switchTab(tab));
        });
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
