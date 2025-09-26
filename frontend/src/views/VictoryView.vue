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

      <FanSummary
        v-if="displayFanSummary"
        :summary="displayFanSummary"
        :seat="seat"
        :nickname="nickname"
        :opponent="opponent"
        title="积分结算"
      />

      <div v-if="hasFinalHands" class="final-hands">
        <section class="hand-section">
          <header class="hand-header">
            <h3>我的手牌</h3>
            <small>{{ finalHandSelf.length }} 张</small>
          </header>
          <div class="hand-tiles">
            <span
              v-for="(entry, i) in annotatedHandSelf"
              :key="`fs${i}`"
              :class="['tile', 'tile-final', { winning: entry.winning }]"
              :title="t2s(entry.tile)"
            >
              <img :src="tileImage(entry.tile)" :alt="t2s(entry.tile)" class="tile-face" />
            </span>
            <span v-if="!finalHandSelf.length" class="muted">暂无</span>
          </div>
          <div class="melds-block">
            <div class="melds-header">明面子</div>
            <div class="melds-list" v-if="finalMeldsSelf.length">
              <div
                v-for="(m, i) in finalMeldsSelf"
                :key="`fms${i}`"
                :class="['meld-card', meldKindClass(m.kind), 'self']"
              >
                <span class="meld-kind">{{ kindText(m.kind) }}</span>
                <div class="meld-tiles">
                  <span
                    v-for="(t, j) in m.tiles"
                    :key="`fms-${i}-${j}`"
                    class="tile tile-small meld-tile"
                    :title="t2s(t)"
                  >
                    <img :src="tileImage(t)" :alt="t2s(t)" class="tile-face" />
                  </span>
                </div>
              </div>
            </div>
            <span v-else class="muted">暂无</span>
          </div>
        </section>
        <section class="hand-section">
          <header class="hand-header">
            <h3>对手手牌</h3>
            <small>{{ finalHandOpp.length }} 张</small>
          </header>
          <div class="hand-tiles">
            <span
              v-for="(entry, i) in annotatedHandOpp"
              :key="`fo${i}`"
              :class="['tile', 'tile-final', { winning: entry.winning }]"
              :title="t2s(entry.tile)"
            >
              <img :src="tileImage(entry.tile)" :alt="t2s(entry.tile)" class="tile-face" />
            </span>
            <span v-if="!finalHandOpp.length" class="muted">暂无</span>
          </div>
          <div class="melds-block">
            <div class="melds-header">对手明面子</div>
            <div class="melds-list" v-if="finalMeldsOpp.length">
              <div
                v-for="(m, i) in finalMeldsOpp"
                :key="`fmo${i}`"
                :class="['meld-card', meldKindClass(m.kind)]"
              >
                <span class="meld-kind">{{ kindText(m.kind) }}</span>
                <div class="meld-tiles">
                  <span
                    v-for="(t, j) in m.tiles"
                    :key="`fmo-${i}-${j}`"
                    class="tile tile-small meld-tile"
                    :title="t2s(t)"
                  >
                    <img :src="tileImage(t)" :alt="t2s(t)" class="tile-face" />
                  </span>
                </div>
              </div>
            </div>
            <span v-else class="muted">暂无</span>
          </div>
        </section>
      </div>
      <p v-else class="final-hands-hint">暂无手牌结算信息，等待下一局。</p>

      <div class="victory-actions">
        <button class="primary" :disabled="!connected" @click="ready">
          再来一局
        </button>
        <button class="secondary" @click="backToJoin">返回准备</button>
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
import FanSummary from '../components/FanSummary.vue'
import { useGameStore } from '../stores/game'

const router = useRouter()
const store = useGameStore()

const {
  gameResult,
  seat,
  opponent,
  nickname,
  t2s,
  tileImage,
  finalHandSelf,
  finalHandOpp,
  finalMeldsSelf,
  finalMeldsOpp,
  meldKindClass,
  kindText,
  ready,
  connected,
  gameInProgress,
  liveFanSummary,
} = store


