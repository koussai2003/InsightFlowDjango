<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import Brand from './components/Brand.vue'
import ProjectSpace from './components/ProjectSpace.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import UserManagement from './components/UserManagement.vue'
function currentPage() { return { '#/settings': 'settings', '#/team': 'team' }[window.location.hash] || 'workspace' }
const page = ref(currentPage())
async function refreshAccess() {
  if (!user.value || busy.value) return
  try { await load() } catch (error) { message.value = error.message }
}
function syncPage() { page.value = currentPage(); message.value = ''; refreshAccess() }
onMounted(() => window.addEventListener('hashchange', syncPage))
onUnmounted(() => window.removeEventListener('hashchange', syncPage))
onMounted(() => window.addEventListener('focus', refreshAccess))
onUnmounted(() => window.removeEventListener('focus', refreshAccess))
const labels = { data_scientist: 'Member', reviewer: 'Member', administrator: 'Platform administrator' }
const user = ref(null), rows = ref([]), message = ref(''), busy = ref(false)
const signupPending = ref(false), signupCode = ref('')
const deleteConfirmation = ref('')
const confirmation = ref(''), setting = ref(''), pending = ref(false), currentPassword = ref(''), newEmail = ref(''), newPassword = ref(''), newConfirmation = ref(''), code = ref(''), newCode = ref('')
const registering = ref(false), email = ref(''), password = ref(''), workspace = ref('')
const securitySections = [
  { id: 'email', title: 'Email address', description: 'Update the email you use to sign in and receive verification codes.', action: 'Change email' },
  { id: 'password', title: 'Password', description: 'Choose a strong password to protect your account.', action: 'Change password' },
  { id: 'delete', title: 'Danger zone', description: 'Permanently delete your account and end all active sessions. This cannot be undone.', action: 'Delete account' },
]
function selectSetting(value = '') {
  if (busy.value) return
  setting.value = value
  pending.value = false
  message.value = ''
  deleteConfirmation.value = currentPassword.value = newEmail.value = newPassword.value = newConfirmation.value = code.value = newCode.value = ''
}
async function api(path, method = 'GET', body) {
  let response
  try {
    response = await fetch('/api' + path, {
    signal: AbortSignal.timeout(40000),
    method, headers: { 'Content-Type': 'application/json', 'X-InsightFlow': '1' },
    body: body ? JSON.stringify(body) : undefined
    })
  } catch (error) {
    throw new Error(error.name === 'TimeoutError' ? 'The server took too long to respond. Please try again.' : 'Cannot reach the server. Please try again.')
  }
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
      signupPending.value = true
      message.value = 'Check your email and follow the verification link. If your email contains a code, enter it below.'
    } else {
      await api('/session', 'POST', credentials)
      await load()
      window.location.hash = '/workspace'
    }
    password.value = ''
  })
}
async function updateRole(row, role) {
  await run(async () => {
    await api('/admin/accounts/' + row.id, 'PATCH', { role })
    await load()
    message.value = 'Role updated for ' + row.email + '.'
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
    // Keep the password only in component memory until verification completes.
    code.value = newCode.value = ''
    message.value = 'Verification email requested. Enter the code from your email within 10 minutes.'
  })
}
async function securityVerify() {
  await run(async () => {
    const result = await api('/me/security/verify', 'POST', { code: code.value, current_password: currentPassword.value, ...(setting.value === 'password' ? {new_password: newPassword.value, confirm_password: newConfirmation.value} : {}), ...(setting.value === 'delete' ? { delete_confirmation: deleteConfirmation.value } : {}), ...(setting.value === 'email' ? { new_email_code: newCode.value } : {}) })
    user.value = null
    pending.value = false
    setting.value = ''
    code.value = newCode.value = password.value = ''
    rows.value = []; workspace.value = ''; deleteConfirmation.value = ''; currentPassword.value = newPassword.value = newConfirmation.value = ''
    message.value = result.message
  })
}
async function verifySignup() {
  await run(async () => {
    await api('/accounts/verify', 'POST', {email: email.value, code: signupCode.value})
    signupPending.value = false
    signupCode.value = ''
    await load()
    message.value = 'Email verified. Welcome to InsightFlow.'
  })
}
async function resendSignup() {
  await run(async () => {
    const result = await api('/accounts/resend', 'POST', {email: email.value})
    message.value = result.message
  })
}
onMounted(async () => {
  const fragment = new URLSearchParams(window.location.hash.slice(1))
  const token = fragment.get('access_token')
  const error = fragment.get('error_description')
  if (token || error) history.replaceState(null, '', window.location.pathname + '#/workspace')
  if (error) { message.value = 'Verification link is invalid or expired. Request another email.'; return }
  try {
    if (token) {
      await api('/session/link', 'POST', {access_token: token})
      message.value = 'Email verified. Welcome to InsightFlow.'
    }
    await load()
  } catch (error) { if (error.message !== 'Sign in to continue') message.value = error.message }
})
</script>
<template>
  <div v-if="!user" class="auth-layout">
    <ThemeToggle class="auth-theme-toggle"/>
    <aside class="auth-story"><Brand/><div class="auth-story-copy"><span class="eyebrow">A LITTLE CLARITY GOES A LONG WAY</span><h2>Your data.<br>Your questions.<br><em>Your next insight.</em></h2><p>A thoughtful space to understand, prepare, and explore your data.</p><div class="abstract-chart" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><span>From possibility to perspective</span></div></div><small>INSIGHTFLOW / DATA, WITH DIRECTION.</small></aside>
    <main class="auth-main"><div class="mobile-brand"><Brand/></div><section class="auth-card"><span class="eyebrow">LET'S GET STARTED</span>
    <h1>{{ signupPending ? 'Verify your email' : registering ? 'Create account' : 'Sign in' }}</h1>
    <form v-if="!signupPending" @submit.prevent="submit">
      <label>Email<input v-model="email" type="email" autocomplete="email" required></label>
      <label>Password<input v-model="password" type="password" :minlength="registering ? 12 : 1" maxlength="128" :autocomplete="registering ? 'new-password' : 'current-password'" required></label>
      <label v-if="registering">Confirm password<input v-model="confirmation" type="password" autocomplete="new-password" required maxlength="128"></label>
      <small v-if="registering">Use at least 12 characters.</small>
      <button :disabled="busy">{{ busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in' }}</button>
    </form>
    <div v-if="signupPending">
      <p>We requested a verification email for <strong>{{ email }}</strong>. Open it and follow the confirmation link, then return here to sign in.</p>
      <form @submit.prevent="verifySignup">
        <label>Verification code (if provided in your email)<input v-model="signupCode" inputmode="numeric" pattern="[0-9]{6,10}" maxlength="10" autocomplete="one-time-code" required></label>
        <button :disabled="busy">Verify code</button>
      </form>
      <button class="link" :disabled="busy" @click="resendSignup">Resend verification email</button>
      <button class="link" :disabled="busy" @click="signupPending = false; registering = false; signupCode = ''">Return to sign in</button>
    </div>
    <button v-if="!signupPending" class="link" :disabled="busy" @click="registering = !registering; message = ''; password = ''">{{ registering ? 'Sign in instead' : 'Create an account' }}</button>

    <p class="notice" v-if="message" role="status" aria-live="polite">{{ message }}</p></section><span class="auth-footnote">A clearer view starts here.</span></main>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar"><a class="brand-link" href="#/workspace" aria-label="InsightFlow home"><Brand/></a><div class="sidebar-nav"><span class="nav-label">WORKSPACE</span><a href="#/workspace" :class="{ active: page === 'workspace' }" :aria-current="page === 'workspace' ? 'page' : undefined"><span class="nav-icon">&#9707;</span> My projects</a><a v-if="user.role === 'administrator'" href="#/team" :class="{ active: page === 'team' }" :aria-current="page === 'team' ? 'page' : undefined"><span class="nav-icon">&#9783;</span> Platform accounts</a></div><div class="sidebar-note"><span class="little-spark">&#10022;</span><strong>Every insight starts<br>with a question.</strong><p>Make room for discovery.</p></div><div class="account-nav"><div class="user-card"><span class="avatar">{{ user.email.charAt(0).toUpperCase() }}</span><div><strong>{{ labels[user.role] }}</strong><span :title="user.email">{{ user.email }}</span></div></div><a href="#/settings" :class="{ active: page === 'settings' }" :aria-current="page === 'settings' ? 'page' : undefined"><span class="nav-icon">&#9881;</span> Account settings</a><ThemeToggle/><button class="signout" :disabled="busy" @click="signOut"><span class="nav-icon">&#8599;</span> Sign out</button></div></aside>
    <main class="app-main"><ProjectSpace v-show="page === 'workspace'" :api="api" :user="user"/><UserManagement v-if="page === 'team' && user.role === 'administrator'" :rows="rows" :user="user" :busy="busy" @save="updateRole" @refresh="run(load)"/><section v-else-if="page === 'team'" class="settings-content"><h1>Administrator access required</h1><p class="page-intro">Your account cannot manage other users.</p><a class="link" href="#/workspace">Return to your workspace</a></section><section v-show="page === 'settings'" class="settings-page"><header class="page-header"><div><span class="eyebrow">YOUR ACCOUNT</span><h1>Account settings</h1></div><span class="status-pill">{{ labels[user.role] }}</span></header><div class="settings-content"><p class="page-intro">Manage your details and keep your account secure.</p><div class="profile-card"><span class="avatar large">{{ user.email.charAt(0).toUpperCase() }}</span><div><h2>{{ labels[user.role] }}</h2><p>{{ user.email }}</p></div><span class="profile-badge">Signed in</span></div><div class="settings-sections">
      <section v-for="section in securitySections" :key="section.id" class="settings-section" :class="{ 'danger-zone': section.id === 'delete' }" :aria-labelledby="'heading-' + section.id">
        <h2 :id="'heading-' + section.id">{{ section.title }}</h2>
        <div class="settings-section-body">
          <div class="settings-row">
            <div class="settings-description"><strong v-if="section.id === 'email'" class="current-email">{{ user.email }} <span class="primary-badge">Primary</span></strong><p>{{ section.description }}</p></div>
            <button type="button" class="settings-action" :class="{ 'delete-action': section.id === 'delete' }" :disabled="busy || (pending && setting !== section.id)" :aria-expanded="setting === section.id" :aria-controls="'editor-' + section.id" @click="selectSetting(setting === section.id ? '' : section.id)">{{ setting === section.id ? 'Cancel' : section.action }}</button>
          </div>
          <div v-if="setting === section.id" :id="'editor-' + section.id" class="settings-editor">
    <form v-if="!pending" @submit.prevent="securityRequest">
      <p v-if="setting === 'delete'" role="alert">Deleting your account permanently removes your login and ends all active sessions. This cannot be undone.</p>
      <label>Current password<input v-model="currentPassword" type="password" autocomplete="current-password" required></label>
      <label v-if="setting === 'email'">New email<input v-model="newEmail" type="email" autocomplete="email" required></label>
      <template v-else-if="setting === 'password'">
        <label>New password<input v-model="newPassword" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></label>
        <label>Confirm new password<input v-model="newConfirmation" type="password" autocomplete="new-password" required></label>
      </template>
      <p>{{ setting === 'email' ? 'Verify both your current and new email addresses.' : 'A verification code will be sent to your current email.' }}</p>
      <button :disabled="busy">{{ busy ? 'Please wait…' : 'Send verification code' }}{{ setting === 'email' ? 's' : '' }}</button>
    </form>
    <form v-if="pending" @submit.prevent="securityVerify">
      <label>Code sent to your current email<input v-model="code" inputmode="numeric" pattern="[0-9]{6,10}" maxlength="10" autocomplete="one-time-code" required></label>
      <label v-if="setting === 'email'">Code sent to your new email<input v-model="newCode" inputmode="numeric" pattern="[0-9]{6,10}" maxlength="10" required></label>
      <label v-if="setting === 'delete'">Type DELETE to confirm permanent deletion<input v-model="deleteConfirmation" pattern="DELETE" autocomplete="off" required></label>
      <button :class="{ danger: setting === 'delete' }" :disabled="busy || (setting === 'delete' && deleteConfirmation !== 'DELETE')">{{ setting === 'delete' ? 'Permanently delete my account' : 'Verify and save' }}</button>
      <button type="button" class="link" :disabled="busy" @click="pending = false">Request new codes</button>
    </form>

            <p v-if="message" class="notice" role="status" aria-live="polite">{{ message }}</p>
          </div>
        </div>
      </section>
    </div></div></section><p v-if="message && !(page === 'settings' && setting)" class="notice app-notice" role="status" aria-live="polite">{{ message }}</p></main>
  </div>
</template>
