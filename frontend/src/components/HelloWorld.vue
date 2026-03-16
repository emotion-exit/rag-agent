<script setup lang="ts">
defineProps<{
  msg: string;
}>();
</script>

<template>
  <div class="text-center lg:text-left">
    <h1
      class="relative -top-2.5 text-[2.6rem] font-medium text-(--color-success)">
      {{ msg }}
    </h1>
    <h3 class="text-[1.2rem]">
      You’ve successfully created a project with
      <a href="https://vite.dev/" target="_blank" rel="noopener">Vite</a>
      +
      <a href="https://vuejs.org/" target="_blank" rel="noopener">Vue 3</a>
      . What's next?
    </h3>
  </div>
</template>
