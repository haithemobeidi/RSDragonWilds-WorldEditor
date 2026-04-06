/* api.js — HTTP helpers (DRY for fetch boilerplate) */

/**
 * POST JSON to an endpoint and return the parsed response.
 * On network failure, shows a toast and returns null.
 * Callers handle status interpretation themselves.
 */
async function apiPost(url, body) {
    try {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
        return await resp.json();
    } catch (e) {
        showToast('Network error: ' + e.message, true);
        return null;
    }
}

/** GET a JSON endpoint. */
async function apiGet(url) {
    try {
        const resp = await fetch(url);
        return await resp.json();
    } catch (e) {
        showToast('Network error: ' + e.message, true);
        return null;
    }
}
