<script setup>
import { computed, ref } from 'vue';
import { PHASE_LABELS } from '../api';

const props = defineProps({ run: Object, phase: String });
const emit = defineEmits(['run']);

const DESCRIPTIONS = {
    brief: 'Provjera ulaza, čitanje opisa objava i službene web-stranice (sve poveznice se bilježe).',
    analysis: 'Claude analizira screenshotove, opise i web: ton, publika, boje, stil, proizvodi, provjerene činjenice i pretpostavke.',
    plan: 'Claude osmišljava tri objave: cilj, format, koncept, obrazloženje, slajdove, promptove za scenu i tekstove.',
    create: 'Gemini generira samo pozadinske scene; pravi proizvod, logo i naslov slažu se preko njih (etiketa ostaje točna).',
    review: 'Claude kao art direktor ocjenjuje svaki slajd i opis; loši slajdovi se automatski ponovno generiraju s ispravkama.',
    deliver: 'Gotove objave, opisi s hashtagovima, sažetak i ZIP.',
};

const note = ref('');
const showNote = ref(false);

const info = computed(() => props.run.phases[props.phase]);
const index = computed(() => Object.keys(PHASE_LABELS).indexOf(props.phase));
const ready = computed(() =>
    Object.keys(PHASE_LABELS).slice(0, index.value).every((p) => props.run.phases[p].status === 'done'),
);
const canNote = computed(() => ['analysis', 'plan', 'create'].includes(props.phase));

function start() {
    emit('run', showNote.value ? note.value : null);
    showNote.value = false;
    note.value = '';
}
</script>

<template>
  <div class="card">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div class="max-w-2xl">
        <h2 class="font-display text-2xl">{{ index + 1 }}. {{ PHASE_LABELS[phase] }}</h2>
        <p class="mt-1 text-sm text-stone-600">{{ DESCRIPTIONS[phase] }}</p>
        <p v-if="run.notes[phase]" class="mt-2 text-xs text-stone-500">Zadnja napomena: „{{ run.notes[phase] }}“</p>
      </div>
      <div class="flex gap-2">
        <button v-if="info.status === 'done' && canNote" class="btn-ghost" :disabled="run.busy"
                @click="showNote = !showNote">
          Ponovi s napomenom
        </button>
        <button class="btn-primary" :disabled="run.busy || !ready" @click="start">
          {{ info.status === 'pending' ? 'Pokreni' : 'Pokreni ponovno' }}
        </button>
      </div>
    </div>

    <div v-if="showNote" class="mt-4 space-y-2">
      <textarea v-model="note" class="input h-20"
                placeholder="npr. Više humora, manje stručnih izraza. Drugu objavu napravi kao kviz o hmelju." />
      <button class="btn-primary" :disabled="!note.trim() || run.busy" @click="start">Ponovi fazu s ovom napomenom</button>
    </div>

    <p v-if="info.status === 'failed'" class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ info.error }}</p>
    <p v-if="!ready && info.status === 'pending'" class="mt-3 text-xs text-stone-500">Prvo završi prethodne faze.</p>
    <p v-if="info.status === 'done' && index < 5" class="mt-3 text-xs text-stone-500">
      Pregledaj rezultat. Ako je dobar, pokreni sljedeću fazu; ako nije, ponovi ovu s napomenom.
      Ponavljanje faze poništava sve faze nakon nje.
    </p>
  </div>
</template>
