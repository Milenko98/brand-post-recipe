<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue';
import { api, formatDateTime } from '../api';

const props = defineProps({ health: Object });
const emit = defineEmits(['close', 'saved']);

const NAMES = { claude: 'Claude (Anthropic)', gemini: 'Gemini (Google AI Studio)' };
const form = reactive(Object.fromEntries(
    Object.entries(props.health.budget).map(([key, b]) => [key, b.remaining === null ? '' : b.remaining.toFixed(2)]),
));
const saving = ref('');

// Esc closes the dialog
const onKey = (e) => e.key === 'Escape' && emit('close');
onMounted(() => window.addEventListener('keydown', onKey));
onUnmounted(() => window.removeEventListener('keydown', onKey));
const error = ref('');

async function save(service) {
    error.value = '';
    saving.value = service;
    try {
        const value = String(form[service]).replace(',', '.').trim();
        const health = await api.setCredit(service, value === '' ? null : Number(value));
        emit('saved', health);
    } catch (e) {
        error.value = e.message;
    } finally {
        saving.value = '';
    }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4">
    <div class="card my-auto w-full max-w-lg space-y-5 text-stone-900">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h2 class="font-display text-2xl">Stanje kredita</h2>
          <p class="mt-1 text-sm text-stone-600">
            Provideri nemaju API za stanje računa. Upiši iznos koji vidiš u konzoli; aplikacija od tog trenutka
            oduzima svaki trošak koji zabilježi i ne pokreće posao koji preostali kredit ne može platiti.
          </p>
        </div>
        <button class="text-2xl leading-none text-stone-400 hover:text-stone-900" aria-label="Zatvori" @click="emit('close')">×</button>
      </div>

      <div v-for="(b, key) in health.budget" :key="key" class="space-y-2 rounded-lg bg-stone-50 p-4">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <span class="font-semibold">{{ NAMES[key] }}</span>
          <a :href="b.console" target="_blank" rel="noopener" class="text-sm text-dragon hover:underline">Otvori konzolu ↗</a>
        </div>
        <p v-if="b.balance !== null" class="text-sm text-stone-600">
          Uneseno {{ formatDateTime(b.balance_at) }}: ${{ b.balance.toFixed(2) }}, od tada potrošeno
          ${{ b.spent_since.toFixed(2) }} → preostalo <b>~${{ b.remaining.toFixed(2) }}</b>
        </p>
        <p v-else class="text-sm text-stone-600">Stanje nije uneseno, pa nema ograničenja potrošnje.</p>
        <form class="flex gap-2" @submit.prevent="save(key)">
          <div class="relative flex-1">
            <span class="absolute top-1/2 left-3 -translate-y-1/2 text-stone-400">$</span>
            <input v-model="form[key]" class="input pl-7" inputmode="decimal" placeholder="npr. 2.26"
                   :aria-label="`Stanje ${NAMES[key]}`" />
          </div>
          <button class="btn-primary" :disabled="saving === key">{{ saving === key ? 'Spremam…' : 'Spremi' }}</button>
        </form>
      </div>

      <p v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
      <p class="text-xs text-stone-500">Prazno polje i Spremi uklanja ograničenje za taj servis.</p>
    </div>
  </div>
</template>
