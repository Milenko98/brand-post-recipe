<script setup>
defineProps({ status: { type: String, required: true } });

const colors = {
    done: 'bg-emerald-500',
    running: 'bg-amber-400 animate-pulse',
    failed: 'bg-red-500',
    pending: 'bg-stone-300',
};
</script>

<template>
  <span class="inline-block h-2.5 w-2.5 rounded-full" :class="colors[status] || colors.pending" />
</template>
