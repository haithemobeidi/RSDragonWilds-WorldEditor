/* character.js — Character editing queue functions */

/** Helper: push an action onto the queue and flush. */
function queueAction(action) {
    pendingUpdates.push(action);
    applyUpdates();
}

// ----- Vitals & stats -----
function queueUpdate(action, value) {
    queueAction({ action: action, value: parseFloat(value) });
}

function queueStatUpdate(stat, value) {
    queueAction({ action: 'stat', stat: stat, value: parseFloat(value) });
}

function queueHardcoreUpdate(value) {
    queueAction({ action: 'hardcore', enabled: value === 'true' });
}

function queueCharTypeUpdate(value) {
    pendingUpdates.push({ action: 'char_type', value: parseInt(value) });
    markDirty();
}

function queuePosition() {
    const x = parseFloat(document.getElementById('pos-x').value);
    const y = parseFloat(document.getElementById('pos-y').value);
    const z = parseFloat(document.getElementById('pos-z').value);
    queueAction({ action: 'position', x: x, y: y, z: z });
}

// ----- Skills -----
function queueSkillUpdate(skillId, xp, inputEl) {
    xp = parseInt(xp);
    pendingUpdates.push({ action: 'skill_xp', skill_id: skillId, xp: xp });

    // Update UI in place
    const row = inputEl.closest('.skill-row');
    const level = xpToLevel(xp);
    row.querySelector('[data-field="level"]').textContent = level;

    const nextXp = level + 1 < XP_TABLE.length ? XP_TABLE[level + 1] : XP_TABLE[XP_TABLE.length - 1];
    const currXp = level < XP_TABLE.length ? XP_TABLE[level] : 0;
    const pct = Math.min(100, ((xp - currXp) / Math.max(1, nextXp - currXp)) * 100);
    row.querySelector('[data-field="bar"]').style.width = pct + '%';
    row.querySelector('[data-field="bar-text"]').textContent = xp + ' / ' + (level + 1 < XP_TABLE.length ? nextXp : 'MAX');

    applyUpdates();
}

function maxSkill(skillId, btnEl) {
    const row = btnEl.closest('.skill-row');
    const maxXp = XP_TABLE[XP_TABLE.length - 1];
    row.querySelector('[data-field="xp"]').value = maxXp;
    queueSkillUpdate(skillId, maxXp, row.querySelector('[data-field="xp"]'));
}

// ----- Quests -----
function queueQuestUpdate(questId, state) {
    queueAction({ action: 'quest_state', quest_id: questId, state: parseInt(state) });
}

function queueQuestBool(questId, varName, value) {
    queueAction({ action: 'quest_bool', quest_id: questId, var_name: varName, value: value === 'true' });
}

function queueQuestInt(questId, varName, value) {
    queueAction({ action: 'quest_int', quest_id: questId, var_name: varName, value: parseInt(value) });
}

function completeAllQuests() {
    if (!confirm('Set all quests to Completed?')) return;
    document.querySelectorAll('#questsList .quest-row').forEach(row => {
        const questId = row.dataset.questId;
        if (questId) {
            pendingUpdates.push({ action: 'quest_state', quest_id: questId, state: 2 });
            const select = row.querySelector('select');
            if (select) select.value = '2';
            const badge = row.querySelector('.badge');
            if (badge) {
                badge.className = 'badge badge-completed';
                badge.textContent = 'Completed';
            }
        }
    });
    applyUpdates();
    showToast('All quests set to completed');
}

// ----- Inventory -----
function queueDurabilityUpdate(slot, durability, source) {
    queueAction({ action: 'item_durability', slot: slot, durability: parseInt(durability), source: source });
}

function queueCountUpdate(slot, count) {
    queueAction({ action: 'item_count', slot: slot, count: parseInt(count) });
}

function deleteItem(slot, btnEl) {
    if (!confirm('Delete this item from inventory?')) return;
    pendingUpdates.push({ action: 'delete_item', slot: slot });
    btnEl.closest('.inv-slot').remove();
    applyUpdates();
}

function repairAllItems() {
    document.querySelectorAll('#inventoryGrid input[type="number"]').forEach(input => {
        input.value = 9999;
        const slot = input.closest('.inv-slot').dataset.slot;
        pendingUpdates.push({ action: 'item_durability', slot: parseInt(slot), durability: 9999, source: 'Inventory' });
    });
    applyUpdates();
    showToast('All items set to max durability');
}

