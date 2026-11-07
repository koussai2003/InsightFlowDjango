<script setup>
defineProps({ role: String })
</script>
<template>
  <section class="settings-page"><header class="page-header"><div><span class="eyebrow">YOUR WORKSPACE</span><h1>{{ role === 'administrator' ? 'Administration' : 'Review workspace' }}</h1></div><span class="status-pill">{{ role === 'administrator' ? 'Administrator' : 'Reviewer' }}</span></header>
    <div class="settings-content"><section class="settings-panel"><template v-if="role === 'administrator'"><h2>Manage access to InsightFlow</h2><p class="panel-intro">Assign Data scientist, Reviewer, or Administrator access to verified accounts.</p><a class="settings-action role-link" href="#/team">Manage users & permissions →</a></template><template v-else><h2>Your review space</h2><p class="panel-intro">Your account has reviewer access. Dataset feedback and approval will be available when the review workflow is implemented.</p><p class="role-footnote">Data preparation and user administration are reserved for their respective roles.</p></template></section></div>
  </section>
</template>
