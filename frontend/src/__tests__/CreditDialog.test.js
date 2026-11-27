import { describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import CreditDialog from '../components/CreditDialog.vue';
import { api, formatDateTime } from '../api';

const health = {
    budget: {
        claude: { balance: 2.26, balance_at: '2026-11-27T14:48:20+01:00', spent_since: 0.5, remaining: 1.76, console: 'https://x' },
        gemini: { balance: null, balance_at: null, spent_since: 0, remaining: null, console: 'https://y' },
    },
};

describe('CreditDialog', () => {
    it('saves the balance typed with a decimal comma', async () => {
        vi.spyOn(api, 'setCredit').mockResolvedValue(health);
        const w = mount(CreditDialog, { props: { health } });
        const input = w.findAll('input').at(1);
        await input.setValue('4,50');
        await w.findAll('form').at(1).trigger('submit');
        await flushPromises();
        expect(api.setCredit).toHaveBeenCalledWith('gemini', 4.5);
        expect(w.emitted('saved')).toHaveLength(1);
    });

    it('shows when the balance was entered as a normal date', () => {
        const w = mount(CreditDialog, { props: { health } });
        expect(w.text()).toContain(formatDateTime('2026-11-27T14:48:20+01:00'));
        expect(formatDateTime('2026-11-27T14:48:20+01:00')).toMatch(/27\. ?11\. ?2026\. u \d\d:\d\d/);
    });

    it('closes on Escape', () => {
        const onClose = vi.fn();
        const w = mount(CreditDialog, { props: { health, onClose } });
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(onClose).toHaveBeenCalledTimes(1);
        w.unmount();
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(onClose).toHaveBeenCalledTimes(1); // listener removed with the dialog
    });
});
