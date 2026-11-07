<script setup>
import { onMounted, ref } from 'vue'
const labels = { data_scientist: 'Data scientist', reviewer: 'Reviewer', administrator: 'Administrator' }
const user = ref(null), rows = ref([]), message = ref(''), busy = ref(false)
const deleteConfirmation = ref('')
const confirmation = ref(''), setting = ref(''), pending = ref(false), currentPassword = ref(''), newEmail = ref(''), newPassword = ref(''), newConfirmation = ref(''), code = ref(''), newCode = ref('')
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
      await api('/accounts', 'POST', { ...credentials, confirm_password: confirmation.value })
      confirmation.value = ''
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
  await run(async () => { await api('/session', 'DELETE'); user.value = null; rows.value = []; workspace.value = ''; setting.value = ''; pending.value = false; currentPassword.value = newPassword.value = newConfirmation.value = code.value = newCode.value = '' })
}
async function securityRequest() {
  await run(async () => {
    await api('/me/security/request', 'POST', {
      current_password: currentPassword.value,
      ...(setting.value === 'delete' ? { delete_account: true } : setting.value === 'email' ? { new_email: newEmail.value } : { new_password: newPassword.value, confirm_password: newConfirmation.value })
    })
    pending.value = true
    currentPassword.value = newPassword.value = newConfirmation.value = ''
    code.value = newCode.value = ''
    message.value = 'Codes sent. They expire in 10 minutes.'
  })
}
async function securityVerify() {
  await run(async () => {
    const result = await api('/me/security/verify', 'POST', { code: code.value, ...(setting.value === 'delete' ? { delete_confirmation: deleteConfirmation.value } : {}), ...(setting.value === 'email' ? { new_email_code: newCode.value } : {}) })
    user.value = null
    pending.value = false
    setting.value = ''
    code.value = newCode.value = password.value = ''
    rows.value = []; workspace.value = ''; deleteConfirmation.value = ''
    message.value = result.message
  })
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
      <label v-if="registering">Confirm password<input v-model="confirmation" type="password" autocomplete="new-password" required maxlength="128"></label>
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
    <h2>Account settings</h2>
    <label>Change<select v-model="setting" :disabled="busy" @change="deleteConfirmation = ''; pending = false; message = ''; currentPassword = ''; newPassword = ''; newConfirmation = ''; code = ''; newCode = ''">
      <option value="">Choose an option</option><option value="email">Email address</option><option value="password">Password</option><option value="delete">Delete account</option>
    </select></label>
    <form v-if="setting && !pending" @submit.prevent="securityRequest">
      <p v-if="setting === 'delete'" role="alert">Deleting your account permanently removes your login and ends all active sessions. This cannot be undone.</p>
      <label>Current password<input v-model="currentPassword" type="password" autocomplete="current-password" required></label>
      <label v-if="setting === 'email'">New email<input v-model="newEmail" type="email" autocomplete="email" required></label>
      <template v-else-if="setting === 'password'">
        <label>New password<input v-model="newPassword" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></label>
        <label>Confirm new password<input v-model="newConfirmation" type="password" autocomplete="new-password" required></label>
      </template>
      <p>{{ setting === 'email' ? 'Verify both your current and new email addresses.' : 'A verification code will be sent to your current email.' }}</p>
      <button :disabled="busy">Send verification code{{ setting === 'email' ? 's' : '' }}</button>
    </form>
    <form v-if="pending" @submit.prevent="securityVerify">
      <label>Code sent to your current email<input v-model="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" required></label>
      <label v-if="setting === 'email'">Code sent to your new email<input v-model="newCode" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required></label>
      <label v-if="setting === 'delete'">Type DELETE to confirm permanent deletion<input v-model="deleteConfirmation" pattern="DELETE" autocomplete="off" required></label>
      <button :class="{ danger: setting === 'delete' }" :disabled="busy || (setting === 'delete' && deleteConfirmation !== 'DELETE')">{{ setting === 'delete' ? 'Permanently delete my account' : 'Verify and save' }}</button>
      <button type="button" class="link" :disabled="busy" @click="pending = false">Request new codes</button>
    </form>
    <button class="link" :disabled="busy" @click="signOut">Sign out</button>
  </section>
  <p role="status" aria-live="polite">{{ message }}</p>
</template>

<style scoped>
.danger { background: #b42318; color: white; border-color: #b42318; }
.danger:disabled { opacity: .5; }
</style>
