<script setup>
import { reactive, ref, watch } from 'vue'
import {
  GraduationCap,
  MapPin,
  Save,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
  X,
} from 'lucide-vue-next'

import {
  updateMyProfile,
  uploadAvatar,
} from '../services/auth'


const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  user: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits([
  'update:modelValue',
  'updated',
])

const loading = ref(false)
const error = ref('')
const success = ref('')
const avatarLoading = ref(false)
const avatarInput = ref(null)

async function changeAvatar(event) {
  const file = event.target.files?.[0]
  if (!file) return
  error.value = ''; success.value = ''
  if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 5*1024*1024) {
    error.value = 'Chọn ảnh JPG, PNG hoặc WebP, tối đa 5 MB.'
    event.target.value = ''; return
  }
  avatarLoading.value = true
  try {
    const updated = await uploadAvatar(file)
    emit('updated', updated)
    success.value = 'Đã cập nhật ảnh đại diện.'
  } catch (err) { error.value = err.message || 'Không tải được ảnh.' }
  finally { avatarLoading.value = false; event.target.value = '' }
}

const form = reactive({
  name: '',
  expected_score: '',
  target_combination: '',
  target_major: '',
  city: '',
  bio: '',
})

const combinations = [
  '',
  'A00',
  'A01',
  'B00',
  'C00',
  'D01',
  'D07',
]

watch(
  () => [props.modelValue, props.user],
  () => {
    if (!props.modelValue || !props.user) {
      return
    }

    form.name = props.user.name || ''
    form.expected_score = props.user.profile?.expected_score ?? ''
    form.target_combination = props.user.profile?.target_combination || ''
    form.target_major = props.user.profile?.target_major || ''
    form.city = props.user.profile?.city || ''
    form.bio = props.user.profile?.bio || ''

    error.value = ''
    success.value = ''
  },
  {
    immediate: true,
    deep: true,
  }
)

function close() {
  emit('update:modelValue', false)
}

async function save() {
  loading.value = true
  error.value = ''
  success.value = ''

  try {
    const user = await updateMyProfile({
      name: form.name.trim(),
      expected_score: form.expected_score === ''
        ? null
        : Number(form.expected_score),
      target_combination: form.target_combination,
      target_major: form.target_major.trim(),
      city: form.city.trim(),
      bio: form.bio.trim(),
    })

    emit('updated', user)
    success.value = 'Đã cập nhật hồ sơ.'
  } catch (err) {
    error.value = err.message || 'Không thể cập nhật hồ sơ.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    v-if="modelValue && user"
    class="modal-backdrop"
    @click.self="close"
  >
    <section class="profile-editor">
      <div class="profile-editor-head">
        <div>
          <span class="section-kicker">
            HỒ SƠ UNICONNECT
          </span>

          <h3>
            Cá nhân hóa tư vấn AI
          </h3>
        </div>

        <button
          class="icon-btn"
          @click="close"
        >
          <X :size="19" />
        </button>
      </div>

      <div class="profile-summary">
        <span class="profile-big-avatar">
          <img v-if="user.avatar_url" :src="user.avatar_url" alt="Ảnh đại diện"/>
          <template v-else>{{ (user.name || 'U').slice(0, 2).toUpperCase() }}</template>
        </span>

        <div>
          <strong>{{ user.name }}</strong>
          <small>{{ user.email }}</small>

          <span>
            <ShieldCheck :size="13" />
            {{ user.profile?.role === 'mentor' ? 'Mentor' : 'Thành viên UniConnect' }}
          </span>
        </div>
      </div>

      <div class="avatar-upload-row">
        <input ref="avatarInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="changeAvatar"/>
        <button class="soft-btn" :disabled="avatarLoading" @click="avatarInput.click()">{{ avatarLoading ? 'Đang tải ảnh…' : 'Đổi ảnh đại diện' }}</button>
        <small>JPG, PNG hoặc WebP · tối đa 5 MB</small>
      </div>
      <div class="profile-form-grid">
        <label class="full">
          <span>Họ và tên</span>

          <div class="auth-input">
            <UserRound :size="17" />
            <input v-model="form.name" />
          </div>
        </label>

        <label>
          <span>Điểm dự kiến</span>

          <div class="auth-input">
            <Target :size="17" />

            <input
              v-model="form.expected_score"
              type="number"
              min="0"
              max="30"
              step="0.25"
            />
          </div>
        </label>

        <label>
          <span>Tổ hợp mục tiêu</span>

          <div class="auth-input">
            <GraduationCap :size="17" />

            <select v-model="form.target_combination">
              <option
                v-for="item in combinations"
                :key="item"
                :value="item"
              >
                {{ item || 'Chưa chọn' }}
              </option>
            </select>
          </div>
        </label>

        <label class="full">
          <span>Ngành mục tiêu</span>

          <div class="auth-input">
            <GraduationCap :size="17" />

            <input
              v-model="form.target_major"
              placeholder="Công nghệ thông tin"
            />
          </div>
        </label>

        <label class="full">
          <span>Tỉnh / Thành mong muốn</span>

          <div class="auth-input">
            <MapPin :size="17" />

            <input
              v-model="form.city"
              placeholder="Đà Nẵng"
            />
          </div>
        </label>

        <label class="full">
          <span>Giới thiệu ngắn</span>

          <textarea
            v-model="form.bio"
            maxlength="300"
            rows="4"
            placeholder="Mục tiêu học tập, sở thích ngành nghề..."
          ></textarea>
        </label>
      </div>

      <div
        v-if="error"
        class="auth-error"
      >
        {{ error }}
      </div>

      <div
        v-if="success"
        class="profile-success"
      >
        <Sparkles :size="15" />
        {{ success }}
      </div>

      <button
        class="auth-submit"
        :disabled="loading"
        @click="save"
      >
        <span
          v-if="loading"
          class="spinner"
        ></span>

        <Save
          v-else
          :size="17"
        />

        {{ loading ? 'Đang lưu...' : 'Lưu hồ sơ' }}
      </button>
    </section>
  </div>
</template>
