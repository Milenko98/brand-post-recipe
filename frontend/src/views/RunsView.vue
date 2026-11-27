<script setup>
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api, PHASE_LABELS } from '../api';
import StatusDot from '../components/StatusDot.vue';

const router = useRouter();
const runs = ref([]);
const error = ref('');
const starting = ref(false);

onMounted(async () => {
    runs.value = await api.runs().catch((e) => (error.value = e.message, []));
});

async function startExample() {
    starting.value = true;
    try {
        const { id } = await api.createExample();
        router.push(`/runs/${id}`);
    } catch (e) {
        error.value = e.message;
        starting.value = false;
    }
}
</script>

<template>
  <section class="mb-8 grid gap-4 md:grid-cols-2">
    <div class="card">
      <h2 class="font-display text-xl">Demo: Zmajska pivovara</h2>
      <p class="mt-2 text-sm text-stone-600">
        Pokreće recept s pripremljenim brifom, screenshotovima objava, fotografijama piva i logotipom
        (<code>inputs/zmajska/</code>).
      </p>
      <button class="btn-primary mt-4" :disabled="starting" @click="startExample">Pokreni demo</button>
    </div>
    <div class="card">
      <h2 class="font-display text-xl">Novi brend</h2>
      <p class="mt-2 text-sm text-stone-600">
        Interaktivni brifing: web-stranica, proizvodi, publika, ciljevi i učitavanje fotografija, logotipa i referenci.
      </p>
      <RouterLink to="/new" class="btn-ghost mt-4">Novi brif</RouterLink>
    </div>
  </section>

  <p v-if="error" class="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>

  <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">Dosadašnja pokretanja</h2>
  <div class="card divide-y divide-stone-100 overflow-hidden p-0">
    <RouterLink v-for="run in runs" :key="run.id" :to="`/runs/${run.id}`"
                class="flex flex-col gap-2 px-5 py-3 hover:bg-stone-50 sm:flex-row sm:items-center sm:justify-between">
      <span class="break-all font-mono text-sm">{{ run.id }}</span>
      <span class="flex items-center gap-3">
        <span class="flex gap-1">
          <StatusDot v-for="(status, phase) in run.phases" :key="phase" :status="status" :title="PHASE_LABELS[phase]" />
        </span>
        <span class="w-16 text-right text-xs text-stone-500">${{ run.cost_usd.toFixed(2) }}</span>
      </span>
    </RouterLink>
    <p v-if="!runs.length" class="px-5 py-4 text-sm text-stone-500">Još nema pokretanja.</p>
  </div>
</template>
