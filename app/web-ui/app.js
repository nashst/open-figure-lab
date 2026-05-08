class OpenFigureLabApp {
    constructor() {
        this.apiBase = '';
        this.isRunning = false;
    }

    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadInitialData();
        this.tryLoadPreview();
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
        this.btnRefresh.addEventListener('click', () => this.refreshPreview());
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
    }

    async fetchSpec() {
        try {
            const res = await fetch(`${this.apiBase}/api/spec`);
            const data = await res.json();
            if (res.ok) {
                this.specContent.textContent = JSON.stringify(data.content, null, 2);
            } else {
                this.specContent.textContent = `# ${data.error}`;
            }
        } catch (err) {
            this.specContent.textContent = `# Failed to load spec: ${err.message}`;
        }
    }

    async fetchDataManifest() {
        try {
            const res = await fetch(`${this.apiBase}/api/data-manifest`);
            const data = await res.json();
            if (res.ok) {
                this.dataContent.textContent = JSON.stringify(data.content, null, 2);
            } else {
                this.dataContent.textContent = `# ${data.error}`;
            }
        } catch (err) {
            this.dataContent.textContent = `# Failed to load data manifest: ${err.message}`;
        }
    }

    async fetchQAReport() {
        try {
            const res = await fetch(`${this.apiBase}/api/qa-report`);
            const data = await res.json();
            if (res.ok) {
                this.qaContent.textContent = data.content;
            } else {
                this.qaContent.textContent = data.error;
            }
        } catch (err) {
            this.qaContent.textContent = `Failed to load QA report: ${err.message}`;
        }
    }

    tryLoadPreview() {
        const img = new Image();
        img.onload = () => {
            this.previewImage.src = img.src;
            this.previewImage.style.display = 'block';
            this.previewEmpty.style.display = 'none';
        };
        img.onerror = () => {
            this.previewImage.style.display = 'none';
            this.previewEmpty.style.display = 'block';
        };
        img.src = `${this.apiBase}/outputs/figure.png?t=${Date.now()}`;
    }

    refreshPreview() {
        this.previewImage.src = `${this.apiBase}/outputs/figure.png?t=${Date.now()}`;
        this.previewImage.style.display = 'block';
        this.previewEmpty.style.display = 'none';
        this.previewImage.onerror = () => {
            this.previewImage.style.display = 'none';
            this.previewEmpty.style.display = 'block';
        };
    }

    async executeCommand(command) {
        if (this.isRunning) return;

        this.isRunning = true;
        this.setStatus('running', `Running ${command}...`);
        this.disableButtons(true);
        this.addLogEntry(`Executing: ofl ${command}`, 'command');

        try {
            const res = await fetch(`${this.apiBase}/api/${command}`, { method: 'POST' });
            const data = await res.json();

            if (data.success) {
                this.addLogEntry(data.stdout || `${command} completed successfully`, 'success');
            } else {
                this.addLogEntry(data.stderr || data.stdout || `${command} failed`, 'error');
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
        if (command === 'validate') {
            await this.fetchSpec();
        } else if (command === 'render') {
            this.refreshPreview();
        } else if (command === 'qa') {
            await this.fetchQAReport();
        }
        await this.fetchDataManifest();
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
}

document.addEventListener('DOMContentLoaded', () => {
    const app = new OpenFigureLabApp();
    app.init();
});
