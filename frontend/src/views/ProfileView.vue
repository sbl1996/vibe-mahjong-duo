<template>
  <GameLayout>
    <div class="profile-page">
      <section class="summary-section">
        <div class="profile-hero">
          <div class="hero-top">
            <div class="hero-meta">
              <span class="identity-chip">玩家档案</span>
              <h1 class="username">{{ user?.username || '未知玩家' }}</h1>
              <p class="hero-subtitle">专属积分与战绩总览</p>
            </div>
            <div class="score-display">
              <span class="score-label">当前积分</span>
              <span class="score-value">{{ user?.score ?? '--' }}</span>
              <span class="score-hint">总对局 {{ stats.total_games ?? 0 }}</span>
            </div>
          </div>
          <div class="hero-stats">
            <div
              v-for="highlight in statHighlights"
              :key="highlight.label"
              class="hero-stat-item"
            >
              <span class="stat-label">{{ highlight.label }}</span>
              <span class="stat-value">{{ highlight.value }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="detail-grid">
        <article class="panel records-panel">
          <header class="panel-header">
            <div>
              <h2>最近对局记录</h2>
              <p class="panel-subtitle">展示最新 10 场对局</p>
            </div>
            <button class="refresh-button" @click="loadRecords" :disabled="loading">
              {{ loading ? '刷新中…' : '刷新' }}
            </button>
          </header>

          <div class="records-list" v-if="records.length">
            <div v-for="record in records" :key="record.id" class="record-card">
              <span class="opponent-name">{{ record.opponent_username || '未知玩家' }}</span>
              <span class="record-result" :class="`is-${record.result}`">
                {{ getResultText(record.result) }}
              </span>
              <span class="score-delta" :class="scoreChangeClass(record.score_change)">
                {{ record.score_change > 0 ? '+' : '' }}{{ record.score_change }}
              </span>
              <span class="meta-text">{{ record.is_first_hand ? '先手' : '后手' }} | 最终积分: {{ record.final_score }}</span>
              <span class="record-time">{{ formatDate(record.game_time) }}</span>
            </div>
          </div>

          <div class="empty-state" v-else>
            暂无对局记录
          </div>
        </article>

        <article class="panel leaderboard-panel">
          <header class="panel-header">
            <div>
              <h2>排行榜</h2>
              <p class="panel-subtitle">全服前十玩家</p>
            </div>
          </header>

          <div class="leaderboard-list" v-if="leaderboard.length">
            <div
              v-for="(player, index) in leaderboard"
              :key="player.id"
              class="leaderboard-row"
            >
              <span class="leaderboard-rank" :class="rankClass(index)">
                {{ String(index + 1).padStart(2, '0') }}
              </span>
              <span class="leaderboard-name">{{ player.username }}</span>
              <span class="leaderboard-score">{{ player.score }}</span>
            </div>
          </div>
          <div class="empty-state" v-else>
            暂无排行榜数据
          </div>
        </article>
      </section>
    </div>
  </GameLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import GameLayout from '../components/GameLayout.vue'
import { useGameStore } from '../stores/game'

const store = useGameStore()
const { user, setUser } = store

const stats = ref({
  total_games: 0,
  wins: 0,
  losses: 0,
  draws: 0,
  win_rate: 0
})

interface GameRecord {
  id: number
  opponent_username: string
  game_time: string
  is_first_hand: boolean
  result: 'win' | 'lose' | 'draw'
  score_change: number
  final_score: number
}

interface LeaderboardPlayer {
  id: number
  username: string
  score: number
}

const records = ref<GameRecord[]>([])
const leaderboard = ref<LeaderboardPlayer[]>([])
const loading = ref(false)

const winRateText = computed(() => {
  const rate = Number(stats.value.win_rate)
  if (!Number.isFinite(rate)) return '--'
  return `${rate.toFixed(1)}%`
})

const statHighlights = computed(() => [
  { label: '胜场', value: stats.value.wins ?? 0 },
  { label: '失败', value: stats.value.losses ?? 0 },
  { label: '平局', value: stats.value.draws ?? 0 },
  { label: '胜率', value: winRateText.value }
])

const loadUserData = async () => {
  if (!user.value) return

  try {
    // 获取用户统计信息
    const statsResponse = await fetch(`/api/user/${user.value.username}`)
    if (statsResponse.ok) {
      const data = await statsResponse.json()
      if (data.user) {
        setUser(data.user)
      }
      stats.value = {
        ...stats.value,
        ...(data.stats || {}),
      }
    }

    // 加载对局记录和排行榜
    await loadRecords()
    await loadLeaderboard()
  } catch (error) {
    console.error('加载用户数据失败:', error)
  }
}

const loadRecords = async () => {
  if (!user.value) return

  loading.value = true
  try {
    const response = await fetch(`/api/user/${user.value.username}/records?limit=10`)
    if (response.ok) {
      const data = await response.json()
      records.value = (data.records || []) as GameRecord[]
    }
  } catch (error) {
    console.error('加载对局记录失败:', error)
  } finally {
    loading.value = false
  }
}

const loadLeaderboard = async () => {
  try {
    const response = await fetch('/api/leaderboard?limit=10')
    if (response.ok) {
      const data = await response.json()
      leaderboard.value = (data.leaderboard || []) as LeaderboardPlayer[]
    }
  } catch (error) {
    console.error('加载排行榜失败:', error)
  }
}

const scoreChangeClass = (value: number) => {
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return 'neutral'
}

const rankClass = (index: number) => {
  if (index === 0) return 'gold'
  if (index === 1) return 'silver'
  if (index === 2) return 'bronze'
  return ''
}

const DEFAULT_TIME_ZONE = 'Asia/Shanghai'
const DEFAULT_OFFSET_MINUTES = 8 * 60

const resolveUserTimeZone = () => {
  try {
    const { timeZone } = Intl.DateTimeFormat().resolvedOptions()
    if (timeZone) return timeZone
  } catch (error) {
    console.warn('无法解析用户时区，退回默认值:', error)
  }
  return DEFAULT_TIME_ZONE
}

const userTimeZone = resolveUserTimeZone()

const normalizeUtcString = (value: string) => {
  const trimmed = value.trim()
  if (!trimmed) return ''
  if (/Z$|[+-]\d{2}:?\d{2}$/.test(trimmed)) {
    return trimmed
  }
  const withSeparator = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  return `${withSeparator}Z`
}

const parseUtcDate = (value: string | number | Date) => {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }

  if (typeof value === 'number') {
    const fromNumber = new Date(value)
    return Number.isNaN(fromNumber.getTime()) ? null : fromNumber
  }

  if (typeof value !== 'string') return null
  const normalized = normalizeUtcString(value)
  if (!normalized) return null

  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const formatDate = (value: string | number | Date) => {
  const date = parseUtcDate(value)
  if (!date) return typeof value === 'string' ? value : '--'

  try {
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: userTimeZone,
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date)
  } catch (error) {
    console.warn('Intl 格式化失败，使用东八区偏移:', error)
    const localDate = new Date(date.getTime() + DEFAULT_OFFSET_MINUTES * 60 * 1000)
    const pad = (num: number) => String(num).padStart(2, '0')
    return `${pad(localDate.getMonth() + 1)}/${pad(localDate.getDate())} ${pad(localDate.getHours())}:${pad(localDate.getMinutes())}`
  }
}

