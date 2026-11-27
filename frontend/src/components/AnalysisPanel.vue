<script setup>
defineProps({ run: Object, data: Object });
</script>

<template>
  <div class="space-y-4">
    <div class="card space-y-4">
      <p>{{ data.summary }}</p>
      <div class="grid gap-4 md:grid-cols-2">
        <div><span class="label">Publika</span><p class="text-sm">{{ data.audience }}</p></div>
        <div><span class="label">Ton</span><p class="text-sm">{{ data.tone_of_voice }}</p></div>
      </div>
      <div>
        <span class="label">Primjeri tona</span>
        <blockquote v-for="q in data.tone_examples" :key="q" class="border-l-4 border-dragon pl-3 text-sm italic">{{ q }}</blockquote>
      </div>
      <div>
        <span class="label">Pravila pisanja</span>
        <ul class="list-disc pl-5 text-sm"><li v-for="r in data.language_rules" :key="r">{{ r }}</li></ul>
      </div>
    </div>

    <div class="card space-y-4">
      <div>
        <span class="label">Boje</span>
        <div class="flex flex-wrap gap-3">
          <div v-for="c in data.colors" :key="c.hex + c.name" class="flex items-center gap-2" :title="c.usage">
            <span class="h-8 w-8 rounded ring-1 ring-stone-300" :style="{ background: c.hex }" />
            <span class="text-xs"><b>{{ c.name }}</b><br />{{ c.hex }}</span>
          </div>
        </div>
      </div>
      <div class="grid gap-4 text-sm md:grid-cols-2">
        <div><span class="label">Fotografija</span>{{ data.photography_style }}</div>
        <div><span class="label">Grafika</span>{{ data.graphic_style }}</div>
        <div><span class="label">Tipografija</span>{{ data.typography }}</div>
        <div><span class="label">Prikaz proizvoda</span>{{ data.product_presentation }}</div>
      </div>
    </div>

    <div class="card">
      <span class="label">Proizvodi</span>
      <table class="w-full text-left text-sm">
        <thead class="text-xs text-stone-500"><tr><th>Naziv</th><th>Stil</th><th>Alk.</th><th>Volumen</th><th>Izvor</th></tr></thead>
        <tbody>
          <tr v-for="p in data.products" :key="p.name" class="border-t border-stone-100 align-top">
            <td class="py-1 font-semibold">{{ p.name }}</td><td>{{ p.style }}</td><td>{{ p.abv }}</td>
            <td>{{ p.volume }}</td><td class="max-w-48 truncate text-xs">{{ p.source }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <div class="card">
        <span class="label">Činjenice</span>
        <ul class="space-y-1 text-sm">
          <li v-for="f in data.facts" :key="f.claim">
            <span :class="f.verified ? 'text-emerald-600' : 'text-amber-600'">{{ f.verified ? '✓ provjereno' : '? neprovjereno' }}</span>
            {{ f.claim }} <span class="text-xs text-stone-400">({{ f.source }})</span>
          </li>
        </ul>
      </div>
      <div class="card space-y-3">
        <div>
          <span class="label">Pretpostavke</span>
          <ul class="list-disc pl-5 text-sm"><li v-for="a in data.assumptions" :key="a">{{ a }}</li></ul>
        </div>
        <div v-if="data.unavailable_sources.length">
          <span class="label">Nedostupni izvori</span>
          <ul class="list-disc pl-5 text-sm"><li v-for="u in data.unavailable_sources" :key="u">{{ u }}</li></ul>
        </div>
      </div>
    </div>

    <details class="card">
      <summary class="cursor-pointer text-sm font-semibold">Dokazi ({{ data.evidence.length }})</summary>
      <ul class="mt-3 space-y-1 text-sm">
        <li v-for="e in data.evidence" :key="e.observation">{{ e.observation }} <span class="text-xs text-stone-400">– {{ e.reference }}</span></li>
      </ul>
    </details>
  </div>
</template>
