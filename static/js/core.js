/* core.js — Global state, UI primitives, character save/reload */

// Globals (set by index.html inline before this loads)
//   currentFile : string  — selected character filename
//   XP_TABLE    : array   — RS XP curve
let pendingUpdates = [];
let isDirty = false;

function switchTab(tabId, el) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('tab-' + tabId).classList.add('active');
}

function selectCharacter(filename) {
    window.location.href = '/?char=' + encodeURIComponent(filename);
}

function markDirty() {
    isDirty = true;
    document.getElementById('saveBtn').style.display = '';
    document.getElementById('dirtyBadge').classList.add('show');
}

function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.className = 'toast show' + (isError ? ' error' : '');
    setTimeout(() => { toast.className = 'toast'; }, 3000);
}

function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function xpToLevel(xp) {
    for (let i = XP_TABLE.length - 1; i >= 0; i--) {
        if (xp >= XP_TABLE[i]) return i;
    }
    return 1;
}

/**
 * Flush pendingUpdates to the character update endpoint.
 * Marks dirty on success. Used by all queue* functions.
 */
async function applyUpdates() {
    if (pendingUpdates.length === 0) return;

    const updates = [...pendingUpdates];
    pendingUpdates = [];

    const data = await apiPost(`/api/character/${currentFile}/update`, updates);
    if (!data) return;

    const failed = (data.results || []).filter(r => !r.ok);
    if (failed.length > 0) {
        showToast(`${failed.length} update(s) failed`, true);
    }
    markDirty();
}

async function saveChanges() {
    const data = await apiPost(`/api/character/${currentFile}/save`);
    if (!data) return;
    if (data.ok) {
        isDirty = false;
        document.getElementById('dirtyBadge').classList.remove('show');
        showToast('Saved successfully! Backup created.');
    } else {
        showToast('Save failed: ' + data.error, true);
    }
}

async function reloadSaves() {
    const data = await apiPost('/api/reload');
    if (!data) return;
    showToast(`Reloaded: ${data.characters} characters, ${data.worlds} worlds`);
    setTimeout(() => window.location.reload(), 1000);
}