const getResultText = (result: string) => {
  switch (result) {
    case 'win': return '胜利'
    case 'lose': return '失败'
    case 'draw': return '平局'
    default: return result
  }
}


onMounted(() => {
  loadUserData()
})
</script>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  color: #e3eaff;
}

.summary-section {
  width: 100%;
}


.profile-hero {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 28px;
  border-radius: 28px;
  background: linear-gradient(150deg, rgba(37, 54, 116, 0.95), rgba(15, 24, 53, 0.9));
  border: 1px solid rgba(118, 154, 255, 0.45);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 30px 60px rgba(6, 12, 30, 0.52);
}

.hero-top {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.hero-meta {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 200px;
}

.hero-subtitle {
  margin: 0;
  font-size: 0.95rem;
  color: #9fb4ff;
  letter-spacing: 0.08em;
}

.score-display {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  padding: 20px 26px;
  border-radius: 24px;
  background: rgba(12, 20, 44, 0.9);
  border: 1px solid rgba(140, 167, 255, 0.5);
  box-shadow: 0 18px 38px rgba(10, 18, 42, 0.6);
  min-width: min(260px, 100%);
}

.score-hint {
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  color: rgba(197, 213, 255, 0.75);
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
}

.hero-stat-item {
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(10, 17, 38, 0.92);
  border: 1px solid rgba(120, 149, 255, 0.3);
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: inset 0 0 16px rgba(6, 11, 28, 0.45);
}

.stat-label {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #8fa2ff;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #eef2ff;
  letter-spacing: 0.06em;
}

.identity-chip {
  align-self: flex-start;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(102, 126, 234, 0.22);
  border: 1px solid rgba(102, 126, 234, 0.45);
  color: #dbe5ff;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.username {
  margin: 6px 0 12px;
  font-size: clamp(1.9rem, 2vw + 1.2rem, 2.8rem);
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #f8fbff;
  text-shadow:
    0 0 24px rgba(91, 129, 255, 0.6),
    0 4px 12px rgba(0, 0, 0, 0.35);
}

.score-label {
  font-size: 0.9rem;
  color: #a7b6ff;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.score-value {
  font-size: clamp(2.2rem, 3vw + 1.4rem, 3rem);
  font-weight: 700;
  color: #78b3ff;
  letter-spacing: 0.08em;
  text-shadow:
    0 16px 40px rgba(48, 108, 255, 0.45),
    0 0 18px rgba(90, 138, 255, 0.6);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
  gap: 20px;
  align-items: flex-start;
}

.panel {
  padding: 24px;
  border-radius: 24px;
  background: rgba(13, 21, 42, 0.92);
  border: 1px solid rgba(110, 143, 240, 0.32);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 24px 48px rgba(4, 8, 22, 0.45);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.panel-header h2 {
  margin: 0;
  font-size: 1.3rem;
  letter-spacing: 0.08em;
  color: #f1f5ff;
}

.panel-subtitle {
  margin: 6px 0 0;
  font-size: 0.85rem;
  color: #889aed;
  letter-spacing: 0.06em;
}

.refresh-button {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.35), rgba(45, 197, 253, 0.35));
  border: 1px solid rgba(102, 126, 234, 0.6);
  color: #e8efff;
  border-radius: 999px;
  padding: 10px 18px;
  font-size: 0.9rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.25s ease;
}

