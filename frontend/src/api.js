async function request(method, url, body) {
    const options = { method, headers: { Accept: 'application/json' } };
    if (body instanceof FormData) {
        options.body = body;
    } else if (body !== undefined) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = Array.isArray(data.detail)
            ? data.detail.map((d) => `${(d.loc || []).join('.')}: ${d.msg}`).join('; ')
            : data.detail;
        throw new Error(detail || `HTTP ${response.status}`);
    }
    return data;
}

export const api = {
    health: () => request('GET', '/api/health'),
    exampleBrief: () => request('GET', '/api/example-brief'),
    runs: () => request('GET', '/api/runs'),
    run: (id) => request('GET', `/api/runs/${id}`),
    createExample: () => request('POST', '/api/runs/example'),
    createRun: (formData) => request('POST', '/api/runs', formData),
    runPhase: (id, phase, note) => request('POST', `/api/runs/${id}/phases/${phase}`, { note: note || null }),
    continueRun: (id) => request('POST', `/api/runs/${id}/continue`),
    savePlan: (id, plan) => request('PUT', `/api/runs/${id}/plan`, plan),
};

export function fileUrl(runId, path, version = '') {
    return `/api/runs/${runId}/files/${path}${version ? `?v=${encodeURIComponent(version)}` : ''}`;
}

export const PHASE_LABELS = {
    brief: 'Brif',
    analysis: 'Analiza brenda',
    plan: 'Plan objava',
    create: 'Izrada',
    review: 'Provjera',
    deliver: 'Isporuka',
};
