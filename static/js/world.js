/* world.js — World data loading, editing, and mode conversion */

// Track which world has unsaved edits
const worldDirty = {};

function markWorldDirty(filename) {
    worldDirty[filename] = true;
    document.querySelectorAll('[id^="worldSaveBtn-"]').forEach(btn => {
        const card = btn.closest('.card');
        if (card && card.innerHTML.includes(filename)) {
            btn.style.display = '';
        }
    });
}

/**
 * Send a single world update action. Marks dirty on success.
 * Returns true on success, false on failure.
 */
async function postWorldUpdate(filename, update) {
    const data = await apiPost(`/api/world/${filename}/update`, [update]);
    if (!data) return false;
    if (data.results && data.results[0] && data.results[0].ok) {
        markWorldDirty(filename);
        return true;
    }
    showToast('Update failed: ' + (data.results?.[0]?.error || 'unknown'), true);
    return false;
}

// ----- World data loading & rendering -----

async function loadWorldDetails(filename, btn) {
    btn.textContent = 'Loading...';
    btn.disabled = true;

    try {
        const data = await apiGet(`/api/world/${filename}`);
        if (!data) { btn.disabled = false; return; }
        const container = btn.closest('.card').querySelector('[id^="world-details-"]');

        let html = '';
        html += renderDifficultySection(filename, data);
        html += renderWeatherSection(filename, data);
        html += renderEventsSection(filename, data);
        html += renderContainersSection(filename, data);
        html += renderStationsSection(data);

        container.innerHTML = html || '<p style="color:var(--text-dim)">No editable world data found.</p>';
        btn.textContent = 'Refresh Data';
    } catch (e) {
        showToast('Failed to load world: ' + e.message, true);
    }
    btn.disabled = false;
}

function renderDifficultySection(filename, data) {
    if (!data.difficulty || !data.difficulty.current) return '';
    const fname = escapeHtml(filename);
    const cur = data.difficulty.current;
    const missing = data.difficulty.missing || [];
    let html = `<div class="card-title card-title-flush">
        Custom Difficulty Settings (${cur.length} active / ${data.difficulty.total_known} total)
    </div>`;
    html += `<p class="text-sm text-dim section-desc">
        Edit existing settings below (length-preserving, safe). Adding new settings to a world that
        doesn't have them requires Phase 2 binary injection — not yet implemented.
    </p>`;

    if (cur.length === 0) {
        html += '<p class="text-sm" style="color:var(--accent-red)">No active settings in this save.</p>';
    } else {
        html += '<div class="grid grid-2">';
        for (const s of cur) {
            const tag = escapeHtml(s.tag);
            const name = escapeHtml(s.name);
            const hint = escapeHtml(s.hint);
            html += `<div class="event-row">
                <div class="event-name">${name}</div>
                <div class="text-xs text-dim font-mono" style="margin-bottom:6px">${tag}</div>
                <div class="trigger-row" style="align-items:center">
                    <span class="text-sm">${hint}</span>
                    <input type="number" value="${s.value}" step="0.1" min="0" max="100"
                        class="input-sm"
                        onchange="updateDifficulty('${fname}', '${tag}', parseFloat(this.value))">
                </div>
            </div>`;
        }
        html += '</div>';
    }

    if (missing.length > 0) {
        html += `<details class="missing-tags-panel">
            <summary class="text-sm text-dim">
                Show ${missing.length} unset tags (Phase 2 will allow injection)
            </summary>
            <div class="missing-tags-grid">`;
        for (const m of missing) {
            html += `<div class="text-xs text-dim font-mono" style="padding:4px">${escapeHtml(m.name)}: ${escapeHtml(m.tag)}</div>`;
        }
        html += '</div></details>';
    }

    html += '<hr class="section-divider">';
    return html;
}

function renderWeatherSection(filename, data) {
    if (!data.weather || data.weather.length === 0) return '';
    let html = '<div class="card-title card-title-flush">Weather (' + data.weather.length + ' regions)</div>';
    html += '<div class="grid grid-2">';
    for (const w of data.weather) {
        const fname = escapeHtml(filename);
        const wname = escapeHtml(w.name);
        const currentType = (w.type || '').replace('EWeatherType::', '');
        html += `<div class="event-row">
            <div class="event-name">${wname}</div>
            <div class="trigger-row">
                <span>Type</span>
                <select onchange="updateWeather('${fname}', '${wname}', this.value, null)" class="input-md">
                    ${['Sunny','Cloudy','Rain','Storm','Snow','Fog','Hail','Wind'].map(t =>
                        `<option value="${t}" ${t===currentType?'selected':''}>${t}</option>`
                    ).join('')}
                </select>
            </div>
            <div class="trigger-row">
                <span>Day Count</span>
                <span>${w.day_count}</span>
            </div>
            <div class="trigger-row">
                <span>Time Remaining</span>
                <input type="number" value="${w.remaining_time.toFixed(0)}" min="0"
                       class="input-sm"
                       onchange="updateWeather('${fname}', '${wname}', null, parseFloat(this.value))">
            </div>
        </div>`;
    }
    html += '</div>';
    return html;
}

