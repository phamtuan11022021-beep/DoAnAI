<script setup>
import { ref } from 'vue'
import { Search, ArrowUpRight } from 'lucide-vue-next'
const emit = defineEmits(['search'])
const query = ref('')
function submit() { emit('search', query.value.trim()) }
</script>

<template>
  <section class="campus-hero" aria-label="Cùng bạn tìm trường, chọn ngành">
    <img class="campus-photo" src="/images/campus-students-hero.webp" alt="Nhóm sinh viên cùng trao đổi bên máy tính trong khuôn viên trường" fetchpriority="high"/>
    <div class="campus-shade"/>
    <div class="campus-hero-copy">
      <span class="campus-eyebrow">CÙNG BẠN CHỌN HƯỚNG TƯƠNG LAI</span>
      <h1>Tìm trường, chọn ngành<br/>với thông tin thật<br/>và <em>trải nghiệm thật.</em></h1>
      <p>Hiểu mình hơn, lắng nghe người đi trước.<br/>Từng bước tìm nơi phù hợp với bạn.</p>
    </div>
    <span class="campus-handnote" aria-hidden="true">
      <span>Mỗi hành trình</span>
      <span>bắt đầu từ bạn</span>
      <ArrowUpRight :size="25"/>
    </span>
    <form class="campus-search" @submit.prevent="submit">
      <Search :size="19" aria-hidden="true"/>
      <input v-model="query" aria-label="Ngành hoặc trường bạn quan tâm" placeholder="Bạn đang quan tâm ngành nào? Ví dụ: Công nghệ thông tin…"/>
      <button type="submit"><Search :size="16"/><span>Tìm kiếm</span></button>
    </form>
  </section>
</template>
