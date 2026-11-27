<script setup>
import { ref } from 'vue';
import { fileUrl } from '../api';

const props = defineProps({ run: Object, data: Object });
const version = props.run.phases.deliver.finished || '';
const copied = ref(null);

async function copy(post) {
    await navigator.clipboard.writeText(post.caption);
    copied.value = post.number;
}
</script>

<template>
  <div class="space-y-4">
    <div class="card flex items-center justify-between">
      <span class="text-sm">Sve objave, opisi, sažetak i međurezultati faza:</span>
      <a :href="fileUrl(run.id, data.zip_file, version)" class="btn-primary" download>Preuzmi ZIP</a>
    </div>

    <div v-for="post in data.posts" :key="post.number" class="card">
      <h3 class="mb-3 font-display text-xl">Objava {{ post.number }}: {{ post.title }}</h3>
      <div class="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div class="flex snap-x gap-3 overflow-x-auto pb-2">
          <img v-for="f in post.files" :key="f" :src="fileUrl(run.id, f, version)"
               class="w-72 shrink-0 snap-start rounded-lg ring-1 ring-stone-200" />
        </div>
        <div>
          <div class="mb-2 flex items-center justify-between">
            <span class="label">Opis</span>
            <button class="text-xs text-dragon" @click="copy(post)">{{ copied === post.number ? 'Kopirano ✓' : 'Kopiraj' }}</button>
          </div>
          <p class="whitespace-pre-line text-sm">{{ post.caption }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