function renderEventsSection(filename, data) {
    if (!data.events || data.events.length === 0) return '';
    let html = '<div class="card-title" style="margin-top:16px">World Events (' + data.events.length + ')</div>';
    const fname = escapeHtml(filename);
    html += `<div style="margin-bottom:8px">
        <button class="btn btn-danger" onclick="disableAllRaids('${fname}')">Disable All Raids/Ambushes</button>
    </div>`;
    for (const ev of data.events) {
        const evname = escapeHtml(ev.name);
        html += `<div class="event-row">
            <div class="event-name">${evname}</div>`;
        for (const t of ev.triggers) {
            const cls = t.active ? 'trigger-active' : 'trigger-inactive';
            const tname = escapeHtml(t.name);
            html += `<div class="trigger-row" style="align-items:center">
                <span>${tname}</span>
                <div style="display:flex;gap:6px;align-items:center">
                    <span class="${cls} text-xs">${t.time}</span>
                    <button class="btn btn-mini"
                        onclick="toggleEventTrigger('${fname}', '${evname}', '${tname}', ${!t.active})">
                        ${t.active ? 'Disable' : 'Enable'}
                    </button>
                </div>
            </div>`;
        }
        html += '</div>';
    }
    return html;
}

function renderContainersSection(filename, data) {
    if (!data.containers || data.containers.length === 0) return '';
    const fname = escapeHtml(filename);
    let html = `<div class="card-title">World Storage (${data.containers.length} containers with items)</div>`;
    html += `<p class="text-sm text-dim section-desc">
        These are crafting station I/O, chests, and storage containers in the world.
        Edit Count for stackable items, Durability for gear.
    </p>`;
    html += '<div class="containers-scroll">';
    data.containers.forEach((c, idx) => {
        html += `<div class="event-row">
            <div class="event-name container-header">
                <span>Container ${idx + 1}</span>
                <span class="text-xs text-dim font-mono">${c.offset} &middot; ${c.item_count} items</span>
            </div>`;
        for (const item of c.items) {
            const itemId = escapeHtml(item.item_data || '?');
            if (item.is_stackable) {
                html += `<div class="trigger-row" style="align-items:center">
                    <span class="text-xs font-mono">[${item.slot}] ${itemId}</span>
                    <div style="display:flex;gap:6px;align-items:center">
                        <span class="text-xs text-cyan">x</span>
                        <input type="number" value="${item.count}" min="0" max="99999"
                            class="input-narrow"
                            onchange="updateContainerItem('${fname}', ${c.section_index}, ${item.slot}, 'Count', parseInt(this.value))">
                    </div>
                </div>`;
            } else if (item.durability !== null) {
                html += `<div class="trigger-row" style="align-items:center">
                    <span class="text-xs font-mono">[${item.slot}] ${itemId}</span>
                    <div style="display:flex;gap:6px;align-items:center">
                        <span class="text-xs text-gold">dur</span>
                        <input type="number" value="${item.durability}" min="0" max="99999"
                            class="input-narrow"
                            onchange="updateContainerItem('${fname}', ${c.section_index}, ${item.slot}, 'Durability', parseInt(this.value))">
                    </div>
                </div>`;
            } else {
                html += `<div class="trigger-row">
                    <span class="text-xs font-mono">[${item.slot}] ${itemId}</span>
                    <span class="text-xs text-dim">no editable fields</span>
                </div>`;
            }
        }
        html += '</div>';
    });
    html += '</div>';
    return html;
}

function renderStationsSection(data) {
    if (!data.stations || data.stations.length === 0) return '';
    let html = '<div class="card-title">Crafting Stations (' + data.stations.length + ')</div>';
    for (const s of data.stations) {
        html += `<div class="stat-row" style="margin-bottom:4px">
            <span class="stat-label text-xs font-mono">${s.offset}</span>
            <span class="text-sm">Fuel: ${s.fuel_time.toFixed(1)}s | Recipe: ${s.recipe_time.toFixed(1)}s${s.running ? ' | <strong class="text-success">RUNNING</strong>' : ''}</span>
        </div>`;
    }
    return html;
}

