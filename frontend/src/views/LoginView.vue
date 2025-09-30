<template>
  <div class="page">
    <div class="game-card">
      <header class="game-header">
        <div class="title-block">
          <h1>MAMA</h1>
        </div>
      </header>

      <div class="connection-card">
        <div class="field-group">
          <label>用户名</label>
          <input
            v-model="username"
            placeholder="请输入用户名"
            @keyup.enter="handleLogin"
          />
        </div>

        <div class="field-group">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </div>

        <div class="error-message" v-if="error">
          {{ error }}
        </div>

        <div class="action-group">
          <button
            class="primary"
            @click="handleLogin"
            :disabled="loading || !username || !password"
          >
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </div>

        <div class="helper-links">
          <router-link to="/rules" class="inline-link">查看番数规则</router-link>
        </div>

        <div class="help-text">
          <p>默认用户：</p>
          <p>用户名: A, 密码: A</p>
          <p>用户名: B, 密码: B</p>
          <p>用户名: C, 密码: C</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'

const router = useRouter()
const store = useGameStore()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    })

    const data = await response.json()

    if (response.ok && data.success && data.user && typeof data.token === 'string') {
      // 登录成功，同步用户信息到全局状态
      store.setUser(data.user)
      store.setAuthToken(data.token)
      // 跳转到游戏房间页面
      router.push('/join')
    } else {
      error.value = data.error || '登录失败'
    }
  } catch (err) {
    error.value = '网络错误，请稍后重试'
    console.error('Login error:', err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
:global(body) {
  margin: 0;
  background: radial-gradient(circle at top, #1c2540 0%, #0b1220 55%, #05070f 100%);
  min-height: 100vh;
  font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  color: #f1f4ff;
}

.page {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px 16px 64px;
  box-sizing: border-box;
}

.game-card {
  width: min(1100px, 100%);
  max-width: 500px;
  background: linear-gradient(145deg, rgba(18, 26, 48, 0.95), rgba(7, 12, 24, 0.92));
  border-radius: 28px;
  padding: 32px;
  box-shadow:
    0 40px 80px rgba(4, 8, 16, 0.65),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(90, 122, 191, 0.24);
  backdrop-filter: blur(12px);
}

.game-header {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 32px;
}

.title-block h1 {
  margin: 0;
  font-size: 2.4rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #f9fbff;
  text-shadow:
    0 0 18px rgba(82, 117, 255, 0.45),
    0 0 4px rgba(255, 255, 255, 0.2);
}

.connection-card {
  background: rgba(13, 20, 40, 0.9);
  border-radius: 22px;
  padding: 28px;
  border: 1px solid rgba(96, 128, 212, 0.32);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 24px 48px rgba(10, 14, 32, 0.55);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-group label {
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: #9db3ff;
}

.field-group input {
  background: rgba(10, 16, 30, 0.9);
  border: 1px solid rgba(92, 120, 205, 0.4);
  border-radius: 14px;
  padding: 14px;
  color: #f3f6ff;
  font-size: 1.02rem;
  transition: border-color 0.2s ease;
}

.field-group input:focus {
  outline: none;
  border-color: rgba(119, 149, 255, 0.9);
  box-shadow: 0 0 0 2px rgba(82, 117, 255, 0.25);
}

.error-message {
  color: #ff6c6c;
  background: rgba(255, 108, 108, 0.1);
  border: 1px solid rgba(255, 108, 108, 0.3);
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 0.95rem;
}

.action-group {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}

.helper-links {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.inline-link {
  color: #9db3ff;
  text-decoration: none;
  font-size: 0.9rem;
}

.inline-link:hover {
  text-decoration: underline;
}

button {
  border-radius: 14px;
  padding: 14px 28px;
  font-size: 1rem;
  letter-spacing: 0.04em;
  border: none;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  background: rgba(17, 30, 58, 0.85);
  color: #dce7ff;
  border: 1px solid rgba(101, 131, 213, 0.4);
  flex: 1;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

button:not(:disabled):hover {
  transform: translateY(-2px);
}

.primary {
  background: linear-gradient(135deg, #4f9aff, #5270ff);
  color: #fff;
  box-shadow: 0 12px 24px rgba(82, 112, 255, 0.35);
}

.primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 16px 28px rgba(82, 112, 255, 0.45);
}

.help-text {
  background: rgba(13, 20, 40, 0.7);
  border: 1px solid rgba(96, 128, 212, 0.2);
  border-radius: 16px;
  padding: 20px;
  margin-top: 8px;
}

.help-text p {
  margin: 8px 0;
  color: #b9c9ff;
  font-size: 0.9rem;
  line-height: 1.5;
}

.help-text p:first-child {
  font-weight: 600;
  color: #9db3ff;
  margin-bottom: 12px;
  letter-spacing: 0.05em;
}

@media (max-width: 768px) {
  .game-card {
    padding: 24px;
    margin: 16px;
  }

  .title-block h1 {
    font-size: 2rem;
  }

  .connection-card {
    padding: 20px;
  }

  .action-group {
    flex-direction: column;
  }

  button {
    width: 100%;
  }
}
</style>
