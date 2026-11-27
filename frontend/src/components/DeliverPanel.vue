<script setup>
import { reactive, ref } from 'vue';
import { fileUrl } from '../api';

const props = defineProps({ run: Object, data: Object });
const version = props.run.phases.deliver.finished || '';
const copied = ref(null);
const expanded = reactive({});

// Goal and QA status come from the plan and review phases of the same run
const planned = (n) => props.run.outputs.plan?.posts.find((p) => p.number === n);
const reviewed = (n) => props.run.outputs.review?.posts.find((p) => p.number === n);
const formatLabel = (post) => {
    const n = post.files.length;
    return post.format === 'carousel' ? `Karusel · ${n} ${n >= 2 && n <= 4 ? 'slajda' : 'slajdova'}` : 'Jedna slika';
};

async function copy(post) {
    await navigator.clipboard.writeText(post.caption);
    copied.value = post.number;
}
</script>

<template>
  <div class="space-y-4">
    <div class="card flex items-center justify-between gap-4">
      <span class="text-sm">Sve objave, opisi, sažetak i međurezultati faza:</span>
      <a :href="fileUrl(run.id, data.zip_file, version)" class="btn-primary shrink-0" download>Preuzmi ZIP</a>
    </div>

    <div v-for="post in data.posts" :key="post.number" class="card space-y-4">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="font-display text-xl">Objava {{ post.number }}: {{ post.title }}</h3>
        <div class="flex flex-wrap gap-2 text-xs">
          <span class="rounded-full bg-stone-100 px-3 py-1">{{ formatLabel(post) }}</span>
          <span v-if="planned(post.number)" class="rounded-full bg-stone-100 px-3 py-1">{{ planned(post.number).goal }}</span>
          <span v-if="reviewed(post.number)" class="rounded-full px-3 py-1 font-semibold"
                :class="reviewed(post.number).passed ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'">
            {{ reviewed(post.number).passed ? 'Prošla provjeru' : 'Treba ljudski pregled' }}
          </span>
        </div>
      </div>

      <!-- Slides at their real 4:5 ratio, scrolling sideways like a carousel -->
      <div class="flex snap-x gap-3 overflow-x-auto pb-2">
        <img v-for="f in post.files" :key="f" :src="fileUrl(run.id, f, version)" :alt="`Objava ${post.number}`"
             class="aspect-[4/5] w-56 shrink-0 snap-start rounded-lg object-cover ring-1 ring-stone-200 sm:w-64" />
      </div>

      <div class="rounded-lg bg-stone-50 p-4">
        <div class="mb-2 flex items-center justify-between">
          <span class="label">Opis objave</span>
          <button class="text-xs font-semibold text-dragon" @click="copy(post)">
            {{ copied === post.number ? 'Kopirano ✓' : 'Kopiraj' }}
          </button>
        </div>
        <div class="relative" :class="expanded[post.number] ? '' : 'max-h-36 overflow-hidden'">
          <p class="whitespace-pre-line text-sm">{{ post.caption }}</p>
          <div v-if="!expanded[post.number]"
               class="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-stone-50" />
        </div>
        <button class="mt-2 text-xs font-semibold text-stone-600 hover:text-dragon"
                @click="expanded[post.number] = !expanded[post.number]">
          {{ expanded[post.number] ? 'Sakrij' : 'Prikaži cijeli opis' }}
        </button>
      </div>
    </div>
  </div>
</template>
