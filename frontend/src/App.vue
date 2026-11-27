<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import { api, formatDateTime } from './api';
import CreditDialog from './components/CreditDialog.vue';

const health = ref(null);
const showCredit = ref(false);
let timer = null;

// Refreshed regularly so the credit estimate follows running phases
async function refresh() {
    health.value = await api.health().catch(() => null);
}
onMounted(() => {
    refresh();
    timer = setInterval(refresh, 10000);
});
onUnmounted(() => clearInterval(timer));

function credit(service) {
    const b = health.value?.budget?.[service];
    if (!b || b.remaining === null) return null;
    return b;
}

function creditClass(b) {
    if (b.remaining <= 0) return 'text-red-400';
    if (b.remaining < 1) return 'text-amber-300';
    return 'text-stone-300';
}

const creditTitle = (name, b) =>
    `${name}: stanje $${b.balance.toFixed(2)} uneseno ${formatDateTime(b.balance_at)}, ` +
    `od tada potrošeno $${b.spent_since.toFixed(2)}. Klikni za unos novog stanja.`;
</script>

<template>
  <header class="sticky top-0 z-30 bg-stone-900 text-white">
    <div class="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
      <RouterLink to="/" class="whitespace-nowrap font-display text-xl tracking-wide sm:text-2xl">
        BRAND POST <span class="text-dragon">RECIPE</span>
      </RouterLink>
      <div v-if="health" class="flex flex-col items-end whitespace-nowrap text-xs sm:flex-row sm:gap-3 sm:text-sm">
        <!-- Model names only on wider screens; the colored dot is the status -->
        <span v-for="[key, name, model] in [['claude', 'Claude', health.claude_model], ['gemini', 'Gemini', health.image_model]]"
              :key="key" class="flex items-baseline gap-1.5">
          <span :class="health[key] ? 'text-emerald-400' : 'text-red-400'">● {{ name }}<span class="ml-1 hidden lg:inline">{{ model }}</span></span>
          <button v-if="credit(key)" type="button" :class="creditClass(credit(key))" :title="creditTitle(name, credit(key))"
                  class="text-xs underline decoration-dotted underline-offset-4 hover:text-white" @click="showCredit = true">
            ~${{ credit(key).remaining.toFixed(2) }}<span class="hidden sm:inline"> preostalo</span>
          </button>
          <button v-else type="button" class="text-xs text-stone-400 underline decoration-dotted underline-offset-4 hover:text-white"
                  @click="showCredit = true">unesi kredit</button>
        </span>
      </div>
      <span v-else class="text-xs text-red-400">API nije dostupan</span>
    </div>
  </header>
  <CreditDialog v-if="showCredit && health" :health="health" @close="showCredit = false"
                @saved="(h) => (health = h)" />
  <main class="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:py-8">
    <RouterView />
  </main>
</template>
