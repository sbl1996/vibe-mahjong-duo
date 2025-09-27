<template>
  <GameLayout>
    <section class="rules-page">
      <header class="rules-hero">
        <h2>番数规则总览</h2>
        <p>
          番数包括基础番、牌型番、杠番及役满。
          玩家胡牌时按条件叠加番数（普通手封顶 7 番），失败方承担等额负番。
        </p>
      </header>

      <div class="rules-grid">
        <article
          v-for="section in ruleSections"
          :key="section.title"
          class="rules-card"
        >
          <h3>{{ section.title }}</h3>
          <p class="section-description">{{ section.description }}</p>
          <ul class="rule-list">
            <li v-for="item in section.items" :key="item.name" class="rule-item">
              <div>
                <span class="rule-name">{{ item.name }}</span>
                <span class="rule-detail">{{ item.detail }}</span>
              </div>
              <span class="rule-fan">{{ item.fan }}</span>
            </li>
          </ul>
        </article>
      </div>

      <section class="yakuman-card">
        <h3>役满（固定 8 番）</h3>
        <p class="section-description">
          役满优先判定。如果满足以下任意一种役满，直接计 8 番，其余普通番不再叠加，失败方记 <span class="highlight">-8 番</span>。
        </p>
        <ul class="yakuman-list">
          <li v-for="item in yakumanRules" :key="item.name" class="yakuman-item">
            <div>
              <span class="rule-name">{{ item.name }}</span>
              <span class="rule-detail">{{ item.detail }}</span>
            </div>
            <span class="rule-fan">{{ item.fan }}</span>
          </li>
        </ul>
      </section>

      <section class="scoring-card">
        <h3>积分换算</h3>
        <p class="section-description">
          胜者积分 = <code>8 × 2<sup>番</sup></code>；败者扣除同等积分。下表列出常见番数的对应分值。
        </p>
        <div class="scoring-table">
          <div class="scoring-row scoring-header">
            <span>番数</span>
            <span>积分变动</span>
            <span>说明</span>
          </div>
          <div
            v-for="entry in scoringTable"
            :key="entry.label"
            class="scoring-row"
          >
            <span>{{ entry.label }}</span>
            <span>{{ entry.points }}</span>
            <span>{{ entry.remark }}</span>
          </div>
        </div>
      </section>
    </section>
  </GameLayout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import GameLayout from '../components/GameLayout.vue'

const ruleSections = [
  {
    title: '基础 / 行为 / 杠番',
    description: '胡牌基础番、自摸／门前等行为番以及明暗杠带来的番数奖励。',
    items: [
      { name: '和底', fan: '+1', detail: '胡牌必得的基础番。' },
      { name: '自摸', fan: '+1', detail: '自摸胡牌时额外加番。' },
      { name: '门前清', fan: '+1', detail: '整局未碰、未明杠保持门清。' },
      { name: '杠', fan: '+1 / 每杠', detail: '明杠、暗杠、加杠均计入；当局合计最多 +2 番。' },
    ],
  },
  {
    title: '牌型番',
    description: '由手牌结构决定的番数，可以与非牌型叠加。',
    items: [
      { name: '断幺九', fan: '+1', detail: '全部牌为 2-8，去除幺九。' },
      { name: '对对胡', fan: '+2', detail: '四个刻子 + 将眼。' },
      { name: '三暗刻', fan: '+2 / +1', detail: '拥有三副暗刻；若已满足对对胡，则在 +2 基础上再额外 +1。' },
      { name: '清一色', fan: '+2', detail: '所有牌属于同一花色（万 / 条 / 筒）。' },
      { name: '平和', fan: '+2', detail: '门前清且四组面子均为顺子。' },
    ],
  },
]

const yakumanRules = [
  { name: '四暗刻', fan: '+8', detail: '四副暗刻 + 将牌，自摸或荣和皆算。' },
  { name: '四杠', fan: '+8', detail: '组合中出现四个杠（任意明暗）。' },
  { name: '清幺九', fan: '+8', detail: '所有面子与将均为幺九牌（1、9）。' },
]

const scoringTable = computed(() => {
  const base = 8
  const regularFans = Array.from({ length: 7 }, (_, idx) => {
    const fan = idx + 1
    return {
      label: `${fan} 番`,
      points: base * (2 ** fan),
      remark: fan === 7 ? '普通手封顶' : '',
    }
  })
  const yakuman = {
    label: '8 番（役满）',
    points: base * (2 ** 8),
    remark: '满足任一役满时的固定番数',
  }
  return [...regularFans, yakuman]
})
</script>

<style scoped>
.rules-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.rules-hero {
  background: linear-gradient(145deg, rgba(30, 42, 86, 0.85), rgba(17, 25, 49, 0.92));
  border: 1px solid rgba(95, 126, 212, 0.35);
  border-radius: 20px;
  padding: 24px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.rules-hero h2 {
  margin: 0 0 12px;
  font-size: 1.6rem;
  letter-spacing: 0.08em;
}

.rules-hero p {
  margin: 0;
  color: #b7c7ff;
  line-height: 1.6;
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 18px;
}

.rules-card,
.yakuman-card,
.scoring-card,
.notes-card {
  background: rgba(12, 20, 42, 0.88);
  border: 1px solid rgba(88, 118, 204, 0.35);
  border-radius: 18px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rules-card h3,
.yakuman-card h3,
.scoring-card h3,
.notes-card h3 {
  margin: 0;
  font-size: 1.2rem;
  letter-spacing: 0.06em;
  color: #dee7ff;
}

.section-description {
  margin: 0;
  color: #8ea7ff;
  font-size: 0.95rem;
  line-height: 1.5;
}

.rule-list,
.yakuman-list,
.notes-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rule-item,
.yakuman-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 14px 16px;
  background: rgba(8, 14, 29, 0.75);
  border-radius: 14px;
  border: 1px solid rgba(70, 103, 190, 0.25);
}

.rule-name {
  display: block;
  font-weight: 600;
  color: #dce4ff;
}

.rule-detail {
  display: block;
  color: #9fb4ff;
  font-size: 0.9rem;
  margin-top: 4px;
}

.rule-fan {
  color: #f5d18a;
  font-weight: 600;
  white-space: nowrap;
}

.yakuman-card {
  border-color: rgba(235, 158, 97, 0.35);
  background: linear-gradient(135deg, rgba(30, 22, 54, 0.9), rgba(18, 27, 52, 0.92));
}

.highlight {
  color: #f9d27c;
  font-weight: 600;
}

.scoring-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scoring-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: rgba(8, 14, 29, 0.75);
  border-radius: 12px;
  border: 1px solid rgba(70, 103, 190, 0.25);
  color: #d0dcff;
}

.scoring-header {
  background: rgba(28, 44, 92, 0.85);
  font-weight: 600;
}

.notes-list li {
  color: #b9c9ff;
  line-height: 1.6;
  background: rgba(8, 14, 29, 0.6);
  border-radius: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(70, 103, 190, 0.2);
}

@media (max-width: 768px) {
  .rules-grid {
    grid-template-columns: 1fr;
  }

  .scoring-row {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
  }

  .scoring-row span:nth-child(3) {
    grid-column: 1 / -1;
  }
}
</style>
