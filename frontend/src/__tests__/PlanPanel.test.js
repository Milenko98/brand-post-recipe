import { describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import PlanPanel from '../components/PlanPanel.vue';
import { api } from '../api';

const slide = { purpose: 'hook', background: 'photo', product: 'Pils', product_position: 'center', headline: 'Stari', subline: '', scene_prompt: 'bar' };
const data = { strategy: 'S', posts: [{ number: 1, title: 'T', goal: 'G', format: 'single_image', concept: 'C', rationale: 'R', slides: [slide], caption: 'Opis', hashtags: [] }] };
const run = { id: 'r1', busy: false, phases: { create: { status: 'pending' } } };

describe('PlanPanel', () => {
    it('shows progress while saving and a confirmation afterwards', async () => {
        let finish;
        vi.spyOn(api, 'savePlan').mockReturnValue(new Promise((resolve) => (finish = resolve)));
        const w = mount(PlanPanel, { props: { run, data } });

        await w.find('input').setValue('Novi naslov');
        await w.find('input').trigger('input');
        await w.find('button.btn-primary').trigger('click');
        expect(w.text()).toContain('Spremam');
        expect(api.savePlan.mock.calls[0][1].posts[0].slides[0].headline).toBe('Novi naslov');

        finish({ recomposed: false });
        await flushPromises();
        expect(w.text()).toContain('Spremljeno');
        expect(w.emitted('saved')).toHaveLength(1);
    });
});