// ----- World edit actions -----

function updateContainerItem(filename, sectionIndex, slot, field, value) {
    postWorldUpdate(filename, {
        action: 'container_item',
        section_index: sectionIndex,
        slot: slot,
        field: field,
        value: value
    });
}

function updateDifficulty(filename, tag, value) {
    postWorldUpdate(filename, { action: 'difficulty_value', tag: tag, value: value });
}

function updateWeather(filename, weatherName, type, remainingTime) {
    const update = { action: 'weather', weather_name: weatherName };
    if (type !== null) update.type = type;
    if (remainingTime !== null) update.remaining_time = remainingTime;
    postWorldUpdate(filename, update);
}

function toggleEventTrigger(filename, eventName, triggerName, active) {
    postWorldUpdate(filename, {
        action: 'event_trigger',
        event_name: eventName,
        trigger_name: triggerName,
        active: active
    }).then(ok => {
        if (ok) {
            const btn = document.querySelector(`[onclick*="loadWorldDetails('${filename}'"]`);
            if (btn) loadWorldDetails(filename, btn);
        }
    });
}

function disableAllRaids(filename) {
    if (!confirm('Disable all raid/ambush events? This will set their cooldowns to 999 days.')) return;
    postWorldUpdate(filename, { action: 'disable_all_raids' }).then(ok => {
        if (ok) {
            showToast('All raids/ambushes disabled');
            const btn = document.querySelector(`[onclick*="loadWorldDetails('${filename}'"]`);
            if (btn) loadWorldDetails(filename, btn);
        }
    });
}

async function convertWorldMode(filename, targetMode, idx) {
    const action = targetMode === 'custom' ? 'convert_to_custom' : 'revert_to_standard';
    const confirmMsg = targetMode === 'custom'
        ? `Convert "${filename}" to a Custom World?\n\n` +
          `⚠️ KNOWN BUG — DO THIS FIRST IN-GAME BEFORE CONVERTING:\n` +
          `  • Unlock and empty any LOCKED CHESTS you care about\n` +
          `  • Pick up / remove any PROTECTION TOTEMS you've placed\n` +
          `  • Note your PRIVACY SETTINGS (you may need to reset them)\n\n` +
          `Conversion appears to break the world ↔ character ownership binding,\n` +
          `so locked chests and protection totems may become unusable afterward\n` +
          `(reported by community testers — fix is on the bug list).\n\n` +
          `What this does:\n` +
          `  • Flips two bytes (L_World+9 + PROP CustomDifficultySettings byte)\n` +
          `  • Game treats world as Custom — exposes all difficulty categories\n` +
          `  • Required to use custom difficulty settings\n\n` +
          `After conversion:\n` +
          `  1. Click Save World\n` +
          `  2. Set your character's char_type to 3 (Character Editor)\n` +
          `  3. Launch the game and join with that character\n\n` +
          `Auto-backup will be created. Proceed?`
        : `Revert "${filename}" to Standard World?\n\nThis flips both bytes back to 0. Custom difficulty settings will no longer apply.\n\nProceed?`;
    if (!confirm(confirmMsg)) return;

    const data = await apiPost(`/api/world/${filename}/update`, [{action: action}]);
    if (!data) return;
    if (data.results && data.results[0] && data.results[0].ok) {
        markWorldDirty(filename);
        showToast(`World mode changed to: ${data.results[0].new_mode}. Click Save World to write to disk.`);
        setTimeout(() => location.reload(), 1500);
    } else {
        showToast('Conversion failed: ' + JSON.stringify(data.results), true);
    }
}

async function saveWorld(filename, idx) {
    if (!confirm(`Save world '${filename}'?\n\nMake sure the game is CLOSED first.`)) return;

    const data = await apiPost(`/api/world/${filename}/save`);
    if (!data) return;
    if (data.ok) {
        worldDirty[filename] = false;
        document.getElementById('worldSaveBtn-' + idx).style.display = 'none';
        if (data.warnings && data.warnings.length > 0) {
            showToast(`Saved with ${data.warnings.length} warnings (some sections too large to fit)`, true);
            console.warn('World save warnings:', data.warnings);
        } else {
            showToast('World saved successfully!');
        }
    } else {
        showToast('Save failed: ' + data.error, true);
    }
}
