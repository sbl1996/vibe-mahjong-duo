<template>
  <section v-if="shouldRender" :class="['fan-summary', { 'fan-summary--dense': dense }]">
    <div class="fan-summary__header">
      <h3>{{ title }}</h3>
    </div>
    <div class="fan-summary__players">
      <article v-for="entry in entries" :key="entry.seat" class="fan-summary__player">
        <header class="fan-summary__player-header">
          <h4>{{ entry.label }}</h4>
          <span class="fan-summary__total">{{ entry.fanTotal }} 番</span>
        </header>
        <p :class="['fan-summary__net-change', { positive: entry.netChange > 0, negative: entry.netChange < 0 }]">
          积分变化：{{ formatSigned(entry.netChange) }}
        </p>
        <ul class="fan-summary__breakdown">
          <li
            v-for="(row, index) in entry.breakdown"
            :key="`fan-${entry.seat}-${index}`"
            class="fan-summary__breakdown-item"
          >
            <div class="fan-summary__row">
              <span class="fan-summary__name">{{ row.name }}</span>
              <span :class="['fan-summary__value', { positive: (row.fan ?? 0) > 0, negative: (row.fan ?? 0) < 0 }]">
                {{ formatSigned(row.fan ?? 0) }}
              </span>
            </div>
            <small v-if="row.detail" class="fan-summary__detail">{{ row.detail }}</small>
          </li>
          <li v-if="!entry.breakdown.length" class="fan-summary__breakdown-item fan-summary__breakdown-item--empty">
            <span class="fan-summary__empty">暂无积分加成</span>
          </li>
        </ul>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FanBreakdownItem, FanPlayerScore, FanSummary } from '../stores/game'

type DisplayEntry = {
  seat: number
  label: string
  fanTotal: number
  netChange: number
  breakdown: FanBreakdownItem[]
}

const props = withDefaults(
  defineProps<{
    summary: FanSummary | null | undefined
    seat: number | null
    nickname: string
    opponent: string
    title?: string
    dense?: boolean
  }>(),
  {
    title: '积分结算',
    dense: false,
  }
)

const shouldRender = computed(() => props.summary !== null && props.summary !== undefined)

const entries = computed<DisplayEntry[]>(() => {
  const players = props.summary?.players ?? {}
  const seatValue = props.seat

  // Determine display order: my team first, then opponent team
  let displayOrder: number[]
  if (seatValue === null) {
    // If no seat assigned, use seat order
    displayOrder = [0, 1]
  } else {
    // My team first, then opponent team
    displayOrder = [seatValue, 1 - seatValue]
  }

  return displayOrder.map((seatId) => {
    const payload = players[String(seatId)] as FanPlayerScore | undefined
    const fanTotal = typeof payload?.fan_total === 'number' ? payload.fan_total : 0
    const netChange = typeof payload?.net_change === 'number' ? payload.net_change : 0
    const rawBreakdown = payload?.fan_breakdown
    const breakdown = Array.isArray(rawBreakdown) ? (rawBreakdown as FanBreakdownItem[]) : []
    return {
      seat: seatId,
      label: resolveSeatLabel(seatId),
      fanTotal,
      netChange,
      breakdown,
    }
  })
})

function resolveSeatLabel(seatId: number): string {
  const seatText = `座位 ${seatId}`
  const seatValue = props.seat
  if (seatValue === null) return seatText
  if (seatValue === seatId) {
    return `${props.nickname || '我方'}（${seatText}）`
  }
  return `${props.opponent || '对手'}（${seatText}）`
}

function formatSigned(value: number): string {
  if (Number.isFinite(value) && value > 0) return `+${value}`
  if (Number.isFinite(value) && value < 0) return `${value}`
  return '0'
}
</script>

<style scoped>
.fan-summary {
  background: rgba(8, 14, 29, 0.9);
  border: 1px solid rgba(96, 126, 216, 0.28);
  border-radius: 18px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fan-summary--dense {
  padding: 16px 18px;
  gap: 12px;
}

.fan-summary__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  color: #dde5ff;
}

.fan-summary__header h3 {
  margin: 0;
  font-size: 1.05rem;
  letter-spacing: 0.05em;
}

.fan-summary__net {
  color: #9fb8ff;
  font-size: 0.95rem;
}

.fan-summary__players {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.fan-summary__player {
  background: rgba(12, 21, 43, 0.9);
  border: 1px solid rgba(94, 126, 212, 0.35);
  border-radius: 16px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fan-summary--dense .fan-summary__player {
  padding: 12px 14px;
  gap: 8px;
}

.fan-summary__player-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  color: #d1deff;
}

.fan-summary__player-header h4 {
  margin: 0;
  font-size: 0.98rem;
  letter-spacing: 0.04em;
}

.fan-summary__total {
  color: #f2f5ff;
  font-weight: 600;
}

.fan-summary__net-change {
  margin: 0;
  color: #9bb3ff;
  font-size: 0.95rem;
}

.fan-summary__net-change.positive {
  color: #7fe29b;
}

.fan-summary__net-change.negative {
  color: #ff9a9a;
}

.fan-summary__breakdown {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fan-summary__breakdown-item {
  background: rgba(8, 14, 29, 0.75);
  border-radius: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(70, 103, 190, 0.25);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fan-summary__breakdown-item--empty {
  align-items: center;
  justify-content: center;
  color: #7d8fc4;
}

.fan-summary__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.fan-summary__name {
  color: #dce4ff;
  font-size: 0.95rem;
}

.fan-summary__value {
  font-weight: 600;
  color: #f5d18a;
}

.fan-summary__value.positive {
  color: #7fe29b;
}

.fan-summary__value.negative {
  color: #ff9a9a;
}

.fan-summary__detail {
  color: #8ea7ff;
  font-size: 0.85rem;
}

.fan-summary__empty {
  font-size: 0.9rem;
}
</style>
