<script setup>
import { onMounted, ref } from 'vue'
const labels = { data_scientist: 'Data scientist', reviewer: 'Reviewer', administrator: 'Administrator' }
const user = ref(null), rows = ref([]), message = ref(''), busy = ref(false)
const registering = ref(false), email = ref(''), password = ref(''), workspace = ref('')
async function api(path, method = 'GET', body) {
  const response = await fetch('/api' + path, {
    method, headers: { 'Content-Type': 'application/json', 'X-InsightFlow': '1' },
    body: body ? JSON.stringify(body) : undefined
  })
  if (response.status === 204) return
  const data = await response.json()
  if (!response.ok) {
    if (response.status === 401) user.value = null
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Check your email and password.')
  }
  return data
}
async function load() {
  rows.value = []
  workspace.value = ''
  user.value = await api('/me')
  if (user.value.role === 'administrator') rows.value = await api('/admin/accounts')
  else {
    const path = user.value.role === 'reviewer' ? 'review' : 'preparation'
    workspace.value = (await api('/workspaces/' + path)).title
  }
}
async function run(action) {
  busy.value = true
  message.value = ''
  try { await action() } catch (error) { message.value = error.message }
  finally { busy.value = false }
}
async function submit() {
  await run(async () => {
    const credentials = { email: email.value, password: password.value }
    if (registering.value) {
      await api('/accounts', 'POST', credentials)
      registering.value = false
      message.value = 'Account created. Sign in to continue.'
    } else {
      await api('/session', 'POST', credentials)
      await load()
    }
    password.value = ''
  })
}
async function updateRole(row) {
  await run(async () => {
    await api('/admin/accounts/' + row.id, 'PATCH', { role: row.role })
    await load()
    message.value = 'Role saved.'
  })
}
async function signOut() {
  await run(async () => { await api('/session', 'DELETE'); user.value = null; rows.value = []; workspace.value = '' })
}
onMounted(async () => {
  try { await load() } catch (error) { if (error.message !== 'Sign in to continue') message.value = error.message }
})
</script>
<template>
  <header>InsightFlow</header>
  <section v-if="!user">
    <h1>{{ registering ? 'Create account' : 'Sign in' }}</h1>
    <form @submit.prevent="submit">
      <label>Email<input v-model="email" type="email" autocomplete="email" required></label>
      <label>Password<input v-model="password" type="password" :minlength="registering ? 12 : 1" maxlength="128" :autocomplete="registering ? 'new-password' : 'current-password'" required></label>
      <small v-if="registering">Use at least 12 characters.</small>
      <button :disabled="busy">{{ registering ? 'Create account' : 'Sign in' }}</button>
    </form>
    <button class="link" :disabled="busy" @click="registering = !registering; message = ''; password = ''">{{ registering ? 'Sign in instead' : 'Create an account' }}</button>
  </section>
  <section v-else>
    <h1>{{ user.role === 'administrator' ? 'Manage account roles' : workspace }}</h1>
    <p>{{ user.email }} · {{ labels[user.role] }}</p>
    <ul v-if="user.role === 'administrator'">
      <li v-for="row in rows" :key="row.id">
        <label>{{ row.email }}
          <select v-model="row.role" :disabled="busy || row.id === user.id">
            <option v-for="(label, value) in labels" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <button v-if="row.id !== user.id" :disabled="busy" @click="updateRole(row)">Save</button>
      </li>
    </ul>
    <button class="link" :disabled="busy" @click="signOut">Sign out</button>
  </section>
  <p role="status" aria-live="polite">{{ message }}</p>
</template>
