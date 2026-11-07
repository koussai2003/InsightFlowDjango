<script setup>
import { computed, ref } from 'vue'
const prompt = ref(''), file = ref(null), headers = ref([]), preview = ref([]), error = ref(''), questions = ref([]), dragging = ref(false), reading = ref(false)
const picker = ref(null)
let selection = 0
const suggestions = ['Help me understand this dataset', 'What should I clean first?', 'How should I evaluate my model?']
const size = computed(() => file.value ? (file.value.size / 1024).toFixed(1) + ' KB' : '')
// Parse quoted CSV fields (including escaped quotes and embedded newlines).
// Only the header and first five rows are retained for the local preview.
function sampleCSV(text) {
  const rows = []; let row = [], field = '', quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++ }
      else if (!field || quoted) quoted = !quoted
      else field += c
    } else if (c === ',' && !quoted) { row.push(field); field = '' }
    else if ((c === '\n' || c === '\r') && !quoted) {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(field); if (row.some(v => v.trim())) rows.push(row)
      row = []; field = ''; if (rows.length === 6) return rows
    } else field += c
  }
  if (quoted) throw new Error('The CSV has an unclosed quoted field. Please check the file.')
  row.push(field); if (row.some(v => v.trim())) rows.push(row)
  return rows
}
async function attach(selected) {
  const version = ++selection
  error.value = ''; dragging.value = false
  if (!selected) return
  if (!/\.csv$/i.test(selected.name)) { error.value = 'Choose a CSV file to preview your dataset.'; return }
  if (selected.size > 10 * 1024 * 1024) { error.value = 'Please choose a CSV smaller than 10 MB for this preview.'; return }
  reading.value = true
  try {
    const rows = sampleCSV((await selected.text()).replace(/^\uFEFF/, ''))
    if (!rows.length) throw new Error('This file is empty. Choose a CSV with column names and data.')
    if (version !== selection) return
    file.value = selected; headers.value = rows[0]; preview.value = rows.slice(1)
  } catch (e) { if (version === selection) error.value = e.message }
  finally { if (version === selection) reading.value = false }
}
function clearFile() { selection++; reading.value = false; file.value = null; headers.value = []; preview.value = []; if (picker.value) picker.value.value = '' }
function send() {
  if (!prompt.value.trim() || reading.value) return
  questions.value.push({ text: prompt.value.trim(), dataset: file.value?.name })
  prompt.value = ''
}
</script>
<template>
  <div class="workspace-page">
    <header class="page-header"><div><span class="eyebrow">YOUR WORKSPACE</span><h1>Data studio</h1></div><span class="status-pill"><i></i> Local preview</span></header>
    <div class="studio-body">
      <div class="welcome"><span class="studio-mark" aria-hidden="true">IF<span>✦</span></span><span class="eyebrow">FROM DATA TO UNDERSTANDING</span><h2>Good questions.<br><span>Clearer insights.</span></h2><p>Bring your dataset. Start with a question.<br>A dedicated space for your next discovery.</p></div>
      <section class="conversation" v-if="questions.length" aria-label="Your questions" aria-live="polite"><article v-for="(question, index) in questions" :key="index" class="question"><span class="eyebrow">YOU <span v-if="question.dataset">· {{ question.dataset }}</span></span><p>{{ question.text }}</p><small>Question saved in this session. AI responses are not connected yet.</small></article></section>
      <form class="composer" :class="{ dragging }" @submit.prevent="send" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="attach($event.dataTransfer.files[0])">
        <label class="sr-only" for="question">Ask a question about your data</label><textarea id="question" v-model="prompt" placeholder="What would you like to understand about your data?" maxlength="4000" @keydown.ctrl.enter.prevent="send" @keydown.meta.enter.prevent="send"></textarea>
        <div class="attachment" v-if="file"><span class="file-icon">CSV</span><span><strong>{{ file.name }}</strong><small>{{ size }} · {{ headers.length }} columns</small></span><button class="icon-button" type="button" aria-label="Remove dataset" @click="clearFile">×</button></div>
        <div class="composer-toolbar"><input ref="picker" class="sr-only" type="file" accept=".csv,text/csv" aria-label="Choose CSV dataset" @change="attach($event.target.files[0]); $event.target.value = ''"><button type="button" class="attach-button" :disabled="reading" @click="picker.click()"><span aria-hidden="true">＋</span> {{ reading ? 'Reading dataset…' : 'Attach dataset' }}</button><span class="file-hint">CSV · up to 10 MB</span><button class="send-button" :disabled="!prompt.trim() || reading" aria-label="Send question" title="Send question (Ctrl + Enter)">↑</button></div>
      </form>
      <p v-if="error" class="notice error" role="alert">{{ error }}</p>
      <div class="suggestions"><button v-for="suggestion in suggestions" :key="suggestion" @click="prompt = suggestion">{{ suggestion }} <span aria-hidden="true">↗</span></button></div>
      <p class="workspace-note">Your file stays in this browser session. AI analysis and cloud uploads are coming next.</p>
      <section v-if="file" class="dataset-preview"><div class="section-heading"><div><span class="eyebrow">DATASET PREVIEW</span><h3>{{ file.name }}</h3></div><span>First {{ preview.length }} rows</span></div><div class="table-scroll"><table><thead><tr><th v-for="(column, i) in headers" :key="i">{{ column || 'Column ' + (i + 1) }}</th></tr></thead><tbody><tr v-for="(row, i) in preview" :key="i"><td v-for="(_, j) in headers" :key="j">{{ row[j] ?? '—' }}</td></tr></tbody></table></div></section>
      <div class="workflow-strip" v-else><span><b>01</b> Understand</span><span class="flow-line"></span><span><b>02</b> Prepare</span><span class="flow-line"></span><span><b>03</b> Explore</span><span class="flow-line"></span><span><b>04</b> Evaluate</span></div>
    </div>
    <footer class="studio-footer"><span>InsightFlow / Data, with direction.</span><span>Workspace preview</span></footer>
  </div>
</template>
