<template>
  <div class="card">
    <div class="flex items-center justify-between">
      <div>
        <p class="text-sm text-gray-600 dark:text-gray-400">{{ title }}</p>
        <p class="text-3xl font-bold mt-2">{{ value.toLocaleString() }}</p>
      </div>
      <div class="text-4xl">{{ icon }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: String,
  value: Number,
  icon: String
})
</script>

