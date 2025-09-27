<template>
  <GameLayout>
    <section class="connection-card">
      <div class="field-group">
        <label>昵称</label>
        <input :value="displayUsername" disabled />
      </div>
      <div class="field-group">
        <label>房间号</label>
        <input v-model="roomId" placeholder="room1" />
      </div>
      <div class="action-group">
        <button
          :class="joinButtonClasses"
          @click="joinAndReady"
          :disabled="joinButtonDisabled"
        >
          {{ joinButtonLabel }}
        </button>
        <button
          v-if="canAccessAiPractice"
          :class="practiceButtonClasses"
          @click="playWithAi"
          :disabled="practiceButtonDisabled"
        >
          AI练习
        </button>
      </div>
    </section>
  </GameLayout>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import GameLayout from '../components/GameLayout.vue'
import { useGameStore } from '../stores/game'

const router = useRouter()
const store = useGameStore()


const {
  displayUsername,
  roomId,
  connected,
  isReady,
  joinAndReady,
  playWithAi,
  ws,
  gameInProgress,
  gameResult,
  canAccessAiPractice,
} = store


const joinButtonLabel = computed(() => {
  if (isReady.value) return '准备就绪'
  if (!connected.value) {
    return ws.value ? '连接中…' : '加入房间'
  }
  return '加入房间'
})

const joinButtonDisabled = computed(() => {
  if (isReady.value) return true
  if (!connected.value && ws.value) return true
  return false
})

const joinButtonClasses = computed(() => ({
  'ready-button': true,
  ready: isReady.value,
  connecting: !connected.value && Boolean(ws.value),
}))

const practiceButtonDisabled = computed(() => {
  if (!canAccessAiPractice.value) return true
  if (gameInProgress.value) return true
  if (isReady.value) return true
  if (!connected.value && Boolean(ws.value)) return true
  return false
})

const practiceButtonClasses = computed(() => ({
  'ready-button': true,
  connecting: !connected.value && Boolean(ws.value),
}))

watch(
  gameInProgress,
  (inProgress) => {
    if (!inProgress) return
    if (router.currentRoute.value.name === 'game') return
    router.replace({ name: 'game' })
  },
  { immediate: true }
)

watch(
  gameResult,
  (result) => {
    if (!result) return
    if (router.currentRoute.value.name === 'victory') return
    router.replace({ name: 'victory' })
  },
  { immediate: true }
)
</script>

<style scoped>
.connection-card {
  max-width: 900px;
  margin: 0 auto;
}

.action-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 当有两个按钮时，横向排列 */
.action-group:has(> button + button) {
  flex-direction: row;
  gap: 16px;
  justify-content: space-between;
}

.action-group > button {
  width: 100%;
  max-width: none;
}

/* 两个按钮时左右分布 */
.action-group:has(> button + button) > button {
  flex: 1 1 0;
  max-width: 48%;
  width: auto;
}

.user-info {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid #667eea;
}

.user-detail {
  flex: 1;
}

.user-detail label {
  display: block;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 5px;
}

.user-detail span {
  font-size: 18px;
  color: #667eea;
  font-weight: 500;
}

.logout-button {
  background: #e74c3c;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s ease;
}

.logout-button:hover {
  background: #c0392b;
  transform: translateY(-1px);
}

.logout-button:active {
  transform: translateY(0);
}
</style>
