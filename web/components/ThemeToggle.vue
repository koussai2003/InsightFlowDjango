<script setup>
import { ref } from 'vue'
const dark = ref(document.documentElement.dataset.theme !== 'light')
function toggle() {
  dark.value = !dark.value
  const theme = dark.value ? 'dark' : 'light'
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
  try { localStorage.setItem('insightflow-theme', theme) } catch { /* Keep the current-session choice. */ }
}
</script>
<template>
  <button type="button" class="theme-toggle" role="switch" :aria-checked="dark" aria-label="Dark mode" @click="toggle">
    <svg v-if="dark" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M20.5 13.4A8.5 8.5 0 0 1 10.6 3.5a8.5 8.5 0 1 0 9.9 9.9Z"/></svg>
    <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/></svg>
    <span>{{ dark ? 'Dark mode' : 'Light mode' }}</span><span class="theme-track" aria-hidden="true"><i></i></span>
  </button>
</template>
