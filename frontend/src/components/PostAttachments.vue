<script setup>
import { ref } from 'vue'
import { apiRequest } from '../services/social'
const props = defineProps({ post: Object, user: Object })
const emit = defineEmits(['login'])
const error = ref(''), busy = ref(false), enlarged = ref('')
async function vote(index) {
  if (!props.user) { emit('login'); return }
  busy.value = true; error.value = ''
  try {
    const data = await apiRequest(`/api/social/posts/${props.post.id}/vote/`, { method: 'POST', body: { option: index } })
    props.post.poll = data.poll
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <div v-if="post.images?.length" class="post-gallery" :class="{single:post.images.length===1}">
    <button v-for="image in post.images" :key="image.id" @click="enlarged=image.url"><img :src="image.url" alt="Ảnh đính kèm bài viết" loading="lazy"/></button>
  </div>
  <div v-if="post.poll" class="post-poll">
    <button v-for="(option,index) in post.poll.options" :key="index" :class="{selected:post.poll.my_vote===index}" :disabled="busy" @click="vote(index)">
      <span class="poll-fill" :style="{width:`${post.poll.total ? option.votes/post.poll.total*100 : 0}%`}"/>
      <span>{{ option.text }} {{ post.poll.my_vote===index ? '✓' : '' }}</span><b>{{ option.votes }} phiếu</b>
    </button>
    <small>{{ post.poll.total }} lượt bình chọn · Mỗi người một lựa chọn, có thể đổi phiếu</small>
    <p v-if="error" class="form-error">{{ error }}</p>
  </div>
  <Teleport to="body"><div v-if="enlarged" class="image-lightbox" @click="enlarged=''" role="dialog" aria-label="Xem ảnh"><button aria-label="Đóng ảnh" @click="enlarged=''">Đóng ×</button><img :src="enlarged" alt="Ảnh bài viết phóng lớn"/></div></Teleport>
</template>