const winnerName = computed(() => {
  if (!gameResult.value) return '胜利结算'
  if (gameResult.value.reason === 'abort') {
    return '对局已中止'
  }
  const winner = gameResult.value.winner
  if (typeof winner !== 'number') {
    return '本局流局'
  }
  if (winner === seat.value) {
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
  if (result.reason === 'wall') return '牌墙摸尽（流局）'
  if (result.reason === 'abort') {
    const seatValue = seat.value
    const oppSeatId = seatValue === null ? null : 1 - seatValue
    if (typeof result.by === 'number') {
      if (seatValue !== null && result.by === seatValue) {
        return `${nickname.value || '我方'} 主动结束对局`
      }
      if (oppSeatId !== null && result.by === oppSeatId) {
        return `${opponent.value || '对手'} 主动结束对局`
      }
      return `座位 ${result.by} 主动结束对局`
    }
    return '对局被提前结束'
  }
  return result.reason || '未知原因'
})

const resultSummary = computed(() => {
  const result = gameResult.value
  if (!result) return '暂无'
  if (result.reason === 'abort') {
    const seatValue = seat.value
    const oppSeatId = seatValue === null ? null : 1 - seatValue
    if (typeof result.by === 'number') {
      if (seatValue !== null && result.by === seatValue) {
        return '对局中止 · 我方主动结束'
      }
      if (oppSeatId !== null && result.by === oppSeatId) {
        return '对局中止 · 对手主动结束'
      }
      return `对局中止 · 座位 ${result.by} 主动结束`
    }
    return '对局中止'
  }
  if (typeof result.winner !== 'number') {
    return `流局 · ${reasonDescription.value}`
  }
  const seatText = `座位 ${result.winner}`
  return `${seatText} · ${reasonDescription.value}`
})

const hasFinalHands = computed(() => finalHandSelf.value.length > 0 || finalHandOpp.value.length > 0)

const winningSeat = computed(() => {
  const winner = gameResult.value?.winner
  return typeof winner === 'number' ? winner : null
})

const winningTile = computed(() => {
  const result = gameResult.value
  if (!result) return null
  if (typeof result.tile === 'number') return result.tile
  return null
})

function annotateHand(tiles: number[], seatId: number | null): Array<{ tile: number; winning: boolean }> {
  if (!tiles.length) return []
  const tile = winningTile.value
  const targetSeat = winningSeat.value
  let remainingHighlights = tile !== null && seatId !== null && targetSeat === seatId ? 1 : 0
  return tiles.map((value) => {
    const shouldHighlight = remainingHighlights > 0 && tile === value
    if (shouldHighlight) {
      remainingHighlights -= 1
    }
    return { tile: value, winning: shouldHighlight }
  })
}

const opponentSeat = computed(() => (seat.value === null ? null : 1 - seat.value))

const annotatedHandSelf = computed(() => annotateHand(finalHandSelf.value, seat.value))
const annotatedHandOpp = computed(() => annotateHand(finalHandOpp.value, opponentSeat.value))

const scoreFromResult = computed(() => gameResult.value?.score ?? null)
const displayFanSummary = computed(() => scoreFromResult.value ?? liveFanSummary.value)

watch(
  gameResult,
  (result) => {
    if (result) return
    if (router.currentRoute.value.name === 'join') return
    router.replace({ name: 'join' })
  },
  { immediate: true }
)

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
  connected,
  (isConnected) => {
    if (isConnected) return
    if (router.currentRoute.value.name === 'join') return
    router.replace({ name: 'join' })
  },
  { immediate: true }
)

function backToJoin() {

  // Check if we're already on the join page
  if (router.currentRoute.value.name === 'join') {
    return
  }

  try {
    // Clear game result to prevent automatic re-navigation
    gameResult.value = null
    // Force navigation to join page
    router.replace({ name: 'join' }).catch((error) => {
      console.error('Navigation error:', error)
      // If navigation fails, try push instead
      router.push({ name: 'join' }).catch((e) => {
        console.error('Push navigation also failed:', e)
      })
    })
  } catch (error) {
    console.error('Error in backToJoin navigation:', error)
  }
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

.final-hands {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 18px;
}

.hand-section {
  background: rgba(8, 14, 29, 0.9);
  border: 1px solid rgba(96, 126, 216, 0.28);
  border-radius: 18px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hand-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  color: #dde5ff;
}

.hand-header h3 {
  margin: 0;
  font-size: 1.05rem;
  letter-spacing: 0.05em;
}

.hand-header small {
  color: #93a8ff;
}

.hand-tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 72px;
}

.tile-final {
  width: 52px;
  height: 76px;
  border-radius: 12px;
  background: linear-gradient(150deg, rgba(20, 30, 58, 0.95), rgba(10, 15, 32, 0.95));
  border: 1px solid rgba(96, 126, 216, 0.35);
  box-shadow:
    0 10px 20px rgba(5, 10, 20, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
}

.tile-final.winning {
  border-color: rgba(255, 210, 92, 0.9);
  box-shadow:
    0 12px 24px rgba(255, 210, 92, 0.45),
    0 0 18px rgba(255, 194, 68, 0.75);
}

.tile-face {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.final-hands-hint {
  margin: 0;
  color: #7d8fc4;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
}

.melds-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.melds-header {
  font-size: 0.95rem;
  color: #9bb3ff;
  letter-spacing: 0.04em;
}

.melds-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.meld-card {
  background: rgba(12, 21, 43, 0.9);
  border-radius: 16px;
  padding: 12px 14px;
  border: 1px solid rgba(94, 126, 212, 0.35);
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 150px;
}

.meld-card.self {
  border-color: rgba(146, 181, 255, 0.55);
}

.meld-kind {
  font-size: 0.9rem;
  color: #d1deff;
}

.meld-tiles {
  display: flex;
  gap: 8px;
}

.meld-tile {
  width: 42px;
  height: 62px;
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(24, 34, 62, 0.95), rgba(11, 16, 32, 0.95));
  border: 1px solid rgba(96, 126, 216, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
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
