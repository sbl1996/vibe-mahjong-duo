<template>
  <GameLayout>
    <div v-if="connected" class="board">
      <FanSummary
        class="board-fan-summary"
        :summary="liveFanSummary"
        :seat="seat"
        :nickname="displayNickname"
        :opponent="displayOpponent"
        title="当前番数"
        dense
      />
      <section class="panel panel-opp">
        <header class="panel-head">
          <h3>对手桌面</h3>
          <small v-if="displayOpponent">{{ displayOpponent }}</small>
        </header>
        <div class="panel-body">
          <div class="info-row hand-row">
            <span class="label">手牌</span>
            <div class="hand-area">
              <div class="hand hand-opponent">
                <div
                  v-for="(_, i) in oppHandPlaceholders"
                  :key="`oh${i}`"
                  class="tile tile-hidden"
                  aria-hidden="true"
                >
                  <img :src="tileBackImage" alt="" class="tile-face" />
                </div>
                <span v-if="!oppHandPlaceholders.length" class="muted">等待同步</span>
              </div>
            </div>
          </div>
          <div class="info-row">
            <span class="label">明面子</span>
            <div class="value melds-value" v-if="meldsOpp.length">
              <div
                v-for="(m, i) in meldsOpp"
                :key="`mo${i}`"
                :class="['meld-card', meldKindClass(m.kind)]"
              >
                <span class="meld-kind">{{ kindText(m.kind) }}</span>
                <div class="meld-tiles">
                  <span
                    v-for="(t, j) in m.tiles"
                    :key="`mot${i}-${j}`"
                    :class="['tile', 'tile-small', 'meld-tile', { 'tile-hidden': t === null }]"
                    :title="t === null ? '' : t2s(t)"
                    :aria-hidden="t === null ? 'true' : undefined"
                  >
                    <img
                      :src="t === null ? tileBackImage : tileImage(t)"
                      :alt="t === null ? '' : t2s(t)"
                      class="tile-face"
                    />
                  </span>
                </div>
              </div>
            </div>
            <span class="value" v-else>暂无</span>
          </div>
          <div class="info-row">
            <span class="label">弃牌河</span>
            <span class="value tile-row">
              <span
                v-for="(t, i) in discOpp"
                :key="`do${i}`"
                class="tile tile-small"
                :title="t2s(t)"
              >
                <img :src="tileImage(t)" :alt="t2s(t)" class="tile-face" />
              </span>
              <span v-if="!discOpp.length" class="muted">暂无</span>
            </span>
          </div>
        </div>
      </section>

      <section class="panel panel-self">
        <header class="panel-head">
          <h3>我的桌面</h3>
          <small v-if="displayNickname">{{ displayNickname }}</small>
        </header>
        <div class="panel-body">
          <div class="info-row hand-row">
            <span class="label">手牌</span>
            <div class="hand-area">
              <div class="hand">
                <button
                  v-for="(t, i) in hand"
                  :key="`h${i}`"
                  :class="['tile', { selected: selectedHandIndex === i, drawn: lastDrawnIndex === i }]"
                  @click="selectTile(i)"
                  :aria-label="t2s(t)"
                >
                  <img :src="tileImage(t)" :alt="t2s(t)" class="tile-face" />
                </button>
                <span v-if="!hand.length" class="muted">等待同步</span>
              </div>
            </div>
          </div>
          <div class="info-row">
            <span class="label">明面子</span>
            <div class="value melds-value" v-if="meldsSelf.length">
              <div
                v-for="(m, i) in meldsSelf"
                :key="`ms${i}`"
                :class="['meld-card', meldKindClass(m.kind), 'self']"
              >
                <span class="meld-kind">{{ kindText(m.kind) }}</span>
                <div class="meld-tiles">
                  <span
                    v-for="(t, j) in m.tiles"
                    :key="`mst${i}-${j}`"
                    :class="['tile', 'tile-small', 'meld-tile', { 'tile-hidden': t === null }]"
                    :title="t === null ? '' : t2s(t)"
                    :aria-hidden="t === null ? 'true' : undefined"
                  >
                    <img
                      :src="t === null ? tileBackImage : tileImage(t)"
                      :alt="t === null ? '' : t2s(t)"
                      class="tile-face"
                    />
                  </span>
                </div>
              </div>
            </div>
            <span class="value" v-else>暂无</span>
          </div>
          <div class="info-row">
            <span class="label">弃牌河</span>
            <span class="value tile-row">
              <span
                v-for="(t, i) in discSelf"
                :key="`ds${i}`"
                class="tile tile-small"
                :title="t2s(t)"
              >
                <img :src="tileImage(t)" :alt="t2s(t)" class="tile-face" />
              </span>
              <span v-if="!discSelf.length" class="muted">暂无</span>
            </span>
          </div>
        </div>
        <footer class="panel-foot" v-if="showActionFooter">
          <div v-if="canAccessAiHint" class="ai-hint-bar">
            <button
              class="ai-hint-button"
              :disabled="aiHintPending || !connected"
              @click="requestAiHint"
            >
              {{ aiHintPending ? 'AI提示分析中…' : aiHint ? '刷新AI提示' : '获取AI提示' }}
            </button>
            <span v-if="aiHintPending" class="ai-hint-status">AI正在分析当前局面…</span>
            <span v-else-if="aiHintError" class="ai-hint-status ai-hint-status--error">{{ aiHintError }}</span>
            <div v-else-if="aiHint" class="ai-hint-result">
              <span class="ai-hint-action">{{ aiHintActionText }}</span>
              <p v-if="aiHintReason" class="ai-hint-reason">{{ aiHintReason }}</p>
            </div>
          </div>
          <div class="actions">
            <div class="action-grid">
              <button
                v-if="discardActions.length"
                class="discard-action"
                :disabled="!canDiscardSelected"
                @click="confirmDiscard"
              >
                打出所选牌
              </button>
              <button v-for="(a, i) in visibleActions" :key="`ac${i}`" @click="doAction(a)">
                {{ actText(a) }}
              </button>
            </div>
          </div>
        </footer>
      </section>
    </div>

    <div v-else class="disconnected-hint">
      <p>连接已断开，返回加入页面重新进入房间。</p>
      <button class="primary" @click="goJoin">返回加入页面</button>
    </div>
  </GameLayout>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import GameLayout from '../components/GameLayout.vue'
