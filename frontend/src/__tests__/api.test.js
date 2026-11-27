import { describe, expect, it, vi } from 'vitest';
import { api, fileUrl } from '../api';

function mockFetch(status, body) {
    return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: status < 400,
        status,
        json: () => Promise.resolve(body),
    });
}

describe('api', () => {
    it('sends the note when re-running a phase', async () => {
        const fetch = mockFetch(202, { status: 'started' });
        await api.runPhase('r1', 'plan', 'More humor');
        const [url, options] = fetch.mock.calls[0];
        expect(url).toBe('/api/runs/r1/phases/plan');
        expect(JSON.parse(options.body)).toEqual({ note: 'More humor' });
    });

    it('turns FastAPI validation errors into a readable message', async () => {
        mockFetch(422, { detail: [{ loc: ['body', 'posts'], msg: 'too short' }] });
        await expect(api.savePlan('r1', {})).rejects.toThrow('body.posts: too short');
    });

    it('uses the plain detail string for other errors', async () => {
        mockFetch(409, { detail: 'A phase of this run is already running' });
        await expect(api.continueRun('r1')).rejects.toThrow('already running');
    });

    it('builds file urls with a cache-busting version', () => {
        expect(fileUrl('r1', 'final/post_1/slide_1.png', '2026-01-01T10:00')).toBe(
            '/api/runs/r1/files/final/post_1/slide_1.png?v=2026-01-01T10%3A00',
        );
    });
});
