<template>
  <GameLayout>
    <section v-if="gameResult" class="victory-card">
      <div class="victory-header">
        <h2>{{ winnerName }}</h2>
        <p class="reason">{{ reasonDescription }}</p>
      </div>

      <div class="result-grid">
        <div class="result-item">
          <span class="item-label">我方座位</span>
          <span class="item-value">{{ seat ?? '未知' }}</span>
        </div>
        <div class="result-item">
          <span class="item-label">对手昵称</span>
          <span class="item-value">{{ opponent || '未知' }}</span>
        </div>
        <div class="result-item">
          <span class="item-label">胜负判定</span>
          <span class="item-value">{{ resultSummary }}</span>
        </div>
      </div>

      <details class="raw-details">
        <summary>查看原始结算数据</summary>
        <pre>{{ prettyResult }}</pre>
      </details>

      <div class="victory-actions">
        <button class="primary" @click="backToJoin">返回准备</button>
        <button class="secondary" :disabled="!connected" @click="ready">
          再来一局
        </button>
      </div>
    </section>

    <section v-else class="victory-card empty">
      <p>暂无对局结果，返回准备页面等待开局。</p>
      <button class="primary" @click="backToJoin">返回准备</button>
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
  gameResult,
  seat,
  opponent,
  nickname,
  t2s,
  ready,
  connected,
  gameInProgress,
} = store

const prettyResult = computed(() => (gameResult.value ? JSON.stringify(gameResult.value, null, 2) : ''))

const winnerName = computed(() => {
  if (!gameResult.value) return '胜利结算'
  if (gameResult.value.winner === seat.value) {
    return `${nickname.value || '我方'} 获胜！`
  }
  return `${opponent.value || '对手'} 获胜`
})

const reasonDescription = computed(() => {
  const result = gameResult.value
  if (!result) return '等待新对局'
  if (result.reason === 'zimo') return '自摸胡牌'
  if (result.reason === 'ron') {
    const tileText = typeof result.tile === 'number' ? t2s(result.tile) : '未知牌'
    return `荣和 ${tileText}`
  }
  return result.reason || '未知原因'
})

const resultSummary = computed(() => {
  const result = gameResult.value
  if (!result) return '暂无'
  const seatText = typeof result.winner === 'number' ? `座位 ${result.winner}` : '未知座位'
  return `${seatText} · ${reasonDescription.value}`
})

watch(
  gameResult,
  (result) => {
    if (result) return
    router.replace({ name: 'join' })
  },
  { immediate: true }
)

watch(
  gameInProgress,
  (inProgress) => {
    if (!inProgress) return
    router.replace({ name: 'game' })
  },
  { immediate: true }
)

watch(
  connected,
  (isConnected) => {
    if (isConnected) return
    router.replace({ name: 'join' })
  },
  { immediate: true }
)

function backToJoin() {
  router.replace({ name: 'join' })
}
</script>

<style scoped>
.victory-card {
  margin-top: 32px;
  padding: 28px 32px;
  background: rgba(17, 26, 46, 0.92);
  border-radius: 22px;
  border: 1px solid rgba(118, 155, 255, 0.32);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 30px 60px rgba(8, 12, 28, 0.45);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.victory-card.empty {
  align-items: center;
  text-align: center;
}

.victory-header h2 {
  margin: 0 0 8px;
  font-size: 2rem;
  letter-spacing: 0.08em;
  color: #fdfdff;
}

.reason {
  margin: 0;
  color: #9fb8ff;
  letter-spacing: 0.05em;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.result-item {
  background: rgba(10, 17, 33, 0.92);
  border: 1px solid rgba(102, 134, 220, 0.28);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.item-label {
  color: #8da6ff;
  font-size: 0.9rem;
  letter-spacing: 0.06em;
}

.item-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: #e6ecff;
}

.raw-details summary {
  cursor: pointer;
  color: #8ea7ff;
}

.raw-details pre {
  background: rgba(6, 10, 22, 0.85);
  border-radius: 14px;
  padding: 16px;
  border: 1px solid rgba(90, 122, 191, 0.28);
  color: #dce4ff;
  overflow: auto;
  font-size: 0.9rem;
}

.victory-actions {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.victory-actions button {
  min-width: 140px;
}

@media (max-width: 600px) {
  .victory-card {
    padding: 24px;
  }

  .victory-actions {
    flex-direction: column;
  }

  .victory-actions button {
    width: 100%;
  }
}
</style>