import FanSummary from '../components/FanSummary.vue'
import { useGameStore } from '../stores/game'
import type { Action } from '../stores/game'

const router = useRouter()
const store = useGameStore()

const {
  connected,
  seat,
  displayOpponent,
  displayNickname,
  oppHandPlaceholders,
  tileBackImage,
  meldsOpp,
  kindText,
  meldKindClass,
  t2s,
  tileImage,
  discOpp,
  hand,
  selectedHandIndex,
  lastDrawnIndex,
  selectTile,
  meldsSelf,
  discSelf,
  showActionFooter,
  discardActions,
  canDiscardSelected,
  confirmDiscard,
  visibleActions,
  doAction,
  actText,
  canAccessAiHint,
  aiHint,
  aiHintPhase,
  aiHintPending,
  aiHintError,
  requestAiHint,
  gameInProgress,
  gameResult,
  liveFanSummary,
} = store

const aiHintAction = computed(() => {
  const hint = aiHint.value
  if (!hint) return null
  const payload: Action = { type: hint.action }
  if (typeof hint.tile === 'number') {
    payload.tile = hint.tile
  }
  if (hint.style) {
    payload.style = hint.style
  } else if (hint.action === 'hu') {
    payload.style = aiHintPhase.value === 'self_turn' ? 'self' : 'ron'
  }
  return payload
})

const aiHintActionText = computed(() => {
  const action = aiHintAction.value
  if (!action) return ''
  return actText(action)
})

const aiHintReason = computed(() => aiHint.value?.reason ?? '')

watch(
  gameInProgress,
  (inProgress) => {
    if (inProgress) return
    if (gameResult.value) {
      router.replace({ name: 'victory' })
    } else {
      router.replace({ name: 'join' })
    }
  },
  { immediate: true }
)

watch(gameResult, (result) => {
  if (!result) return
  if (router.currentRoute.value.name === 'victory') return
  router.replace({ name: 'victory' })
})

watch(connected, (isConnected) => {
  if (isConnected) return
  if (router.currentRoute.value.name === 'join') return
  router.replace({ name: 'join' })
})

function goJoin() {
  router.replace({ name: 'join' })
}
</script>

<style scoped>
.board {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-top: 24px;
}

.board-fan-summary {
  margin-bottom: 4px;
}

.panel {
  background: linear-gradient(155deg, rgba(27, 36, 63, 0.92), rgba(14, 21, 42, 0.92));
  border-radius: 22px;
  border: 1px solid rgba(107, 140, 245, 0.28);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 20px 22px 0;
  color: #e2e8ff;
}

.panel-head h3 {
  margin: 0;
  font-size: 1.15rem;
  letter-spacing: 0.05em;
}

.panel-head small {
  color: #90a6ff;
}

.panel-body {
  padding: 16px 22px 22px;
  flex: 1;
}

