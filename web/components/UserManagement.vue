<script setup>
import { computed, reactive, ref } from 'vue'
const props = defineProps({ rows: Array, user: Object, busy: Boolean })
const emit = defineEmits(['save', 'refresh'])
const query = ref(''), drafts = reactive({})
const roles = { data_scientist: 'Member', administrator: 'Platform administrator' }
const filtered = computed(() => props.rows.filter(row => row.email.toLowerCase().includes(query.value.toLowerCase())))
function roleFor(row) { return drafts[row.id] ?? row.role }
</script>
<template>
  <section class="settings-page">
    <header class="page-header"><div><span class="eyebrow">ADMINISTRATION</span><h1>Platform accounts</h1></div><button class="settings-action" :disabled="busy" @click="emit('refresh')">Refresh users</button></header>
    <div class="settings-content">
      <p class="page-intro">Manage platform access. Project membership is separate; administrators cannot browse private projects without an invitation.</p>
      <label class="user-search">Find a user<input v-model="query" type="search" placeholder="Search by email" autocomplete="off"></label>
      <div class="role-table table-scroll"><table><thead><tr><th>Account</th><th>Role</th><th>Action</th></tr></thead><tbody><tr v-for="row in filtered" :key="row.id"><td><span :title="row.email">{{ row.email }}</span><span v-if="row.id === user.id" class="primary-badge">You</span></td><td><label class="sr-only" :for="'role-' + row.id">Role for {{ row.email }}</label><select :id="'role-' + row.id" :value="roleFor(row)" :disabled="busy || row.id === user.id" @change="drafts[row.id] = $event.target.value"><option v-for="(label, value) in roles" :key="value" :value="value">{{ label }}</option></select></td><td><span v-if="row.id === user.id" class="role-self-note">Managed by another admin</span><button v-else class="settings-action" :disabled="busy || roleFor(row) === row.role" @click="emit('save', row, roleFor(row))">{{ busy ? 'Please wait…' : 'Save role' }}</button></td></tr></tbody></table><p v-if="!filtered.length" class="empty-users">{{ rows.length ? 'No users match this email.' : 'No verified accounts to display.' }}</p></div>
      <p class="role-footnote">New accounts start as Members and own their private workspace. Your own role must be changed by another administrator.</p>
    </div>
  </section>
</template>
