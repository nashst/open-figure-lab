class OpenFigureLabApp {
    constructor() {
        this.apiBase = '';
        this.isRunning = false;
        this.projectName = 'soc_proxy_fig2';
    }

    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadInitialData();
    }

    cacheElements() {
        this.btnValidate = document.getElementById('btnValidate');
        this.btnRender = document.getElementById('btnRender');
        this.btnQA = document.getElementById('btnQA');
        this.btnRefresh = document.getElementById('btnRefresh');
        this.btnClearLog = document.getElementById('btnClearLog');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.statusText = document.getElementById('statusText');
        this.previewImage = document.getElementById('previewImage');
        this.previewEmpty = document.getElementById('previewEmpty');
        this.previewInfo = document.getElementById('previewInfo');
        this.specContent = document.getElementById('specContent');
        this.dataContent = document.getElementById('dataContent');
        this.qaContent = document.getElementById('qaContent');
        this.runLog = document.getElementById('runLog');
        this.tabs = document.querySelectorAll('.tab');
    }

    bindEvents() {
        this.btnValidate.addEventListener('click', () => this.executeCommand('validate'));
        this.btnRender.addEventListener('click', () => this.executeCommand('render'));
        this.btnQA.addEventListener('click', () => this.executeCommand('qa'));
        this.btnRefresh.addEventListener('click', () => this.loadPreview());
        this.btnClearLog.addEventListener('click', () => this.clearLog());
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab));
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
            if (res.ok && data.content) {
                this.specContent.textContent = data.content;
            } else {
                this.specContent.textContent = `# ${data.error || 'No spec found'}`;
            }
        } catch (err) {
            this.specContent.textContent = `# Failed to load spec: ${err.message}`;
        }
    }

    async fetchDataManifest() {
        try {
            const res = await fetch(`${this.apiBase}/api/data-manifest`);
            const data = await res.json();
            if (res.ok && data.content) {
                this.dataContent.textContent = data.content;
            } else {
                this.dataContent.textContent = `# ${data.error || 'No data manifest found'}`;
            }
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
                this.qaContent.innerHTML = '<p class="qa-empty">No QA report. Run QA first.</p>';
            }
        } catch (err) {
            this.qaContent.innerHTML = `<p class="qa-empty">Failed to load: ${err.message}</p>`;
        }
    }

    renderQAReport(content) {
        const lines = content.split('\n');
        let html = '';
        for (const line of lines) {
            if (line.startsWith('# ')) {
                html += `<h3>${this.escapeHtml(line.slice(2))}</h3>`;
            } else if (line.startsWith('## ')) {
                html += `<h4>${this.escapeHtml(line.slice(3))}</h4>`;
            } else if (line.startsWith('- PASS:')) {
                html += `<div class="qa-pass">✓ ${this.escapeHtml(line.slice(7).trim())}</div>`;
            } else if (line.startsWith('- ERROR:')) {
                html += `<div class="qa-error">✗ ${this.escapeHtml(line.slice(8).trim())}</div>`;
            } else if (line.startsWith('- WARNING:')) {
                html += `<div class="qa-warning">⚠ ${this.escapeHtml(line.slice(10).trim())}</div>`;
            } else if (line.trim()) {
                html += `<div class="qa-line">${this.escapeHtml(line)}</div>`;
            }
        }
        this.qaContent.innerHTML = html;
    }

    loadPreview() {
        const imgUrl = `${this.apiBase}/outputs/${this.projectName}.png?t=${Date.now()}`;
        this.previewImage.onload = () => {
            this.previewImage.style.display = 'block';
            this.previewEmpty.style.display = 'none';
            this.previewInfo.textContent = `${this.projectName}.png`;
        };
        this.previewImage.onerror = () => {
            this.previewImage.style.display = 'none';
            this.previewEmpty.style.display = 'flex';
            this.previewInfo.textContent = 'No output';
        };
        this.previewImage.src = imgUrl;
    }

    async executeCommand(command) {
        if (this.isRunning) return;

        this.isRunning = true;
        this.setStatus('running', `Running ${command}...`);
        this.disableButtons(true);
        this.addLogEntry(`$ ofl ${command} examples/${this.projectName}`, 'command');

        try {
            const res = await fetch(`${this.apiBase}/api/${command}`, { method: 'POST' });
            const data = await res.json();

            if (data.success === true) {
                if (data.stdout) {
                    this.addLogEntry(data.stdout, 'success');
                } else {
                    this.addLogEntry(`${command} completed`, 'success');
                }
            } else {
                if (data.stderr) {
                    this.addLogEntry(data.stderr, 'error');
                }
                if (data.stdout) {
                    this.addLogEntry(data.stdout, 'output');
                }
            }

            await this.refreshAfterCommand(command);
        } catch (err) {
            this.addLogEntry(`Error: ${err.message}`, 'error');
        } finally {
            this.isRunning = false;
            this.setStatus('', 'Ready');
            this.disableButtons(false);
        }
    }

    async refreshAfterCommand(command) {
        if (command === 'render') {
            this.loadPreview();
        } else if (command === 'qa') {
            await this.fetchQAReport();
        }
    }

    setStatus(className, text) {
        this.statusIndicator.className = `status-dot ${className}`;
        this.statusText.textContent = text;
    }

    disableButtons(disabled) {
        this.btnValidate.disabled = disabled;
        this.btnRender.disabled = disabled;
        this.btnQA.disabled = disabled;
    }

    switchTab(selectedTab) {
        this.tabs.forEach(tab => tab.classList.remove('active'));
        selectedTab.classList.add('active');

        const tabName = selectedTab.dataset.tab;
        this.specContent.style.display = tabName === 'spec' ? 'block' : 'none';
        this.dataContent.style.display = tabName === 'data' ? 'block' : 'none';
        this.qaContent.style.display = tabName === 'qa' ? 'block' : 'none';
    }

    addLogEntry(message, type = 'output') {
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;

        const time = document.createElement('span');
        time.className = 'log-time';
        time.textContent = new Date().toLocaleTimeString();

        const msg = document.createElement('span');
        msg.className = 'log-msg';
        msg.textContent = message;

        entry.appendChild(time);
        entry.appendChild(msg);
        this.runLog.appendChild(entry);
        this.runLog.scrollTop = this.runLog.scrollHeight;
    }

    clearLog() {
        this.runLog.innerHTML = '';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const app = new OpenFigureLabApp();
    app.init();
});