.refresh-button:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.55), rgba(45, 197, 253, 0.55));
  border-color: rgba(137, 162, 255, 0.85);
  box-shadow: 0 12px 24px rgba(32, 62, 140, 0.45);
}

.refresh-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.records-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.record-card {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) auto auto minmax(0, 1.6fr) minmax(0, 1.2fr);
  align-items: center;
  padding: 14px 18px;
  border-radius: 16px;
  background: rgba(9, 15, 33, 0.95);
  border: 1px solid rgba(103, 130, 228, 0.24);
  box-shadow: inset 0 0 18px rgba(5, 9, 25, 0.4);
  gap: 12px;
}

.record-card > * {
  min-width: 0;
}

.opponent-name {
  font-size: 1.08rem;
  font-weight: 600;
  color: #f0f4ff;
  letter-spacing: 0.05em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-time {
  font-size: 0.84rem;
  color: #8ea0d8;
  letter-spacing: 0.04em;
  justify-self: end;
  text-align: right;
  white-space: nowrap;
}

.meta-text {
  font-size: 0.85rem;
  color: #aeb9f5;
  letter-spacing: 0.04em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-result {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 0.85rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  border: 1px solid rgba(127, 150, 255, 0.4);
  background: rgba(35, 48, 94, 0.6);
  color: #dee6ff;
}

.record-result.is-win {
  border-color: rgba(46, 204, 113, 0.6);
  background: rgba(46, 204, 113, 0.18);
  color: #63ffb2;
  text-shadow: 0 0 12px rgba(99, 255, 178, 0.65);
}

.record-result.is-lose {
  border-color: rgba(231, 76, 60, 0.6);
  background: rgba(231, 76, 60, 0.18);
  color: #ff8c7a;
}

.record-result.is-draw {
  border-color: rgba(255, 206, 84, 0.5);
  background: rgba(255, 206, 84, 0.16);
  color: #ffe68a;
}

.score-delta {
  font-weight: 600;
  font-size: 1rem;
  letter-spacing: 0.06em;
  padding: 6px 12px;
  border-radius: 10px;
  background: rgba(21, 32, 60, 0.85);
  border: 1px solid transparent;
  color: #dbe4ff;
}

.score-delta.positive {
  border-color: rgba(46, 204, 113, 0.48);
  color: #5bfdab;
  box-shadow: 0 0 12px rgba(46, 204, 113, 0.35);
}

.score-delta.negative {
  border-color: rgba(231, 76, 60, 0.48);
  color: #ff9a8a;
  box-shadow: 0 0 12px rgba(231, 76, 60, 0.28);
}

.score-delta.neutral {
  border-color: rgba(127, 150, 255, 0.25);
  color: #bfcaff;
}

.empty-state {
  padding: 32px;
  border-radius: 18px;
  text-align: center;
  color: #8fa4e6;
  background: rgba(10, 17, 35, 0.85);
  border: 1px dashed rgba(102, 126, 234, 0.35);
  letter-spacing: 0.08em;
}

.leaderboard-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.leaderboard-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(8, 14, 30, 0.92);
  border: 1px solid rgba(100, 128, 228, 0.22);
}

.leaderboard-rank {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  letter-spacing: 0.08em;
  background: rgba(16, 26, 52, 0.75);
  color: #bcd1ff;
  border: 1px solid rgba(102, 126, 234, 0.28);
}

.leaderboard-rank.gold {
  background: linear-gradient(140deg, rgba(255, 215, 128, 0.8), rgba(229, 176, 64, 0.8));
  color: #3a2d12;
  border-color: rgba(255, 215, 128, 0.9);
  box-shadow: 0 0 15px rgba(255, 215, 128, 0.5);
}

.leaderboard-rank.silver {
  background: linear-gradient(140deg, rgba(210, 223, 255, 0.8), rgba(164, 183, 223, 0.8));
  color: #1f2536;
  border-color: rgba(210, 223, 255, 0.9);
  box-shadow: 0 0 15px rgba(210, 223, 255, 0.4);
}

.leaderboard-rank.bronze {
  background: linear-gradient(140deg, rgba(255, 191, 150, 0.82), rgba(221, 151, 98, 0.82));
  color: #361e0f;
  border-color: rgba(255, 191, 150, 0.9);
  box-shadow: 0 0 15px rgba(255, 191, 150, 0.4);
}

.leaderboard-name {
  flex: 1;
  font-size: 1rem;
  font-weight: 500;
  color: #f0f4ff;
  letter-spacing: 0.06em;
}

.leaderboard-score {
  font-size: 1.1rem;
  font-weight: 600;
  color: #80b5ff;
  letter-spacing: 0.08em;
}

@media (max-width: 1024px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .hero-top {
    flex-direction: column;
    align-items: flex-start;
  }

  .score-display {
    align-self: stretch;
    align-items: flex-start;
    text-align: left;
  }

  .record-card {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-auto-rows: auto;
    gap: 8px 12px;
  }

  .record-result,
  .score-delta {
    justify-self: start;
  }

  .meta-text,
  .record-time {
    grid-column: 1 / -1;
    white-space: normal;
  }

  .record-time {
    text-align: left;
  }

  .meta-text {
    font-size: 0.82rem;
  }
}

@media (max-width: 720px) {
  .profile-page {
    gap: 20px;
  }

  .panel {
    padding: 20px;
  }

  .record-card {
    padding: 14px 16px;
  }
}
</style>
