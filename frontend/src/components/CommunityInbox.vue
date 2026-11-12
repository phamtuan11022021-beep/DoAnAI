<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Bell, MessagesSquare, X, Send, ArrowLeft, CheckCheck, MessageCircle } from 'lucide-vue-next'
import { apiRequest } from '../services/social'
const props = defineProps({ user: Object, contacts: { type: Array, default: () => [] } })
const emit = defineEmits(['login', 'open-post'])
const panel = ref('')
const notices = ref([])
const unread = ref(0)
const messageUnread = ref(0)
const threads = ref([])
const selected = ref(null)
const messages = ref([])
const draft = ref('')
const error = ref('')
const busy = ref(false)
let timer
const candidates = computed(() => props.contacts.filter(c => c.id !== props.user?.id))
async function refresh() {
  if (!props.user) return
  try {
    const [n, m] = await Promise.all([apiRequest('/api/social/notifications/'), apiRequest('/api/social/inbox/')])
    notices.value = n.notifications; unread.value = n.unread
    threads.value = m.threads; messageUnread.value = m.unread
    if (panel.value === 'messages' && selected.value && !busy.value) {
      const data = await apiRequest(`/api/social/messages/${selected.value.id}/`)
      messages.value = data.messages
    }
  } catch (e) { if (panel.value) error.value = e.message }
}
watch(() => props.user?.id, () => {
  clearInterval(timer); panel.value = ''; selected.value = null
  notices.value = []; threads.value = []; unread.value = 0; messageUnread.value = 0
  if (props.user) { refresh(); timer = setInterval(refresh, 15000) }
}, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))
async function toggle(name) {
  if (!props.user) { emit('login'); return }
  panel.value = panel.value === name ? '' : name
  error.value = ''; await refresh()
}
async function readNotice(notice) {
  try {
    await apiRequest('/api/social/notifications/', { method: 'POST', body: { id: notice.id } })
    if (notice.post_id) { emit('open-post', notice.post_id); panel.value = '' }
    else { await openPerson({ id: notice.actor_id, name: notice.text.split(' đã ')[0] }) }
    await refresh()
  } catch (e) { error.value = e.message }
}
async function readAll() {
  try { await apiRequest('/api/social/notifications/', { method: 'POST', body: {} }); await refresh() }
  catch (e) { error.value = e.message }
}
async function openPerson(person) {
  panel.value = 'messages'; selected.value = person; error.value = ''; draft.value = ''; messages.value = []
  try {
    const data = await apiRequest(`/api/social/messages/${person.id}/`)
    selected.value = data.user; messages.value = data.messages
    await apiRequest(`/api/social/messages/${person.id}/read/`, { method: 'POST', body: {} })
    await refresh()
  } catch (e) { error.value = e.message }
}
async function send() {
  if (!draft.value.trim() || busy.value) return
  busy.value = true; error.value = ''
  try {
    const data = await apiRequest(`/api/social/messages/${selected.value.id}/`, {
      method: 'POST', body: { content: draft.value.trim() } })
    messages.value = data.messages; draft.value = ''; await refresh()
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
defineExpose({ openPerson })
</script>

<template>
  <div class="inbox-actions">
    <button class="icon-btn has-badge" aria-label="Thông báo" :aria-expanded="panel==='notifications'" @click="toggle('notifications')">
      <Bell :size="20"/><span v-if="unread" class="red-badge">{{ unread > 99 ? '99+' : unread }}</span>
    </button>
    <button class="icon-btn has-badge" aria-label="Tin nhắn" :aria-expanded="panel==='messages'" @click="toggle('messages')">
      <MessagesSquare :size="20"/><span v-if="messageUnread" class="blue-badge">{{ messageUnread }}</span>
    </button>
    <div v-if="panel" class="inbox-scrim" @click="panel=''"/>
    <section v-if="panel" class="community-inbox" aria-label="Hộp thư cộng đồng">
      <div class="inbox-head">
        <button v-if="selected && panel==='messages'" class="icon-btn" aria-label="Quay lại" @click="selected=null"><ArrowLeft :size="18"/></button>
        <h3>{{ panel==='notifications' ? 'Thông báo của bạn' : selected?.name || 'Tin nhắn' }}</h3>
        <button class="icon-btn" aria-label="Đóng hộp thư" @click="panel=''"><X :size="18"/></button>
      </div>
      <p v-if="error" role="alert" class="form-error">{{ error }}</p>
      <template v-if="panel==='notifications'">
        <button v-if="unread" class="ghost-btn" @click="readAll"><CheckCheck :size="15"/> Đánh dấu tất cả đã đọc</button>
        <p v-if="!notices.length" class="inbox-empty">Bạn chưa có thông báo mới. Tương tác với cộng đồng để bắt đầu nhé.</p>
        <button v-for="n in notices" :key="n.id" class="notice-item" :class="{unread:!n.read}" @click="readNotice(n)">
          <Bell :size="17"/><span>{{ n.text }}<small>{{ n.time }}</small></span><i v-if="!n.read"/>
        </button>
      </template>
      <template v-else-if="!selected">
        <p v-if="!threads.length" class="inbox-empty">Chưa có cuộc trò chuyện. Chọn một thành viên để nhắn tin.</p>
        <button v-for="t in threads" :key="t.user.id" class="thread-item" @click="openPerson(t.user)">
          <span class="avatar mini"><img v-if="t.user.avatar_url" :src="t.user.avatar_url" alt=""/><template v-else>{{ t.user.name.slice(0,2) }}</template></span>
          <span><b>{{ t.user.name }}</b><small>{{ t.content }}</small></span><strong v-if="t.unread" class="unread-count">{{ t.unread }}</strong>
        </button>
        <h4 class="inbox-caption">Bắt đầu trò chuyện</h4>
        <button v-for="c in candidates" :key="c.id" class="thread-item" @click="openPerson(c)"><MessageCircle :size="18"/><span>{{ c.name }}</span></button>
      </template>
      <template v-else>
        <div class="direct-messages">
          <p v-if="!messages.length" class="inbox-empty">Gửi lời chào và cùng chia sẻ kinh nghiệm chọn trường.</p>
          <div v-for="m in messages" :key="m.id" class="direct-message" :class="{mine:m.mine}"><p>{{ m.content }}</p><small>{{ m.time }}</small></div>
        </div>
        <form class="direct-compose" @submit.prevent="send">
          <input v-model="draft" maxlength="2000" placeholder="Nhập tin nhắn…" aria-label="Nội dung tin nhắn"/>
          <button class="send-btn" :disabled="busy || !draft.trim()" aria-label="Gửi tin nhắn"><Send :size="18"/></button>
        </form>
      </template>
    </section>
  </div>
</template>
