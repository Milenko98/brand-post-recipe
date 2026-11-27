<script setup>
import { onMounted, ref } from 'vue';
import { api } from './api';

const health = ref(null);
onMounted(async () => {
    health.value = await api.health().catch(() => null);
});
</script>

<template>
  <header class="bg-stone-900 text-white">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
      <RouterLink to="/" class="font-display text-2xl tracking-wide">
        BRAND POST <span class="text-dragon">RECIPE</span>
      </RouterLink>
      <div v-if="health" class="flex gap-3 text-xs">
        <span :class="health.claude ? 'text-emerald-400' : 'text-red-400'">● Claude {{ health.claude_model }}</span>
        <span :class="health.gemini ? 'text-emerald-400' : 'text-red-400'">● Gemini {{ health.image_model }}</span>
      </div>
      <span v-else class="text-xs text-red-400">API nije dostupan</span>
    </div>
  </header>
  <main class="mx-auto max-w-7xl px-6 py-8">
    <RouterView />
  </main>
</template>
