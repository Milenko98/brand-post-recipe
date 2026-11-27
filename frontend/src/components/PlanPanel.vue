<script setup>
import { ref, watch } from 'vue';
import { api } from '../api';

const props = defineProps({ run: Object, data: Object });

const BACKGROUND = { photo: 'fotografija', graphic: 'grafika' };
const POSITION = { left: 'lijevo', center: 'sredina', right: 'desno' };
const emit = defineEmits(['saved']);

// Local editable copy of the plan; saving it invalidates image generation
const plan = ref(null);
const dirty = ref(false);
const error = ref('');

watch(() => props.data, (d) => {
    plan.value = JSON.parse(JSON.stringify(d));
    dirty.value = false;
}, { immediate: true });

async function save() {
    error.value = '';
    try {
        await api.savePlan(props.run.id, plan.value);
        dirty.value = false;
        emit('saved');
    } catch (e) {
        error.value = e.message;
    }
}
</script>

<template>
  <div class="space-y-4" @input="dirty = true">
    <div class="card">
      <span class="label">Strategija</span>
      <p class="text-sm">{{ plan.strategy }}</p>
    </div>

    <div v-for="post in plan.posts" :key="post.number" class="card space-y-4">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="font-display text-xl">Objava {{ post.number }}: {{ post.title }}</h3>
        <span class="rounded-full bg-stone-100 px-3 py-1 text-xs">
          {{ post.format === 'carousel' ? `Karusel · ${post.slides.length} slajda` : 'Jedna slika' }} · {{ post.goal }}
        </span>
      </div>
      <div class="grid gap-4 text-sm md:grid-cols-2">
        <div><span class="label">Koncept</span>{{ post.concept }}</div>
        <div><span class="label">Zašto odgovara brendu</span>{{ post.rationale }}</div>
      </div>

      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div v-for="(s, i) in post.slides" :key="i" class="rounded-lg bg-stone-50 p-3 text-xs">
          <p class="mb-2 font-semibold">Slajd {{ i + 1 }} – {{ s.purpose }}</p>
          <label class="label">Naslov</label>
          <input v-model="s.headline" class="input mb-2" />
          <label class="label">Podnaslov</label>
          <input v-model="s.subline" class="input mb-2" />
          <label class="label">Scena ({{ BACKGROUND[s.background] }}) · proizvod: {{ s.product || '—' }}, {{ POSITION[s.product_position] }}</label>
          <p class="mb-1 text-xs text-stone-500">Opis scene za generator slika ostaje na engleskom jer ga model tako najbolje razumije.</p>
          <textarea v-model="s.scene_prompt" class="input h-28 font-mono text-xs" />
        </div>
      </div>

      <div>
        <label class="label">Opis objave</label>
        <textarea v-model="post.caption" class="input h-32" />
        <p class="mt-1 text-xs text-stone-500">{{ post.hashtags.join(' ') }}</p>
      </div>
    </div>

    <div v-if="dirty || error" class="sticky bottom-4 card flex items-center justify-between gap-4 ring-2 ring-dragon">
      <span class="text-sm">{{ error || 'Imaš nespremljene izmjene plana. Promjene teksta i opisa su besplatne (slajdovi se ponovno slože iz postojećih scena); promjena opisa scene traži nove slike.' }}</span>
      <button class="btn-primary" :disabled="run.busy" @click="save">Spremi izmjene</button>
    </div>
  </div>
</template>
