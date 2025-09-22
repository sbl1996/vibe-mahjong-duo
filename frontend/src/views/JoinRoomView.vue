<template>
  <GameLayout>
    <section class="connection-card">
      <div class="field-group">
        <label>昵称</label>
        <input v-model="nickname" placeholder="请输入昵称" />
      </div>
      <div class="field-group">
        <label>房间号</label>
        <input v-model="roomId" placeholder="room1" />
      </div>
      <div class="action-group">
        <button class="primary" @click="connect" :disabled="connected">
          {{ connected ? '已连接' : '连接房间' }}
        </button>
        <button
          class="ready-button"
          :class="{ ready: isReady }"
          @click="ready"
          :disabled="!connected || isReady"
        >
          {{ isReady ? '准备就绪' : '点击准备' }}
        </button>
      </div>
    </section>
  </GameLayout>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { useRouter } from 'vue-router'
import GameLayout from '../components/GameLayout.vue'
import { useGameStore } from '../stores/game'

const router = useRouter()
const store = useGameStore()

const { nickname, roomId, connected, isReady, connect, ready, gameInProgress, gameResult } = store

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
