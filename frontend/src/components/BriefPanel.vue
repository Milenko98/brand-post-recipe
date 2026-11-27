<script setup>
import { fileUrl } from '../api';

defineProps({ run: Object, data: Object });
</script>

<template>
  <div class="card space-y-5">
    <div class="grid gap-4 md:grid-cols-2">
      <div>
        <span class="label">Brend</span>
        <p class="font-semibold">{{ data.brief.brand }}</p>
        <a :href="data.brief.instagram" target="_blank" class="text-sm text-dragon underline">{{ data.brief.instagram }}</a>
      </div>
      <div><span class="label">Publika</span><p class="text-sm">{{ data.brief.audience }}</p></div>
      <div>
        <span class="label">Ciljevi</span>
        <ul class="list-disc pl-5 text-sm"><li v-for="g in data.brief.goals" :key="g">{{ g }}</li></ul>
      </div>
      <div>
        <span class="label">Ograničenja</span>
        <ul class="list-disc pl-5 text-sm"><li v-for="c in data.brief.constraints" :key="c">{{ c }}</li></ul>
      </div>
    </div>

    <div>
      <span class="label">Proizvodi i logo</span>
      <div class="flex flex-wrap items-end gap-4">
        <figure v-for="p in data.brief.products" :key="p.name" class="text-center">
          <img :src="fileUrl(run.id, `inputs/${p.image}`)" class="h-32 object-contain" :alt="p.name" />
          <figcaption class="text-xs">{{ p.name }}</figcaption>
        </figure>
        <img :src="fileUrl(run.id, `inputs/${data.brief.logo}`)" class="h-16 object-contain" alt="logo" />
      </div>
    </div>

    <div>
      <span class="label">Web izvori</span>
      <ul class="space-y-1 text-sm">
        <li v-for="s in data.sources" :key="s.url" class="flex gap-2">
          <span :class="s.ok ? 'text-emerald-600' : 'text-red-600'">{{ s.ok ? '✓' : '✕' }}</span>
          <a :href="s.url" target="_blank" class="truncate underline">{{ s.url }}</a>
          <span v-if="!s.ok" class="text-xs text-red-600">{{ s.error }}</span>
        </li>
      </ul>
    </div>

    <div v-if="data.brief.post_screenshots.length">
      <span class="label">Screenshotovi objava ({{ data.brief.post_screenshots.length }})</span>
      <div class="flex gap-2 overflow-x-auto pb-2">
        <img v-for="s in data.brief.post_screenshots" :key="s" :src="fileUrl(run.id, `inputs/${s}`)"
             class="h-48 rounded" :alt="s" :title="s" />
      </div>
    </div>
  </div>
</template>
