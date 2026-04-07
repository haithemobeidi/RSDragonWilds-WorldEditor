/* database.js — Reference catalog (quests + items) tab logic */

const DB_STATE = {
    catalog: null,
    activeView: 'items',  // 'items' or 'quests'
};

async function loadDatabase() {
    if (DB_STATE.catalog) return DB_STATE.catalog;
    const data = await apiGet('/api/catalog');
    if (!data) return null;
    DB_STATE.catalog = data;
    return data;
}

async function initDatabaseTab() {
    const data = await loadDatabase();
    if (!data) return;
    renderDatabase();
}

function setDbView(view) {
    DB_STATE.activeView = view;
    document.querySelectorAll('.db-view-btn').forEach(b => {
        b.classList.toggle('btn-primary', b.dataset.view === view);
    });
    renderDatabase();
}

function renderDatabase() {
    const data = DB_STATE.catalog;
    if (!data) return;
    const container = document.getElementById('db-grid');
    if (!container) return;

    const items = DB_STATE.activeView === 'items' ? data.items : data.quests;
    const html = (DB_STATE.activeView === 'items' ? items.map(renderItemCard) : items.map(renderQuestCard)).join('');
    container.innerHTML = html;
    document.getElementById('db-counter').textContent = `${items.length} entries`;
    applyDbFilter();
}

function renderItemCard(item) {
    const id = escapeHtml(item.id || '');
    const name = escapeHtml(item.display_name || item.item_name || '?');
    const vestige = item.vestige_name ? `<div class="db-card-meta"><strong>Vestige:</strong> ${escapeHtml(item.vestige_name)}</div>` : '';
    const type = item.type || '';
    const subtype = item.sub_type || '';
    const region = item.region || '';
    const subregion = item.sub_region || '';
    const source = item.source_type || '';
    const sourceName = item.source_name || '';
    const cost = item.soul_fragments_cost ? ` · <strong>${item.soul_fragments_cost} fragments</strong>` : '';
    const icon = item.icon
        ? `<img class="db-card-icon" src="${escapeHtml(item.icon)}" alt="${name}" loading="lazy">`
        : `<div class="db-card-icon db-card-icon-placeholder">?</div>`;

    const typeClass = `db-tag-${type.toLowerCase()}`;
    const tags = `
        ${type ? `<span class="db-tag ${typeClass}">${escapeHtml(type)}</span>` : ''}
        ${subtype ? `<span class="db-tag">${escapeHtml(subtype)}</span>` : ''}
    `;

    return `<div class="db-card db-card-with-icon" data-search="${escapeHtml((name + ' ' + type + ' ' + subtype + ' ' + region + ' ' + sourceName).toLowerCase())}">
        ${icon}
        <div class="db-card-body">
            <div class="db-card-header">
                <span class="db-card-name">${name}</span>
                <span class="db-card-id">${id}</span>
            </div>
            <div style="margin-bottom:6px">${tags}</div>
            ${vestige}
            ${region ? `<div class="db-card-meta"><strong>Region:</strong> ${escapeHtml(region)}${subregion ? ' · ' + escapeHtml(subregion) : ''}</div>` : ''}
            ${source ? `<div class="db-card-meta"><strong>Source:</strong> ${escapeHtml(source)}${sourceName ? ' — ' + escapeHtml(sourceName) : ''}${cost}</div>` : ''}
        </div>
    </div>`;
}

function renderQuestCard(q) {
    const id = escapeHtml(q.id || '');
    const title = escapeHtml(q.title || '?');
    const type = q.quest_type || '';
    const region = q.region || '';
    const subregion = q.sub_region || '';
    const startNpc = q.start_npc___location || q.start_npc__location || '';
    const reward = q.reward_type || '';
    const rewardName = q.reward_name || '';

    const typeClass = `db-tag-${type.toLowerCase()}`;
    const tags = `${type ? `<span class="db-tag ${typeClass}">${escapeHtml(type)}</span>` : ''}`;

    return `<div class="db-card" data-search="${escapeHtml((title + ' ' + type + ' ' + region + ' ' + startNpc).toLowerCase())}">
        <div class="db-card-header">
            <span class="db-card-name">${title}</span>
            <span class="db-card-id">${id}</span>
        </div>
        <div style="margin-bottom:6px">${tags}</div>
        ${region ? `<div class="db-card-meta"><strong>Region:</strong> ${escapeHtml(region)}${subregion ? ' · ' + escapeHtml(subregion) : ''}</div>` : ''}
        ${startNpc ? `<div class="db-card-meta"><strong>Start:</strong> ${escapeHtml(startNpc)}</div>` : ''}
        ${reward ? `<div class="db-card-meta"><strong>Reward:</strong> ${escapeHtml(reward)}${rewardName ? ' — ' + escapeHtml(rewardName) : ''}</div>` : ''}
    </div>`;
}

function applyDbFilter() {
    const q = (document.getElementById('db-search')?.value || '').toLowerCase().trim();
    const cards = document.querySelectorAll('#db-grid .db-card');
    let shown = 0;
    cards.forEach(c => {
        const match = !q || (c.dataset.search || '').includes(q);
        c.classList.toggle('hidden', !match);
        if (match) shown++;
    });
    document.getElementById('db-counter').textContent = `${shown} of ${cards.length} entries`;
}
