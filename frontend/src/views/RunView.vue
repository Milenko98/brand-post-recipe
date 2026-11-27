<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { api, PHASE_LABELS } from '../api';
import StatusDot from '../components/StatusDot.vue';
import PhaseActions from '../components/PhaseActions.vue';
import BriefPanel from '../components/BriefPanel.vue';
import AnalysisPanel from '../components/AnalysisPanel.vue';
import PlanPanel from '../components/PlanPanel.vue';
import CreatePanel from '../components/CreatePanel.vue';
import ReviewPanel from '../components/ReviewPanel.vue';
import DeliverPanel from '../components/DeliverPanel.vue';

const props = defineProps({ id: String, phase: String });
const router = useRouter();

const run = ref(null);
const error = ref('');
let timer = null;

const PANELS = { brief: BriefPanel, analysis: AnalysisPanel, plan: PlanPanel, create: CreatePanel, review: ReviewPanel, deliver: DeliverPanel };
const phases = Object.keys(PHASE_LABELS);

// Show the phase from the URL, otherwise the latest phase that has something to show
const selected = computed(() => {
    if (props.phase) return props.phase;
    if (!run.value) return 'brief';
    const active = phases.find((p) => ['running', 'failed'].includes(run.value.phases[p].status));
    return active || [...phases].reverse().find((p) => run.value.phases[p].status === 'done') || 'brief';
});

async function load() {
    try {
        run.value = await api.run(props.id);
        error.value = '';
    } catch (e) {
        error.value = e.message;
    }
    clearTimeout(timer);
    // Poll fast while a phase is running, slowly otherwise: work can also be started from the CLI
    timer = setTimeout(load, run.value?.busy ? 2000 : 6000);
}

async function act(promise) {
    try {
        await promise;
        await load();
    } catch (e) {
        error.value = e.message;
    }
}

watch(() => props.id, load, { immediate: true });
onUnmounted(() => clearTimeout(timer));

// On mobile the phases are a horizontal strip: keep the selected one in view
const nav = ref(null);
watch([selected, nav], async () => {
    await nextTick();
    const strip = nav.value;
    const tab = strip?.querySelector('[aria-current="page"]');
    if (tab && strip.scrollWidth > strip.clientWidth) {
        strip.scrollLeft = tab.offsetLeft - (strip.clientWidth - tab.offsetWidth) / 2;
    }
});

const usd = (v) => (v === undefined ? '–' : `$${v.toFixed(2)}`);
const num = (v) => v.toLocaleString('hr-HR');

const select = (phase) => router.push(`/runs/${props.id}/${phase}`);
</script>

<template>
  <!-- Desktop: header and phase menu stay put, only the phase content scrolls.
       Mobile: the page scrolls normally and the phases are a sticky tab strip. -->
  <div v-if="run" class="lg:flex lg:h-[calc(100dvh-8rem)] lg:flex-col">
    <div class="mb-4 flex shrink-0 flex-wrap items-end justify-between gap-4 border-b border-stone-200 pb-4">
      <div class="min-w-0">
        <RouterLink to="/" class="text-sm text-stone-500 hover:text-dragon">← Sva pokretanja</RouterLink>
        <h1 class="break-all font-mono text-base sm:text-lg">{{ run.id }}</h1>
        <dl class="mt-1 flex flex-wrap gap-x-6 gap-y-1 text-sm text-stone-600">
          <div><dt class="inline font-semibold">Ukupni trošak:</dt> <dd class="ml-1 inline">{{ usd(run.usage.cost_usd) }}</dd></div>
          <div title="Ulazni tokeni: sve što je poslano Claudeu (brif, web tekstovi, slike). Izlazni: ono što je Claude napisao, uključujući razmišljanje.">
            <dt class="inline font-semibold">Claude:</dt>
            <dd class="ml-1 inline">{{ usd(run.usage.claude_cost_usd) }} · {{ num(run.usage.claude_input_tokens) }} ulaznih
              + {{ num(run.usage.claude_output_tokens) }} izlaznih tokena</dd>
          </div>
          <div><dt class="inline font-semibold">Gemini:</dt> <dd class="ml-1 inline">{{ usd(run.usage.gemini_cost_usd) }} · {{ run.usage.images }} slika</dd></div>
        </dl>
      </div>
      <button class="btn-primary w-full justify-center sm:w-auto" :disabled="run.busy || run.phases.deliver.status === 'done'"
              @click="act(api.continueRun(run.id))">
        Pokreni sve preostale faze
      </button>
    </div>

    <p v-if="error" class="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>

    <div class="grid grid-cols-[minmax(0,1fr)] gap-4 lg:min-h-0 lg:flex-1 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-6">
      <nav ref="nav" class="sticky top-16 z-20 -mx-4 flex gap-1 overflow-x-auto bg-stone-100 px-4 py-2 sm:-mx-6 sm:px-6
                  lg:static lg:mx-0 lg:block lg:space-y-1 lg:self-start lg:p-0">
        <button v-for="(p, i) in phases" :key="p" type="button"
                class="flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-left text-sm whitespace-nowrap lg:w-full lg:gap-3"
                :class="selected === p ? 'bg-stone-900 text-white' : 'hover:bg-white'"
                :aria-current="selected === p ? 'page' : undefined"
                @click="select(p)">
          <StatusDot :status="run.phases[p].status" />
          <span class="text-xs opacity-60">{{ i + 1 }}</span>
          {{ PHASE_LABELS[p] }}
        </button>
      </nav>

      <section class="min-w-0 space-y-4 pb-6 lg:min-h-0 lg:overflow-y-auto lg:pr-2">
        <PhaseActions :run="run" :phase="selected"
                      @run="(note) => act(api.runPhase(run.id, selected, note))" />
        <component :is="PANELS[selected]" v-if="run.outputs[selected]" :run="run"
                   :data="run.outputs[selected]" @saved="load" />
        <div v-else-if="run.phases[selected].status === 'running'" class="card animate-pulse text-sm text-stone-500">
          Faza je u tijeku… (ovdje se automatski prikaže rezultat)
          <pre class="mt-3 max-h-48 overflow-auto text-xs">{{ run.log.slice(-6).join('\n') }}</pre>
        </div>
      </section>
    </div>
  </div>
  <p v-else-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
</template>
