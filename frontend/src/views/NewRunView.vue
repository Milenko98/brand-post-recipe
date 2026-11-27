<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api';

const router = useRouter();
const error = ref('');
const sending = ref(false);

const form = reactive({
    brand: '',
    instagram: '',
    website: '',
    extraUrls: '',
    audience: '',
    goals: '',
    inspiration: '',
    constraints: '',
    captions: '',
    products: [{ name: '', notes: '', file: null }],
    logo: null,
    screenshots: [],
});

const lines = (text) => text.split('\n').map((l) => l.trim()).filter(Boolean);

async function prefillExample() {
    const b = await api.exampleBrief();
    Object.assign(form, {
        brand: b.brand,
        instagram: b.instagram,
        website: b.website,
        extraUrls: (b.extra_urls || []).join('\n'),
        audience: b.audience,
        goals: (b.goals || []).join('\n'),
        inspiration: b.inspiration || '',
        constraints: (b.constraints || []).join('\n'),
        products: b.products.map((p) => ({ name: p.name, notes: p.notes, file: null })),
    });
}

async function submit() {
    error.value = '';
    if (!form.logo || form.products.some((p) => !p.name || !p.file)) {
        error.value = 'Potrebni su logo te naziv i fotografija svakog proizvoda.';
        return;
    }
    const brief = {
        brand: form.brand,
        instagram: form.instagram,
        website: form.website,
        extra_urls: lines(form.extraUrls),
        audience: form.audience,
        goals: lines(form.goals),
        inspiration: form.inspiration,
        constraints: lines(form.constraints),
        products: form.products.map((p) => ({ name: p.name, notes: p.notes, image: '' })),
        logo: '',
    };
    const data = new FormData();
    data.append('brief', JSON.stringify(brief));
    data.append('captions', form.captions);
    data.append('logo', form.logo);
    form.products.forEach((p) => data.append('products', p.file));
    [...form.screenshots].forEach((s) => data.append('screenshots', s));

    sending.value = true;
    try {
        const { id } = await api.createRun(data);
        router.push(`/runs/${id}`);
    } catch (e) {
        error.value = e.message;
        sending.value = false;
    }
}
</script>

<template>
  <!-- Same layout as a run: the header stays in place, only the form scrolls -->
  <div class="lg:flex lg:h-[calc(100dvh-8rem)] lg:flex-col">
  <div class="mb-4 shrink-0 border-b border-stone-200 pb-4">
    <RouterLink to="/" class="text-sm text-stone-500 hover:text-dragon">← Sva pokretanja</RouterLink>
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="font-display text-3xl">Brifing</h1>
      <button class="btn-ghost" type="button" @click="prefillExample">Popuni primjerom (Zmajska)</button>
    </div>
  </div>

  <form class="grid gap-6 pb-6 lg:min-h-0 lg:flex-1 lg:grid-cols-2 lg:items-start lg:overflow-y-auto lg:pr-2" @submit.prevent="submit">
    <div class="card min-w-0 space-y-4">
      <h2 class="font-semibold">Brend</h2>
      <div><label class="label">Naziv brenda</label><input v-model="form.brand" class="input" required /></div>
      <div><label class="label">Instagram profil</label><input v-model="form.instagram" class="input" type="url" required /></div>
      <div><label class="label">Web-stranica / trgovina</label><input v-model="form.website" class="input" type="url" required /></div>
      <div>
        <label class="label">Dodatne poveznice (webshop, stranice proizvoda) – jedna po retku</label>
        <textarea v-model="form.extraUrls" class="input h-24 font-mono text-xs" />
      </div>
      <div><label class="label">Publika</label><textarea v-model="form.audience" class="input h-20" required /></div>
      <div><label class="label">Ciljevi – jedan po retku</label><textarea v-model="form.goals" class="input h-20" required /></div>
      <div><label class="label">Uzori i inspiracija</label><textarea v-model="form.inspiration" class="input h-16" /></div>
      <div><label class="label">Ograničenja – jedno po retku</label><textarea v-model="form.constraints" class="input h-16" /></div>
    </div>

    <div class="min-w-0 space-y-6">
      <div class="card space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">Proizvodi</h2>
          <button type="button" class="btn-ghost" @click="form.products.push({ name: '', notes: '', file: null })">+ Proizvod</button>
        </div>
        <p class="text-xs text-stone-500">Fotografija proizvoda na prozirnoj pozadini (PNG/WebP). Ona se ne generira – ide u objavu točno takva.</p>
        <div v-for="(p, i) in form.products" :key="i" class="grid grid-cols-[1fr_auto] items-end gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <div><label class="label">Naziv</label><input v-model="p.name" class="input" /></div>
          <button v-if="form.products.length > 1" type="button" class="btn-ghost sm:col-start-3 sm:row-start-1" @click="form.products.splice(i, 1)">✕</button>
          <div class="col-span-full sm:col-span-1"><label class="label">Napomena</label><input v-model="p.notes" class="input" placeholder="npr. limenka 0,5 L" /></div>
          <input class="col-span-full w-full min-w-0 text-sm" type="file" accept="image/*" @change="p.file = $event.target.files[0]" />
        </div>
      </div>

      <div class="card space-y-3">
        <h2 class="font-semibold">Reference</h2>
        <div><label class="label">Logo (PNG)</label><input class="w-full min-w-0 text-sm" type="file" accept="image/*" @change="form.logo = $event.target.files[0]" /></div>
        <div>
          <label class="label">Screenshotovi objava s Instagrama</label>
          <input class="w-full min-w-0 text-sm" type="file" accept="image/*" multiple @change="form.screenshots = $event.target.files" />
        </div>
        <div>
          <label class="label">Opisi objava (copy-paste)</label>
          <textarea v-model="form.captions" class="input h-32" />
        </div>
      </div>

      <p v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
      <button class="btn-primary w-full justify-center py-3" :disabled="sending">
        {{ sending ? 'Šaljem…' : 'Spremi brif i pokreni prvu fazu' }}
      </button>
    </div>
  </form>
  </div>
</template>
