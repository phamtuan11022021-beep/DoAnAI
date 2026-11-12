<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from 'lucide-vue-next'

import {
  loginAccount,
  registerAccount,
} from '../services/auth'


const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  initialMode: {
    type: String,
    default: 'login',
  },
})

const emit = defineEmits([
  'update:modelValue',
  'authenticated',
])

const mode = ref(props.initialMode)
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)

const form = reactive({
  name: '',
  email: '',
  password: '',
  passwordConfirm: '',
})

const isRegister = computed(
  () => mode.value === 'register'
)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      mode.value = props.initialMode || 'login'
      error.value = ''
    }
  }
)

function close() {
  emit('update:modelValue', false)
}

function switchMode(nextMode) {
  mode.value = nextMode
  error.value = ''
}

async function submit() {
  error.value = ''
  loading.value = true

  try {
    const user = isRegister.value
      ? await registerAccount({
          name: form.name.trim(),
          email: form.email.trim(),
          password: form.password,
          passwordConfirm: form.passwordConfirm,
        })
      : await loginAccount({
          identifier: form.email.trim(),
          password: form.password,
        })

    emit('authenticated', user)
    close()
  } catch (err) {
    error.value = err.message || 'Không thể xác thực tài khoản.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    v-if="modelValue"
    class="modal-backdrop auth-backdrop"
    @click.self="close"
  >
    <section class="auth-modal">
      <div class="auth-visual">
        <div class="auth-brand-mark">
          <Sparkles :size="25" />
        </div>

        <span class="auth-eyebrow">
          UNICONNECT AI
        </span>

        <h2>
          Một tài khoản cho toàn bộ hành trình chọn trường.
        </h2>

        <p>
          Lưu hồ sơ tư vấn, bài viết, trường yêu thích và cá nhân hóa
          trải nghiệm UniConnect AI.
        </p>

        <div class="auth-proof">
          <span>
            <ShieldCheck :size="16" />
            Django Session Authentication
          </span>

          <span>
            <ShieldCheck :size="16" />
            CSRF Protection
          </span>
        </div>
      </div>

      <div class="auth-form-panel">
        <button
          class="icon-btn auth-close"
          @click="close"
        >
          <X :size="19" />
        </button>

        <div class="auth-tabs">
          <button
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            Đăng nhập
          </button>

          <button
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            Đăng ký
          </button>
        </div>

        <div class="auth-title">
          <span>
            {{ isRegister ? 'TẠO TÀI KHOẢN' : 'CHÀO MỪNG TRỞ LẠI' }}
          </span>

          <h3>
            {{ isRegister ? 'Bắt đầu với UniConnect AI' : 'Tiếp tục hành trình của bạn' }}
          </h3>
        </div>

        <form
          class="auth-form"
          @submit.prevent="submit"
        >
          <a v-if="!isRegister" href="/api/auth/password-reset/">Quên mật khẩu?</a>
          <label v-if="isRegister">
            <span>Họ và tên</span>

            <div class="auth-input">
              <UserRound :size="17" />

              <input
                v-model="form.name"
                required
                minlength="2"
                autocomplete="name"
                placeholder="Nguyễn Văn A"
              />
            </div>
          </label>

          <label>
            <span>{{ isRegister ? 'Email' : 'Email hoặc tên đăng nhập' }}</span>

            <div class="auth-input">
              <Mail :size="17" />

              <input
                v-model="form.email"
                required
                :type="isRegister ? 'email' : 'text'"
                :autocomplete="isRegister ? 'email' : 'username'"
                :placeholder="isRegister ? 'ban@example.com' : 'Email hoặc tên đăng nhập'"
              />
            </div>
          </label>

          <label>
            <span>Mật khẩu</span>

            <div class="auth-input">
              <LockKeyhole :size="17" />

              <input
                v-model="form.password"
                required
                :type="showPassword ? 'text' : 'password'"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                placeholder="••••••••"
              />

              <button
                type="button"
                class="password-toggle"
                @click="showPassword = !showPassword"
              >
                <EyeOff
                  v-if="showPassword"
                  :size="16"
                />

                <Eye
                  v-else
                  :size="16"
                />
              </button>
            </div>
          </label>

          <label v-if="isRegister">
            <span>Xác nhận mật khẩu</span>

            <div class="auth-input">
              <LockKeyhole :size="17" />

              <input
                v-model="form.passwordConfirm"
                required
                type="password"
                autocomplete="new-password"
                placeholder="Nhập lại mật khẩu"
              />
            </div>
          </label>

          <div
            v-if="error"
            class="auth-error"
          >
            {{ error }}
          </div>

          <button
            class="auth-submit"
            type="submit"
            :disabled="loading"
          >
            <span
              v-if="loading"
              class="spinner"
            ></span>

            <Sparkles
              v-else
              :size="17"
            />

            {{
              loading
                ? 'Đang xử lý...'
                : isRegister
                  ? 'Tạo tài khoản'
                  : 'Đăng nhập'
            }}
          </button>
        </form>

        <p class="auth-footer-copy">
          {{
            isRegister
              ? 'Đã có tài khoản?'
              : 'Chưa có tài khoản?'
          }}

          <button
            @click="switchMode(isRegister ? 'login' : 'register')"
          >
            {{
              isRegister
                ? 'Đăng nhập'
                : 'Đăng ký ngay'
            }}
          </button>
        </p>
      </div>
    </section>
  </div>
</template>
