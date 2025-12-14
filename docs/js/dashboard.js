const REPO_OWNER = 'amullick-git';
const REPO_NAME = 'news_bot';
const CONFIG_PATH = 'config.yaml';
const API_BASE = 'https://api.github.com';

const state = {
    config: null,
    sha: null,
    pat: localStorage.getItem('gh_pat') || null
};

// UI Element Refs
const els = {
    app: document.getElementById('app'),
    authView: document.getElementById('auth-view'),
    dashView: document.getElementById('dashboard-view'),
    patInput: document.getElementById('pat-input'),
    loginBtn: document.getElementById('login-btn'),
    editor: document.getElementById('config-editor'),
    saveBtn: document.getElementById('save-btn'),
    logoutBtn: document.getElementById('logout-btn'),
    status: document.getElementById('status-indicator'),
    toastContainer: document.getElementById('toast-container'),
    demoBtn: document.getElementById('demo-btn')
};

// --- Mock Data ---
const MOCK_CONFIG = {
    "system": {
        "app_name": "NewsBot",
        "version": "1.0.0",
        "debug": true
    },
    "feeds": [
        { "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "limit": 5, "enabled": true },
        { "url": "https://feeds.npr.org/1001/rss.xml", "limit": 3, "enabled": true },
        { "url": "https://www.theverge.com/rss/index.xml", "limit": 5, "enabled": false }
    ],
    "audio": {
        "provider": "google",
        "voice": "en-US-Journey-F",
        "speed": 1.1,
        "pitch": 0
    },
    "content": {
        "max_segments": 10,
        "intro_template": "Hello, welcome to your briefing.",
        "outro_template": "That's all for today."
    },
    "schedule": {
        "timezone": "US/Pacific",
        "active_days": ["Mon", "Tue", "Wed", "Thu", "Fri"]
    }
};

function loadMockData() {
    showDashboard(false);
    els.status.textContent = 'Demo Mode (Read Only)';
    state.config = MOCK_CONFIG;
    renderConfig(state.config);
    showToast('Loaded Mock Data', 'info');

    // Disable Save in Demo Mode
    els.saveBtn.disabled = true;
    els.saveBtn.innerText = 'Save Disabled (Demo)';
}

if (els.demoBtn) els.demoBtn.addEventListener('click', loadMockData);

// --- Workflow Actions ---

// --- Workflow Actions ---

async function triggerWorkflow(workflowId, btn) {
    if (!state.pat) return showToast('Please login first', 'error');

    const originalText = 'Run'; // Reset to standard
    btn.disabled = true;
    btn.innerText = 'Starting...';

    // Clear previous status
    const badge = document.getElementById(`status-${workflowId}`);
    if (badge) badge.innerHTML = '';

    try {
        const timestamp = new Date().toISOString();

        // 1. Trigger Dispatch
        const response = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${workflowId}/dispatches`, {
            method: 'POST',
            headers: {
                'Authorization': `token ${state.pat}`,
                'Accept': 'application/vnd.github.v3+json'
            },
            body: JSON.stringify({ ref: 'main' })
        });

        if (!response.ok) throw new Error('Failed to trigger workflow');

        showToast('Workflow triggered!', 'success');

        // 2. Poll for Status & Persist
        // We don't have a run ID yet, so we persist the intent to poll
        const trackingData = {
            id: workflowId,
            start: timestamp,
            status: 'provisioning'
        };
        saveTracking(workflowId, trackingData);

        pollWorkflowStatus(workflowId, timestamp);
        btn.innerText = 'Run';

    } catch (error) {
        console.error(error);
        showToast(error.message, 'error');
        btn.innerText = 'Run';
        btn.disabled = false;
    }
}

async function pollWorkflowStatus(workflowId, startTime) {
    let attempts = 0;
    const maxAttempts = 30; // 60 seconds

    // Initial Badge State
    updateActionStatus(workflowId, { status: 'provisioning' });

    const interval = setInterval(async () => {
        attempts++;
        try {
            // Find runs created AFTER our trigger time
            const res = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/runs?workflow_id=${workflowId}&created=>${startTime}`, {
                headers: { 'Authorization': `token ${state.pat}` }
            });

            const data = await res.json();

            if (data.total_count > 0) {
                const run = data.workflow_runs[0]; // Newest run

                // Update UI based on status
                updateActionStatus(workflowId, run);

                // Update Persistence
                saveTracking(workflowId, {
                    id: workflowId,
                    start: startTime,
                    runId: run.id,
                    status: run.status
                });

                // If terminal state, stop polling
                const conclusion = run.conclusion;
                if (run.status === 'completed') {
                    clearInterval(interval);
                    clearTracking(workflowId);

                    if (conclusion === 'success') showToast('Workflow completed successfully!', 'success');
                    else showToast('Workflow failed.', 'error');
                }
            } else if (attempts >= maxAttempts) {
                // Timeout looking for run
                clearInterval(interval);
                clearTracking(workflowId);
                showToast('Timeout: Could not find new run.', 'error');
                updateActionStatus(workflowId, { status: 'timeout' });
            }

        } catch (e) {
            console.error("Polling error", e);
        }
    }, 2000);
}

