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
    toastContainer: document.getElementById('toast-container')
};

// --- Workflow Actions ---

async function triggerWorkflow(workflowId, btn) {
    if (!state.pat) return showToast('Please login first', 'error');

    const originalText = btn.innerText;
    btn.innerText = 'Starting...';
    btn.disabled = true;

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

        showToast('Workflow triggered! Watching for run...', 'success');
        btn.innerText = 'Thinking...'; // Status: Queued/Provisioning

        // 2. Poll for Status
        pollWorkflowStatus(workflowId, timestamp, btn, originalText);

    } catch (error) {
        console.error(error);
        showToast(error.message, 'error');
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

async function pollWorkflowStatus(workflowId, startTime, btn, originalText) {
    const parent = btn.parentElement.parentElement; // .action-item
    let attempts = 0;
    const maxAttempts = 20; // 40 seconds (2s interval)

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
                updateActionStatus(btn, run);

                // If terminal state, stop polling
                if (run.status === 'completed') {
                    clearInterval(interval);
                    btn.innerText = originalText;
                    btn.disabled = false;
                }
            } else if (attempts >= maxAttempts) {
                // Timeout looking for run
                clearInterval(interval);
                btn.innerText = originalText;
                btn.disabled = false;
                showToast('Workflow started, but could not find run info.', 'info');
            }

        } catch (e) {
            console.error("Polling error", e);
        }
    }, 2000);
}

function updateActionStatus(btn, run) {
    // Replace button text or add badge
    const statusMap = {
        'queued': { icon: '⏳', label: 'Queued', class: 'queued' },
        'in_progress': { icon: '🟡', label: 'Running', class: 'in_progress' },
        'completed': { icon: '🟢', label: 'Done', class: 'completed' },
        'failure': { icon: '🔴', label: 'Failed', class: 'failure' }
    };

    // Check if we effectively finished (completed or failure)
    let state = run.status;
    if (state === 'completed' && run.conclusion === 'failure') state = 'failure';

    const ui = statusMap[state] || { icon: '❓', label: state, class: '' };

    // Update button text to reflect current state
    if (state !== 'completed' && state !== 'failure') {
        btn.innerText = `${ui.icon} ${ui.label}`;
    }

    // Add/Update URL link
    let link = btn.nextElementSibling;
    if (!link || !link.classList.contains('run-link')) {
        link = document.createElement('a');
        link.className = 'run-link';
        link.target = '_blank';
        link.style.marginLeft = '10px';
        link.style.fontSize = '0.8rem';
        link.style.color = '#3b82f6';
        btn.after(link);
    }
    link.href = run.html_url;
    link.innerText = 'View Logs';

    // Cleanup link if done
    if (state === 'failure' || (state === 'completed' && run.conclusion === 'success')) {
        showToast(`Workflow ${run.conclusion || 'finished'}!`, state === 'failure' ? 'error' : 'success');
    }
}

// --- Initialization ---

async function init() {
    if (state.pat) {
        showDashboard();
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

function showDashboard() {
    els.authView.classList.add('hidden');
    els.authView.classList.remove('active');
    els.dashView.classList.add('active');
    els.dashView.classList.remove('hidden');
    loadConfig();
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

    // Define sections explicitly to control order, or iterate keys
    const sections = Object.keys(config);

    sections.forEach(key => {
        const sectionEl = document.createElement('div');
        sectionEl.className = 'section-group';
        sectionEl.innerHTML = `<div class="section-title">${key}</div>`;

        const content = createField(key, config[key]); // Root level keys
        sectionEl.appendChild(content);
        els.editor.appendChild(sectionEl);
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
