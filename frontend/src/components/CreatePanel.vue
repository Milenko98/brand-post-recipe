<script setup>
import { ref } from 'vue';
import { api, fileUrl } from '../api';

const props = defineProps({ run: Object, data: Object });
const emit = defineEmits(['saved']);
const error = ref('');
// Changes when the slides are regenerated or re-composited, so the browser loads the new files
const version = () => `${props.run.phases.create.finished}-${props.run.log.filter((l) => l.includes('re-composited')).length}`;

async function recompose() {
    error.value = '';
    try {
        await api.recompose(props.run.id);
        emit('saved');
    } catch (e) {
        error.value = e.message;
    }
}
</script>

<template>
  <div class="space-y-4">
    <div class="card flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-stone-600">
        AI generira samo pozadinu; pravi proizvod, logo i naslov slažu se preko nje.
        Nakon izmjene teksta ili načina slaganja slajdovi se mogu ponovno složiti iz postojećih pozadina, bez troška.
      </p>
      <button class="btn-ghost" :disabled="run.busy" @click="recompose">Ponovno složi slajdove (besplatno)</button>
      <p v-if="error" class="w-full text-sm text-red-700">{{ error }}</p>
    </div>
    <div v-for="post in data.posts" :key="post.number" class="card">
      <h3 class="mb-3 font-display text-xl">Objava {{ post.number }}</h3>
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <div v-for="slide in post.slides" :key="slide.index" class="space-y-2">
          <img :src="fileUrl(run.id, slide.final_file, version())" class="w-full rounded-lg ring-1 ring-stone-200"
               :alt="`Objava ${post.number}, slajd ${slide.index}`" />
          <details v-for="a in slide.attempts" :key="a.attempt" class="text-xs">
            <summary class="cursor-pointer">
              Pokušaj {{ a.attempt }}
              <span v-if="a.score !== null" class="ml-1 rounded bg-stone-100 px-1">ocjena {{ a.score }}/10</span>
              <span v-if="a.final_file === slide.final_file" class="ml-1 text-emerald-600">odabran</span>
            </summary>
            <p v-if="a.feedback" class="mt-1 text-amber-700">Ispravak: {{ a.feedback }}</p>
            <div class="mt-1 grid grid-cols-2 gap-1">
              <figure><img :src="fileUrl(run.id, a.scene_file)" class="rounded" /><figcaption>AI scena</figcaption></figure>
              <figure><img :src="fileUrl(run.id, a.final_file, version())" class="rounded" /><figcaption>Složeno</figcaption></figure>
            </div>
            <pre class="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-stone-50 p-2 text-xs">{{ a.scene_prompt }}</pre>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>
