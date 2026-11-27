import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import PhaseActions from '../components/PhaseActions.vue';

const phases = (statuses) =>
    Object.fromEntries(['brief', 'analysis', 'plan', 'create', 'review', 'deliver'].map((p, i) => [p, { status: statuses[i] || 'pending' }]));

const run = (statuses, extra = {}) => ({ busy: false, notes: {}, phases: phases(statuses), ...extra });

describe('PhaseActions', () => {
    it('cannot start a phase before the previous ones are done', () => {
        const w = mount(PhaseActions, { props: { run: run(['done']), phase: 'plan' } });
        expect(w.find('button.btn-primary').attributes('disabled')).toBeDefined();
        expect(w.text()).toContain('Prvo završi prethodne faze');
    });

    it('re-runs a finished phase with a note', async () => {
        const w = mount(PhaseActions, { props: { run: run(['done', 'done', 'done']), phase: 'plan' } });
        await w.find('button.btn-ghost').trigger('click');
        await w.find('textarea').setValue('Više humora');
        await w.findAll('button.btn-primary').at(1).trigger('click');
        expect(w.emitted('run')[0]).toEqual(['Više humora']);
    });

    it('shows the error of a failed phase', () => {
        const r = run(['done', 'failed']);
        r.phases.analysis.error = 'AIError: ANTHROPIC_API_KEY is not set';
        const w = mount(PhaseActions, { props: { run: r, phase: 'analysis' } });
        expect(w.text()).toContain('ANTHROPIC_API_KEY is not set');
    });

    it('disables actions while the run is busy', () => {
        const w = mount(PhaseActions, { props: { run: run(['done'], { busy: true }), phase: 'analysis' } });
        expect(w.find('button.btn-primary').attributes('disabled')).toBeDefined();
    });
});
