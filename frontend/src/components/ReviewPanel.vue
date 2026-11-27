<script setup>
defineProps({ run: Object, data: Object });

const checks = { product_accurate: 'proizvod', looks_natural: 'prirodno', brand_consistent: 'brend', text_legible: 'tekst' };
</script>

<template>
  <div class="space-y-4">
    <div v-for="post in data.posts" :key="post.number" class="card space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="font-display text-xl">Objava {{ post.number }}</h3>
        <span class="rounded-full px-3 py-1 text-xs font-semibold"
              :class="post.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'">
          {{ post.passed ? 'Prošla provjeru' : 'Treba ljudski pregled' }}
        </span>
      </div>
      <p v-if="post.regenerated_slides.length" class="text-sm text-stone-600">
        Ponovno generirani slajdovi: {{ post.regenerated_slides.join(', ') }}
      </p>

      <div v-if="post.caption_edited_by_human" class="rounded-lg bg-sky-50 p-3 text-sm text-sky-900">
        <p class="font-semibold">Opis je ručno uređen, pa ga provjera nije mijenjala.</p>
        <p class="mt-1">Primjedbe provjere su ispod; odluka je tvoja.</p>
        <details v-if="post.suggested_caption" class="mt-2">
          <summary class="cursor-pointer">Prijedlog provjere</summary>
          <p class="mt-1 whitespace-pre-line text-stone-700">{{ post.suggested_caption }}</p>
        </details>
      </div>

      <div v-for="(round, r) in post.rounds" :key="r" class="rounded-lg bg-stone-50 p-3">
        <p class="mb-2 text-xs font-semibold uppercase text-stone-500">Krug {{ r + 1 }}</p>
        <div v-for="s in round.slides" :key="s.slide" class="mb-2 text-sm">
          <b>Slajd {{ s.slide }}: {{ s.score }}/10</b>
          <span v-for="(label, key) in checks" :key="key" class="ml-2 text-xs"
                :class="s[key] ? 'text-emerald-600' : 'text-red-600'">{{ s[key] ? '✓' : '✕' }} {{ label }}</span>
          <ul v-if="s.issues.length" class="list-disc pl-5 text-xs text-stone-600"><li v-for="i in s.issues" :key="i">{{ i }}</li></ul>
          <p v-if="s.scene_fix" class="text-xs text-amber-700">Ispravak scene: {{ s.scene_fix }}</p>
        </div>
        <div v-if="round.caption_issues.length" class="text-xs">
          <span class="font-semibold">Problemi u opisu:</span>
          <ul class="list-disc pl-5"><li v-for="i in round.caption_issues" :key="i">{{ i }}</li></ul>
        </div>
      </div>
    </div>
  </div>
</template>