function updateActionStatus(workflowId, run) {
    const badge = document.getElementById(`status-${workflowId}`);
    if (!badge) return;

    // Map Status to UI
    let status = run.status;
    let label = status;
    let icon = '';

    // Normalize status
    if (status === 'provisioning') {
        label = 'Starting...';
        status = 'queued'; // Reuse queued style
    } else if (status === 'timeout') {
        label = 'Timeout';
        status = 'failure';
    } else if (status === 'completed') {
        if (run.conclusion === 'success') {
            label = 'Success';
            status = 'completed';
        } else {
            label = 'Failed';
            status = 'failure';
        }
    } else if (status === 'in_progress') {
        label = 'Running';
    }

    // Render Badge
    badge.className = `status-badge ${status}`;
    badge.innerHTML = `
        <div class="status-dot"></div>
        <span>${label}</span>
        ${run.html_url ? `<a href="${run.html_url}" target="_blank" style="margin-left:5px; text-decoration:none; color:inherit;">↗</a>` : ''}
    `;

    // Enable/Disable Button based on run state
    // Actually, allowing concurrent runs might be okay, but let's disable for safety?
    // User requested "action can be triggered", so maybe keep enabled or re-enable quickly.
    // Let's re-enable the button immediately in triggerWorkflow so user can spam if they want, 
    // but the status badge tracks the latest.
    const btn = badge.nextElementSibling;
    if (btn) btn.disabled = (status === 'provisioning');
}

// --- Persistence Helpers ---
function saveTracking(id, data) {
    const tracked = JSON.parse(localStorage.getItem('tracked_workflows') || '{}');
    tracked[id] = data;
    localStorage.setItem('tracked_workflows', JSON.stringify(tracked));
}

function clearTracking(id) {
    const tracked = JSON.parse(localStorage.getItem('tracked_workflows') || '{}');
    delete tracked[id];
    localStorage.setItem('tracked_workflows', JSON.stringify(tracked));
}

function restoreTracking() {
    const tracked = JSON.parse(localStorage.getItem('tracked_workflows') || '{}');
    Object.values(tracked).forEach(item => {
        // Resume polling
        pollWorkflowStatus(item.id, item.start);
    });
}

// --- Initialization ---

async function init() {
    if (state.pat) {
        showDashboard();
        restoreTracking(); // Resume any active polls
    } else {
        showAuth();
    }
}

// --- Auth Handling ---

function showAuth() {
    els.authView.classList.add('active');
    els.authView.classList.remove('hidden');
    els.dashView.classList.add('hidden');
    els.dashView.classList.remove('active');
}

function showDashboard(shouldFetch = true) {
    els.authView.classList.add('hidden');
    els.authView.classList.remove('active');
    els.dashView.classList.add('active');
    els.dashView.classList.remove('hidden');
    if (shouldFetch) loadConfig();
}

els.loginBtn.addEventListener('click', async () => {
    const token = els.patInput.value.trim();
    if (!token) return showToast('Please enter a token', 'error');

    // Validate Token
    try {
        const res = await fetch(`${API_BASE}/user`, {
            headers: { Authorization: `Bearer ${token}` }
        });

        if (res.ok) {
            localStorage.setItem('gh_pat', token);
            state.pat = token;
            showToast('Authentication successful', 'success');
            showDashboard();
        } else {
            showToast('Invalid Token. Please check scopes.', 'error');
        }
    } catch (e) {
        showToast('Connection error', 'error');
    }
});

