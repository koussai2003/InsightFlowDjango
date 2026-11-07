<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Workspace from './Workspace.vue'
const props=defineProps({api:Function,user:Object})
const projects=ref([]), selected=ref(null), members=ref([]), sent=ref([]), inbox=ref([])
const view=ref('studio'), name=ref(''), email=ref(''), inviteRole=ref('data_scientist'), targetOwner=ref(''), deletion=ref(''), transferConfirmed=ref(false)
const busy=ref(false), error=ref(''), notice=ref(''), ready=ref(false)
const roleNames={owner:'Owner',moderator:'Moderator',data_scientist:'Data Scientist',reviewer:'Reviewer'}
const canManage=computed(()=>['owner','moderator'].includes(selected.value?.role))
const owner=computed(()=>selected.value?.role==='owner')
const projectPath=()=>'/projects/'+selected.value.id
let generation=0
async function refresh(id=selected.value?.id) {
  const version=++generation; ready.value=false
  try {
    const list=await props.api('/projects'), invitations=await props.api('/invitations')
    if(version!==generation)return
    projects.value=list; inbox.value=invitations
    selected.value=list.find(p=>p.id===id)||list[0]||null
    members.value=[];sent.value=[]
    if(selected.value){
      const path=projectPath()
      const people=await props.api(path+'/members')
      const invites=canManage.value ? await props.api(path+'/invitations') : []
      if(version!==generation)return
      members.value=people;sent.value=invites
    }
    ready.value=true
  } catch(e) { if(version===generation){selected.value=null;members.value=[];sent.value=[];error.value=e.message;ready.value=true} }
}
async function run(action){ if(busy.value)return;busy.value=true;error.value='';notice.value='';try{await action()}catch(e){error.value=e.message}finally{busy.value=false} }
function switchProject(event){ deletion.value='';targetOwner.value='';transferConfirmed.value=false;inviteRole.value='data_scientist';run(()=>refresh(event.target.value)) }
async function create(){await run(async()=>{const project=await props.api('/projects','POST',{name:name.value});name.value='';await refresh(project.id);view.value='studio';notice.value='Private project created. You are its Owner.'})}
async function invite(){await run(async()=>{await props.api(projectPath()+'/invitations','POST',{email:email.value,role:inviteRole.value});email.value='';await refresh();notice.value='Invitation created in the recipient’s InsightFlow inbox.'})}
async function respond(invitation,action){await run(async()=>{await props.api('/invitations/'+invitation.id+'/'+action,'POST');await refresh(action==='accept'?invitation.project_id:undefined);notice.value='Invitation '+(action==='accept'?'accepted.':'declined.');if(action==='accept')view.value='studio'})}
async function memberRole(member,event){const role=event.target.value;event.target.value=member.role;await run(async()=>{await props.api(projectPath()+'/members/'+member.id,'PATCH',{role});await refresh();notice.value='Project role updated.'})}
async function remove(member){if(!window.confirm(member.id===props.user.id?'Leave this project?':'Remove '+member.email+' from this project?'))return;await run(async()=>{await props.api(projectPath()+'/members/'+member.id,'DELETE');await refresh();notice.value='Membership removed.'})}
async function revoke(invitation){await run(async()=>{await props.api(projectPath()+'/invitations/'+invitation.id,'DELETE');await refresh();notice.value='Invitation revoked.'})}
async function transfer(){await run(async()=>{await props.api(projectPath()+'/transfer','POST',{profile_id:targetOwner.value});targetOwner.value='';transferConfirmed.value=false;await refresh();notice.value='Ownership transferred. You are now a Moderator.'})}
async function deleteProject(){await run(async()=>{await props.api(projectPath(),'DELETE',{confirmation:deletion.value});deletion.value='';await refresh();notice.value='Project deleted.'})}
function onFocus(){if(!busy.value)run(()=>refresh())}
onMounted(()=>{run(()=>refresh());window.addEventListener('focus',onFocus)})
onUnmounted(()=>{generation++;window.removeEventListener('focus',onFocus)})
</script>
<template>
  <div class="project-space">
    <header class="project-toolbar"><label>PROJECT<select :value="selected?.id || ''" :disabled="busy" @change="switchProject"><option v-if="!projects.length" value="">No projects yet</option><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }} · {{ roleNames[project.role] }}</option></select></label><div class="project-tabs"><button :class="{selected:view==='studio'}" @click="view='studio'">Workspace</button><button :class="{selected:view==='members'}" @click="view='members'">Project settings</button><button :class="{selected:view==='invitations'}" @click="view='invitations'">Invitations <span v-if="inbox.length">({{ inbox.length }})</span></button></div></header>
    <p v-if="error" role="alert" class="notice error project-message">{{ error }}</p><p v-if="notice" role="status" class="notice project-message">{{ notice }}</p>
    <p v-if="!ready" class="project-message">Loading your private projects…</p>
    <Workspace v-if="selected && selected.role!=='reviewer'" v-show="ready && view==='studio'" :key="selected.id" :project="selected"/>
    <template v-if="ready">
      <section v-if="view==='invitations'" class="settings-content"><h1>Your invitations</h1><p class="page-intro">Invitations for your verified email address. Accept to join a shared project.</p><p v-if="!inbox.length" class="empty-users">No pending invitations.</p><article v-for="item in inbox" :key="item.id" class="settings-panel"><h2>{{ item.name }}</h2><p class="panel-intro">Invited as {{ roleNames[item.role] }} · Expires {{ new Date(item.expires_at).toLocaleDateString() }}</p><div class="project-actions"><button :disabled="busy" @click="respond(item,'accept')">Accept invitation</button><button class="settings-action" :disabled="busy" @click="respond(item,'decline')">Decline</button></div></article></section>
      <template v-else-if="selected">
        <section v-if="view==='studio' && selected.role==='reviewer'" class="settings-content"><h1>{{ selected.name }}</h1><section class="settings-panel"><h2>Review workspace</h2><p class="panel-intro">You are a Reviewer in this project. Feedback and approval will be available when the dataset review workflow is implemented.</p></section></section>
        <section v-if="view==='members'" class="settings-content"><span class="eyebrow">PRIVATE PROJECT</span><h1>{{ selected.name }}</h1><p class="page-intro">Your role: {{ roleNames[selected.role] }}. Only accepted project members have access.</p>
          <section class="settings-panel"><h2>Members</h2><p class="panel-intro">Owners control the project. Moderators manage Data Scientists and Reviewers.</p><div class="table-scroll role-table"><table><thead><tr><th>Member</th><th>Project role</th><th>Access</th></tr></thead><tbody><tr v-for="person in members" :key="person.id"><td>{{ person.email }} <span v-if="person.id===user.id" class="primary-badge">You</span></td><td><select v-if="canManage && person.role!=='owner' && (owner || person.role!=='moderator')" :aria-label="'Project role for '+person.email" :value="person.role" :disabled="busy" @change="memberRole(person,$event)"><option v-if="owner" value="moderator">Moderator</option><option value="data_scientist">Data Scientist</option><option value="reviewer">Reviewer</option></select><span v-else>{{ roleNames[person.role] }}</span></td><td><button v-if="person.role!=='owner' && (person.id===user.id || (canManage && (owner || person.role!=='moderator')))" class="settings-action delete-action" :disabled="busy" @click="remove(person)">{{ person.id===user.id?'Leave project':'Remove' }}</button><span v-else>—</span></td></tr></tbody></table></div></section>
          <section v-if="canManage" class="settings-panel"><h2>Invite a collaborator</h2><p class="panel-intro">Invite by email. The recipient accepts from their InsightFlow Invitations page after signing in with that address. No email notification is sent yet.</p><form @submit.prevent="invite"><label>Email address<input v-model="email" type="email" required maxlength="254"></label><label>Project role<select v-model="inviteRole"><option value="data_scientist">Data Scientist</option><option value="reviewer">Reviewer</option><option v-if="owner" value="moderator">Moderator</option></select></label><button :disabled="busy">Create invitation</button></form><div v-if="sent.length" class="pending-invites"><h3>Pending invitations</h3><div v-for="item in sent" :key="item.id" class="invitation-row"><span>{{ item.email }} <small>{{ roleNames[item.role] }} · expires {{ new Date(item.expires_at).toLocaleDateString() }}</small></span><button v-if="owner || item.role!=='moderator'" class="settings-action" :disabled="busy" @click="revoke(item)">Revoke</button></div></div></section>
          <section v-if="owner" class="settings-panel"><h2>Transfer ownership</h2><p class="panel-intro">Give full control to an existing member. You will remain a Moderator.</p><form @submit.prevent="transfer"><label>New Owner<select v-model="targetOwner" required><option value="" disabled>Select a project member</option><option v-for="person in members.filter(m=>m.id!==user.id)" :key="person.id" :value="person.id">{{ person.email }}</option></select></label><label class="confirm-check"><input v-model="transferConfirmed" type="checkbox" required>I understand this member will control the project.</label><button :disabled="busy || !targetOwner || !transferConfirmed">Transfer ownership</button></form></section>
          <section v-if="owner" class="settings-section danger-zone"><h2>Danger zone</h2><div class="settings-section-body"><p class="panel-intro">Delete this project, its memberships and invitations permanently. This cannot be undone.</p><form @submit.prevent="deleteProject"><label>Type {{ selected.name }} to confirm<input v-model="deletion" autocomplete="off" required></label><button class="danger" :disabled="busy || deletion!==selected.name">Delete project</button></form></div></section>
        </section>
      </template>
      <section v-else-if="view!=='invitations'" class="settings-content"><h1>A space of your own</h1><p class="page-intro">Create a private project below, or accept an invitation to join someone else's.</p></section>
      <section class="new-project settings-content"><details><summary>Create another project</summary><form @submit.prevent="create"><label>Project name<input v-model="name" required maxlength="80" placeholder="e.g. Customer churn analysis"></label><button :disabled="busy || !name.trim()">Create private project</button></form></details></section>
    </template>
  </div>
</template>