.panel-foot {
  border-top: 1px solid rgba(146, 171, 255, 0.18);
  padding: 16px 22px 22px;
  background: rgba(16, 24, 47, 0.82);
  border-radius: 0 0 22px 22px;
}

.ai-hint-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.ai-hint-button {
  align-self: flex-start;
  background: linear-gradient(140deg, #2e4bff, #5f8bff);
  border: none;
  color: #f3f6ff;
  font-weight: 600;
  padding: 10px 18px;
  border-radius: 12px;
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.ai-hint-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ai-hint-button:not(:disabled):hover {
  transform: translateY(-1px);
}

.ai-hint-status {
  font-size: 0.92rem;
  color: #93a4d8;
}

.ai-hint-status--error {
  color: #ff9a9a;
}

.ai-hint-result {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(19, 30, 63, 0.65);
  border: 1px solid rgba(102, 153, 255, 0.35);
  border-radius: 14px;
  padding: 10px 14px;
}

.ai-hint-action {
  font-weight: 700;
  color: #d5e2ff;
  letter-spacing: 0.03em;
}

.ai-hint-reason {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.45;
  color: #aebcf5;
}

.panel-self .hand {
  width: 100%;
}

.info-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 14px;
}

.label {
  flex: 0 0 64px;
  font-weight: 700;
  color: #9db6ff;
  letter-spacing: 0.04em;
}

.value {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hand {
  --hand-tile-gap: 8px;
  --hand-scroll-padding: 8px;
  --hand-tile-size: clamp(18px, calc((100% - var(--hand-tile-gap) * 13) / 14), 54px);
  display: flex;
  flex-wrap: nowrap;
  gap: var(--hand-tile-gap);
  width: 100%;
  padding-right: var(--hand-scroll-padding);
  overflow-x: auto;
  overscroll-behavior-x: contain;
}

.hand-opponent {
  justify-content: flex-start;
  gap: var(--hand-tile-gap);
  padding-right: var(--hand-scroll-padding);
  overflow-x: auto;
  overscroll-behavior-x: contain;
}

.hand-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.tile-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tile {
  position: relative;
  width: 54px;
  height: 80px;
  border-radius: 12px;
  background: linear-gradient(145deg, #0f1528, #141d36);
  border: 1px solid rgba(96, 122, 209, 0.4);
  box-shadow:
    0 10px 20px rgba(5, 10, 25, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.hand .tile,
.hand-opponent .tile {
  width: var(--hand-tile-size, 54px);
  height: calc(var(--hand-tile-size, 54px) * 1.48);
  border-radius: clamp(6px, calc(var(--hand-tile-size, 54px) * 0.22), 12px);
  padding: clamp(2px, calc(var(--hand-tile-size, 54px) * 0.08), 4px);
}

.tile button {
  background: none;
}

.tile.selected {
  border-color: rgba(93, 224, 255, 0.85);
  transform: translateY(-4px);
  box-shadow:
    0 12px 22px rgba(9, 24, 54, 0.55),
    0 0 18px rgba(102, 189, 255, 0.45);
}

.tile.drawn {
  border-color: rgba(136, 255, 182, 0.8);
  box-shadow:
    0 12px 18px rgba(10, 32, 20, 0.5),
    0 0 16px rgba(136, 255, 182, 0.5);
}

.tile-hidden {
  background: rgba(9, 14, 30, 0.78);
}

.tile-small {
  width: 44px;
  height: 64px;
  border-radius: 10px;
}

.tile-face {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.melds-value {
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
  min-width: 160px;
}

.meld-card.self {
  border-color: rgba(146, 181, 255, 0.55);
}

.meld-kind {
  font-size: 0.9rem;
  color: #a9c0ff;
  letter-spacing: 0.08em;
}

.meld-tiles {
  display: flex;
  gap: 8px;
}

.actions {
  display: flex;
  justify-content: center;
}

.action-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}

.action-grid button {
  min-width: 130px;
}

.discard-action {
  background: linear-gradient(135deg, #ffb347, #ff7752);
  color: #1b0f09;
  border: none;
}

.disconnected-hint {
  margin-top: 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  align-items: center;
  color: #d4defb;
}

@media (max-width: 1200px) {
  .panel {
    padding-bottom: 12px;
  }

  .panel-foot {
    padding: 16px;
  }

  .action-grid {
    flex-direction: column;
    width: 100%;
  }

  .action-grid button {
    width: 100%;
  }
}

@media (max-width: 600px) {
  .hand {
    --hand-tile-gap: 4px;
    --hand-scroll-padding: 4px;
  }
}
</style>