els.logoutBtn.addEventListener('click', () => {
    localStorage.removeItem('gh_pat');
    state.pat = null;
    location.reload();
});

// --- API Interactions ---

async function loadConfig() {
    els.status.textContent = 'Fetching config...';
    try {
        const url = `${API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${CONFIG_PATH}`;
        const res = await fetch(url, {
            headers: {
                Authorization: `Bearer ${state.pat}`,
                Accept: 'application/vnd.github.v3+json'
            }
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        state.sha = data.sha;

        // Decode Content (Base64 -> UTF8)
        const content = atob(data.content);
        state.config = jsyaml.load(content);

        renderConfig(state.config);
        els.status.textContent = 'Ready';

    } catch (e) {
        console.error(e);
        showToast(`Failed to load config: ${e.message}`, 'error');
        els.editor.innerHTML = `<div class="error">Error loading config. Check console.</div>`;
    }
}

async function saveConfig() {
    els.saveBtn.disabled = true;
    els.saveBtn.textContent = 'Saving...';

    try {
        // Harvest Data
        const newConfig = harvestConfig();
        const yamlStr = jsyaml.dump(newConfig);
        const contentEncoded = btoa(unescape(encodeURIComponent(yamlStr))); // Unicode safe b64

        const body = {
            message: "update config.yaml via Dashboard",
            content: contentEncoded,
            sha: state.sha
        };

        const url = `${API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${CONFIG_PATH}`;
        const res = await fetch(url, {
            method: 'PUT',
            headers: {
                Authorization: `Bearer ${state.pat}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });

        if (!res.ok) throw new Error(await res.text());

        const data = await res.json();
        state.sha = data.content.sha; // Update SHA for next save

        showToast('Configuration saved successfully!', 'success');

    } catch (e) {
        console.error(e);
        showToast('Failed to save changes.', 'error');
    } finally {
        els.saveBtn.disabled = false;
        els.saveBtn.textContent = 'Save Changes';
    }
}

els.saveBtn.addEventListener('click', saveConfig);

// --- Rendering Logic ---

function renderConfig(config) {
    els.editor.innerHTML = ''; // Clear loading

    const sections = Object.keys(config);
    const tabsContainer = document.createElement('div');
    tabsContainer.className = 'config-tabs';

    const contentContainer = document.createElement('div');
    contentContainer.className = 'config-content';

    let first = true;

    sections.forEach(key => {
        // 1. Create Tab Button
        const tabBtn = document.createElement('button');
        tabBtn.className = `tab-btn ${first ? 'active' : ''}`;
        tabBtn.textContent = key;
        tabBtn.onclick = () => switchTab(key);
        tabsContainer.appendChild(tabBtn);

        // 2. Create Section Content
        const sectionEl = document.createElement('div');
        sectionEl.className = `section-group ${first ? 'active' : ''}`;
        sectionEl.id = `tab-${key}`;
        // Remove individual titles inside tabs to save space, or keep them? 
        // Let's keep a small header or just rely on the tab. 
        // Actually, removing the inner title is cleaner if the tab says it.
        // But the original code used the title for harvesting. 
        // Let's keep the title but hide it visually or make it smaller, 
        // OR better: keep the structure but ensure harvestConfig finds it.
        sectionEl.innerHTML = `<div class="section-title hidden-title">${key}</div>`;

        const content = createField(key, config[key]);
        sectionEl.appendChild(content);
        contentContainer.appendChild(sectionEl);

        first = false;
    });

    els.editor.appendChild(tabsContainer);
    els.editor.appendChild(contentContainer);
}

function switchTab(key) {
    // Update Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent === key);
    });

    // Update Content
    document.querySelectorAll('.section-group').forEach(section => {
        section.classList.toggle('active', section.id === `tab-${key}`);
    });
}

/**
 * Recursive function to generate inputs based on data type
 */
function createField(path, value) {
    const container = document.createElement('div');
    container.className = 'field-group';
    container.dataset.type = Array.isArray(value) ? 'array' : typeof value;
    container.dataset.path = path;

    if (Array.isArray(value)) {
        // Handle Lists
        const listContainer = document.createElement('div');
        listContainer.className = 'array-container';

        value.forEach((item, index) => {
            const itemRow = document.createElement('div');
            itemRow.className = 'array-item';

            // Handle complex array items (objects inside arrays)
            let input;
            if (typeof item === 'object' && item !== null) {
                // Special case for 'feeds' with url/limit objects
                // For simplicity in this v1, simplify to JSON string or recursive block?
                // Recursive is better but more complex. 
                // Let's assume most array items are strings, if object use textarea/JSON

                input = document.createElement('textarea');
                input.value = JSON.stringify(item);
                input.dataset.isJson = 'true';
                input.rows = 2;
            } else {
                input = document.createElement('input');
                input.type = 'text';
                input.value = item;
            }

            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-btn';
            removeBtn.innerHTML = '&times;';
            removeBtn.onclick = () => itemRow.remove();

            itemRow.appendChild(input);
            itemRow.appendChild(removeBtn);
            listContainer.appendChild(itemRow);
        });

        const addBtn = document.createElement('button');
        addBtn.className = 'add-btn';
        addBtn.textContent = '+ Add Item';
        addBtn.onclick = () => {
            const row = document.createElement('div');
            row.className = 'array-item';
            row.innerHTML = `<input type="text"><button class="remove-btn" onclick="this.parentElement.remove()">×</button>`;
            listContainer.appendChild(row);
        };

        container.appendChild(listContainer);
        container.appendChild(addBtn);

    } else if (typeof value === 'object' && value !== null) {
        // Nested Object
        Object.keys(value).forEach(subKey => {
            const label = document.createElement('label');
            label.className = 'field-label';
            label.textContent = subKey;

            const subField = createField(`${path}.${subKey}`, value[subKey]);
            // Unwrap the field-group wrapper to avoid nested padding hell
            // actually keep it for structure

            container.appendChild(label);
            container.appendChild(subField);
        });

    } else {
        // Primitive (String, Number, Boolean)
        const input = document.createElement('input');

        if (typeof value === 'boolean') {
            input.type = 'checkbox';
            input.checked = value;
            input.style.width = 'auto';
        } else if (typeof value === 'number') {
            input.type = 'number';
            input.value = value;
        } else {
            input.type = 'text';
            input.value = value;
        }

        container.appendChild(input);
    }

    return container;
}

// --- Data Harvesting ---

function harvestConfig() {
    const sections = els.editor.querySelectorAll('.section-group');
    const newConfig = {};

    sections.forEach(section => {
        const title = section.querySelector('.section-title').textContent;
        // The first child after title is the field-group for the root key
        const rootGroup = section.querySelector('.field-group');
        newConfig[title] = harvestField(rootGroup);
    });

    return newConfig;
}

function harvestField(container) {
    const type = container.dataset.type;

    if (type === 'array') {
        const listContainer = container.querySelector('.array-container');
        const items = [];
        listContainer.querySelectorAll('.array-item input, .array-item textarea').forEach(input => {
            if (input.dataset.isJson) {
                try {
                    items.push(JSON.parse(input.value));
                } catch (e) { /* ignore invalid JSON */ }
            } else {
                if (input.value) items.push(input.value);
            }
        });
        return items;
    }

    // For Objects, we need to find all direct children labels + fields
    // This is tricky because the recursive structure is flattened in DOM
    // Let's rely on the DOM structure: label, div.field-group, label, div.field-group

    if (type === 'object') {
        const obj = {};
        const children = container.children;

        for (let i = 0; i < children.length; i++) {
            if (children[i].classList.contains('field-label')) {
                const key = children[i].textContent;
                const fieldGroup = children[i + 1]; // The next sib is the field group
                if (fieldGroup && fieldGroup.classList.contains('field-group')) {
                    obj[key] = harvestField(fieldGroup);
                }
            }
        }
        return obj;
    }

    // Primitives
    const input = container.querySelector('input');
    if (input.type === 'checkbox') return input.checked;
    if (input.type === 'number') return Number(input.value);
    return input.value;
}

// --- Utilities ---

function showToast(msg, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    els.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Start
init();