function maxAllStacks() {
    document.querySelectorAll('#inventoryGrid .inv-slot').forEach(slot => {
        const isStack = slot.querySelector('[style*="rs-cyan"]');
        if (isStack) {
            const input = slot.querySelector('input[type="number"]');
            if (input) {
                input.value = 999;
                const slotNum = parseInt(slot.dataset.slot);
                pendingUpdates.push({ action: 'item_count', slot: slotNum, count: 999 });
            }
        }
    });
    applyUpdates();
    showToast('All stacks maxed to 999');
}

// ----- Status effects -----
function clearEffect(effectName, btn) {
    pendingUpdates.push({ action: 'clear_status_effect', effect: effectName });
    btn.parentElement.parentElement.querySelector('.stat-label').firstElementChild.style.color = 'var(--text-dim)';
    btn.parentElement.parentElement.querySelector('.stat-label').firstElementChild.textContent = '○';
    btn.remove();
    applyUpdates();
}

function clearAllDebuffs() {
    pendingUpdates.push({ action: 'clear_all_status_effects' });
    document.querySelectorAll('#tab-overview .stat-row').forEach(row => {
        const btn = row.querySelector('.btn-danger');
        if (btn && btn.textContent === 'Clear') {
            const dot = row.querySelector('.stat-label').firstElementChild;
            if (dot) { dot.style.color = 'var(--text-dim)'; dot.textContent = '○'; }
            btn.remove();
        }
    });
    applyUpdates();
    showToast('All debuffs cleared');
}

function fullRestore() {
    pendingUpdates.push({ action: 'full_restore' });
    document.getElementById('stat-health').value = 100;
    document.getElementById('stat-stamina').value = 100;
    document.getElementById('stat-sustenance').value = 100;
    document.getElementById('stat-hydration').value = 100;
    document.getElementById('stat-toxicity').value = 0;
    document.getElementById('stat-endurance').value = 100;
    applyUpdates();
    showToast('Full restore: vitals refilled, debuffs cleared');
}

// ----- Spells -----
function queueSpellSlot(slot, spellId) {
    queueAction({ action: 'spell_slot', slot: slot, spell_id: spellId });
}

function fillAllSpells() {
    const spellId = document.getElementById('fillAllSpellSelect').value;
    if (!spellId) return;
    pendingUpdates.push({ action: 'fill_all_spell_slots', spell_id: spellId });
    document.querySelectorAll('#tab-spells select').forEach(sel => {
        if (sel.id !== 'fillAllSpellSelect') {
            sel.value = spellId;
        }
    });
    applyUpdates();
    showToast('All 48 spell slots filled');
}

function clearAllSpells() {
    if (!confirm('Clear all 48 spell slots?')) return;
    let slotIdx = 0;
    document.querySelectorAll('#tab-spells .stat-row select').forEach(sel => {
        pendingUpdates.push({ action: 'spell_slot', slot: slotIdx++, spell_id: '' });
        sel.value = '';
    });
    applyUpdates();
    showToast('All spell slots cleared');
}

// ----- Mounts -----
function addMount() {
    const id = document.getElementById('newMountId').value.trim();
    if (!id) return;
    pendingUpdates.push({ action: 'add_mount', mount_id: id });
    applyUpdates();
    showToast('Mount added — save and reload to see it');
    document.getElementById('newMountId').value = '';
}

function removeMount(id, btn) {
    if (!confirm('Remove this mount?')) return;
    pendingUpdates.push({ action: 'remove_mount', mount_id: id });
    btn.closest('.stat-row').remove();
    applyUpdates();
}

function equipMount(id) {
    pendingUpdates.push({ action: 'equip_mount', mount_id: id });
    applyUpdates();
    showToast('Equipped: ' + id);
}

// ----- Map / fog -----
function revealMap() {
    pendingUpdates.push({ action: 'reveal_map' });
    applyUpdates();
    showToast('Full map revealed');
}

function hideMap() {
    if (!confirm('Hide the entire map?')) return;
    pendingUpdates.push({ action: 'hide_map' });
    applyUpdates();
    showToast('Map hidden');
}
