<template>
  <div class="page">
    <div class="game-card">
      <header class="game-header">
        <div class="title-block">
          <h1>Mahjong Duo</h1>
          <p class="subtitle">双人即时麻将对战</p>
        </div>
        <div class="header-status">
          <div class="status-line">
            <span class="status-dot" :class="connected ? 'online' : 'offline'"></span>
            <span>{{ connected ? '已连接' : '未连接' }}</span>
          </div>
          <div class="status-line" v-if="connected && status.players">
              <span>
                {{ onlineSummary }} ｜座位 {{ seat ?? '?' }}｜对手 {{ opponent || '?' }}
                <template v-if="!gameInProgress && readyStatus">｜准备 {{ readySummary }}</template>
              </span>
            </div>
        </div>
      </header>

      <section class="connection-card" v-if="!gameInProgress">
        <div class="field-group">
          <label>昵称</label>
          <input v-model="nickname" placeholder="请输入昵称" />
        </div>
        <div class="field-group">
          <label>房间号</label>
          <input v-model="roomId" placeholder="room1" />
        </div>
        <div class="action-group">
          <button class="primary" @click="connect" :disabled="connected">{{ connected ? '已连接' : '连接房间' }}</button>
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

      <div class="board" v-if="connected">
        <section class="panel panel-opp">
          <header class="panel-head">
            <h3>对手桌面</h3>
            <small v-if="opponent">{{ opponent }}</small>
          </header>
          <div class="panel-body">
            <div class="info-row hand-row">
              <span class="label">手牌</span>
              <div class="hand-area">
                <div class="hand hand-opponent">
                  <div
                    v-for="(_,i) in oppHandPlaceholders"
                    :key="'oh'+i"
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
              <span class="value" v-if="meldsOpp.length">
                <span v-for="(m,i) in meldsOpp" :key="'mo'+i" class="meld-chip">{{ meldText(m) }}</span>
              </span>
              <span class="value" v-else>暂无</span>
            </div>
            <div class="info-row">
              <span class="label">弃牌河</span>
              <span class="value tile-row">
                <span
                  v-for="(t,i) in discOpp"
                  :key="'do'+i"
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
            <small v-if="nickname">{{ nickname }}</small>
          </header>
          <div class="panel-body">
            <div class="info-row hand-row">
              <span class="label">手牌</span>
              <div class="hand-area">
                <div class="hand">
                  <button
                    v-for="(t,i) in hand"
                    :key="'h'+i"
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
              <span class="value" v-if="meldsSelf.length">
                <span v-for="(m,i) in meldsSelf" :key="'ms'+i" class="meld-chip">{{ meldText(m) }}</span>
              </span>
              <span class="value" v-else>暂无</span>
            </div>
            <div class="info-row">
              <span class="label">弃牌河</span>
              <span class="value tile-row">
                <span
                  v-for="(t,i) in discSelf"
                  :key="'ds'+i"
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
                <button v-for="(a,i) in visibleActions" :key="'ac'+i" @click="doAction(a)">{{ actText(a) }}</button>
              </div>
            </div>
          </footer>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

type Action = any
type Meld = { kind: string, tiles: number[] }

const nickname = ref('A')
const roomId = ref('room1')
const ws = ref<WebSocket|null>(null)
const connected = ref(false)

const seat = ref<number|null>(null)
const opponent = ref<string>('')
const status = ref<any>({})
const readyStatus = ref<any>(null)

const hand = ref<number[]>([])
const meldsSelf = ref<Meld[]>([])
const meldsOpp = ref<Meld[]>([])
const discSelf = ref<number[]>([])
const discOpp = ref<number[]>([])
const oppHandCount = ref<number>(13)

const actions = ref<Action[]>([])
const events = ref<any[]>([])
const gameResult = ref<any|null>(null)

const selectedHandIndex = ref<number|null>(null)
const lastDrawnIndex = ref<number|null>(null)
const pendingDrawTile = ref<number|null>(null)
const gameInProgress = ref(false)

const discardActions = computed(() => actions.value.filter((a: Action) => a.type === 'discard'))
const visibleActions = computed(() => actions.value.filter((a: Action) => a.type !== 'discard'))
const selectedTileValue = computed(() => selectedHandIndex.value !== null ? hand.value[selectedHandIndex.value] : null)
const selectedDiscardAction = computed(() => {
  if(selectedTileValue.value === null) return null
  return discardActions.value.find((a: Action) => a.tile === selectedTileValue.value) || null
})
const canDiscardSelected = computed(() => Boolean(selectedDiscardAction.value))
const showActionFooter = computed(() => visibleActions.value.length > 0 || discardActions.value.length > 0)
const onlineSummary = computed(() => {
  const players = status.value?.players
  if (!players || !Array.isArray(players)) return '未知'
  return players.map((p: boolean, idx: number) => `座位${idx}：${p ? '在线' : '离线'}`).join('｜')
})
const readySummary = computed(() => {
  const ready = readyStatus.value
  if (!ready) return '等待中'
  return Object.keys(ready)
    .map((key) => `座位${key}：${ready[key] ? '✔' : '…'}`)
    .join('｜')
})
const isReady = computed(() => {
  if (!readyStatus.value || seat.value === null) return false
  const seatKey = seat.value
  if (Object.prototype.hasOwnProperty.call(readyStatus.value, seatKey)) {
    return Boolean(readyStatus.value[seatKey])
  }
  const stringKey = String(seatKey)
  if (Object.prototype.hasOwnProperty.call(readyStatus.value, stringKey)) {
    return Boolean(readyStatus.value[stringKey])
  }
  return false
})
const oppHandPlaceholders = computed(() => Array.from({ length: oppHandCount.value }, () => null))

const suitAssetCodes = ['m','s','p'] as const

function tileImage(t:number){
  if (!Number.isFinite(t) || t < 0) return ''
  const rank = (t % 9) + 1
  const suitIndex = Math.floor(t / 9)
  const suitCode = suitAssetCodes[suitIndex] ?? 'm'
  return `/static/f${rank}${suitCode}.png`
}

const tileBackImage = '/static/flat_back.png'

// 监控手牌变化，手动同步时清除高亮
watch(hand, (newHand, oldHand) => {
  if (oldHand) {
    if (pendingDrawTile.value !== null && newHand.length === oldHand.length + 1) {
      const tile = pendingDrawTile.value
      const addedIndex = tile !== null ? findAddedIndexForTile(newHand, oldHand, tile) : -1
      const fallbackIndex = addedIndex >= 0 ? addedIndex : findAddedIndex(newHand, oldHand)
      lastDrawnIndex.value = fallbackIndex >= 0 ? fallbackIndex : null
      pendingDrawTile.value = null
    } else if (newHand.length < oldHand.length) {
      lastDrawnIndex.value = null
      pendingDrawTile.value = null
    }
  } else {
    pendingDrawTile.value = null
  }

  if(selectedHandIndex.value === null) return
  if(newHand.length === 0 || selectedHandIndex.value >= newHand.length) {
    selectedHandIndex.value = null
  }
})

watch(discardActions, (newActions) => {
  if(selectedHandIndex.value === null) return
  if(!newActions.length) {
    selectedHandIndex.value = null
    return
  }
  const tile = selectedTileValue.value
  if(tile === null) {
    selectedHandIndex.value = null
    return
  }
  const stillAllowed = newActions.some((a: Action) => a.tile === tile)
  if(!stillAllowed) {
    selectedHandIndex.value = null
  }
})

function t2s(t:number){ // 后端同编码：0..26
  const suit = ['万','条','筒'][Math.floor(t/9)]
  const r = t%9 + 1
  return `${r}${suit}`
}
function kindText(k:string){
  if(k==='pong') return '碰'
  if(k==='chow') return '吃'
  if(k==='kong') return '杠'
  return k
}
function meldText(m:Meld){
  return `${kindText(m.kind)}：${m.tiles.map(t2s).join('')}`
}
function actText(a:Action){
  if(a.type==='discard') return `打出 ${t2s(a.tile)}`
  if(a.type==='draw') return '摸牌'
  if(a.type==='peng') return `碰 ${t2s(a.tile)}`
  if(a.type==='kong') return `杠(${a.style}) ${t2s(a.tile)}`
  if(a.type==='hu') return a.style==='self' ? '自摸胡' : `荣和 ${t2s(a.tile)}`
  if(a.type==='pass') return '过'
  return JSON.stringify(a)
}

function connect(){
  if(ws.value) return
  ws.value = new WebSocket(`ws://127.0.0.1:8000/ws`)
  ws.value.onopen = () => {
    connected.value = true
    send({type:"join_room", room_id: roomId.value, nickname: nickname.value})
  }
  ws.value.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    // console.log('MSG', msg)
    if(msg.type==='room_joined'){
      seat.value = msg.seat
    }else if(msg.type==='room_status'){
      status.value = msg
    }else if(msg.type==='ready_status'){
      readyStatus.value = msg.ready
    }else if(msg.type==='game_started'){
      gameResult.value = null
      events.value = []
      actions.value = []
      gameInProgress.value = true
      readyStatus.value = null
    }else if(msg.type==='you_are'){
      // 同步你和对方可见面板
      opponent.value = msg.opponent
      hand.value = msg.hand || []
      meldsSelf.value = msg.melds_self || []
      meldsOpp.value = msg.melds_opp || []
      oppHandCount.value = typeof msg.opp_hand_count === 'number' ? msg.opp_hand_count : oppHandCount.value
      discSelf.value = msg.discards_self || []
      discOpp.value = msg.discards_opp || []
    }else if(msg.type==='sync_hand'){
      hand.value = msg.hand || []
    }else if(msg.type==='sync_view'){
      hand.value = msg.hand || []
      meldsSelf.value = msg.melds_self || []
      meldsOpp.value = msg.melds_opp || []
      oppHandCount.value = typeof msg.opp_hand_count === 'number' ? msg.opp_hand_count : oppHandCount.value
      discSelf.value = msg.discards_self || []
      discOpp.value = msg.discards_opp || []
    }else if(msg.type==='choices'){
      actions.value = msg.actions || []
    }else if(msg.type==='event'){
      events.value.push(msg.ev)
      // 简单可见区同步（弃牌、碰杠后无需复杂刷新）
      const evv = msg.ev
      if(evv.type==='discard'){
        if(evv.seat===seat.value){
          discSelf.value = [...discSelf.value, evv.tile]
        } else {
          discOpp.value = [...discOpp.value, evv.tile]
          oppHandCount.value = Math.max(0, oppHandCount.value - 1)
        }
      }
      if(evv.type==='draw'){
        if(evv.seat===seat.value){
          lastDrawnIndex.value = null
          pendingDrawTile.value = typeof evv.tile === 'number' ? evv.tile : null
        } else {
          oppHandCount.value = Math.min(14, oppHandCount.value + 1)
        }
      } else {
        lastDrawnIndex.value = null
        pendingDrawTile.value = null
      }
    }else if(msg.type==='game_end'){
      gameResult.value = msg.result
      actions.value = []
      oppHandCount.value = 13
      gameInProgress.value = false
      readyStatus.value = null
    }else if(msg.type==='error'){
      alert(`错误：${msg.detail}`)
    }
  }
  ws.value.onclose = () => {
    connected.value=false
    ws.value=null
    gameInProgress.value = false
    oppHandCount.value = 13
    readyStatus.value = null
  }
}

function ready(){
  if (!connected.value || isReady.value) return
  send({type:"ready"})
}

function selectTile(index:number){
  const tile = hand.value[index]
  if(tile === undefined) return
  const canDiscardTile = discardActions.value.some((a: Action) => a.tile === tile)
  if(!canDiscardTile){
    selectedHandIndex.value = null
    return
  }
  if(selectedHandIndex.value === index){
    selectedHandIndex.value = null
    return
  }
  selectedHandIndex.value = index
}

function confirmDiscard(){
  const action = selectedDiscardAction.value
  if(!action) return
  doAction(action)
}

function doAction(a:Action){
  send({type:"act", action: a})
}

function send(obj:any){
  ws.value?.send(JSON.stringify(obj))
}

function findAddedIndex(newHand:number[], oldHand:number[]): number {
  const counts = new Map<number, number>()
  for (const tile of oldHand) {
    counts.set(tile, (counts.get(tile) ?? 0) + 1)
  }
  for (let i = 0; i < newHand.length; i++) {
    const tile = newHand[i]!
    const remaining = counts.get(tile) ?? 0
    if (remaining === 0) {
      return i
    }
    counts.set(tile, remaining - 1)
  }
  return -1
}

function findAddedIndexForTile(newHand:number[], oldHand:number[], tile:number): number {
  let toSkip = 0
  for (const t of oldHand) {
    if (t === tile) {
      toSkip += 1
    }
  }
  for (let i = 0; i < newHand.length; i++) {
    const current = newHand[i]!
    if (current !== tile) continue
    if (toSkip === 0) {
      return i
    }
    toSkip -= 1
  }
  return -1
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
  align-items: flex-start;
  padding: 48px 16px 64px;
  box-sizing: border-box;
}

.game-card {
  width: 100%;
  max-width: 1100px;
  background: rgba(15, 21, 34, 0.82);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(120, 165, 255, 0.25);
  border-radius: 24px;
  padding: 32px;
  box-shadow: 0 24px 50px rgba(0, 0, 0, 0.35);
}

.game-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 28px;
}

.title-block h1 {
  margin: 0;
  font-size: 2.2rem;
  letter-spacing: 0.04em;
}

.subtitle {
  margin: 6px 0 0;
  color: #b7c8ff;
  font-size: 0.95rem;
}

.header-status {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: right;
  font-size: 0.95rem;
  color: #d6e0ff;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  box-shadow: 0 0 12px currentColor;
}

.status-dot.online {
  color: #5bf27a;
  background: #5bf27a;
}

.status-dot.offline {
  color: #ff6b6b;
  background: #ff6b6b;
}

.connection-card {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  background: linear-gradient(135deg, rgba(33, 42, 70, 0.9), rgba(22, 30, 54, 0.9));
  padding: 20px;
  border-radius: 18px;
  border: 1px solid rgba(108, 138, 229, 0.35);
  margin-bottom: 24px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-group label {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #8fa5ff;
}

.field-group input {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(143, 165, 255, 0.45);
  background: rgba(13, 20, 36, 0.72);
  color: #f5f7ff;
}

.field-group input::placeholder {
  color: rgba(193, 205, 255, 0.4);
}

.action-group {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.action-group button {
  padding: 10px 18px;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  font-weight: 600;
  letter-spacing: 0.03em;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.action-group button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.ready-button {
  background: linear-gradient(135deg, #ff9559, #ff4b5c);
  color: #ffffff;
  box-shadow: 0 14px 28px rgba(255, 112, 92, 0.35);
}

.ready-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 16px 32px rgba(255, 102, 82, 0.45);
}

.ready-button.ready {
  background: linear-gradient(135deg, #45d07d, #24a65a);
  box-shadow: 0 12px 26px rgba(58, 197, 120, 0.4);
}

.ready-button.ready:disabled {
  opacity: 1;
  cursor: default;
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

.secondary {
  background: rgba(16, 29, 60, 0.85);
  color: #baceff;
  border: 1px solid rgba(97, 127, 211, 0.6);
}

.secondary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(28, 46, 94, 0.5);
}

.board {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-top: 24px;
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
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  width: 100%;
  padding-right: 8px;
  overflow-x: auto;
  overscroll-behavior-x: contain;
}

.hand-opponent {
  justify-content: flex-start;
  gap: 8px;
  padding-right: 8px;
  overflow-x: auto;
  overscroll-behavior-x: contain;
}

.hand-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.hint {
  font-size: 0.8rem;
  color: rgba(181, 198, 255, 0.7);
}

.hand-row {
  align-items: flex-start;
}

.tile {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  min-width: 46px;
  height: 76px;
  padding: 0 8px;
  border-radius: 12px;
  border: 2px solid rgba(223, 235, 255, 0.18);
  background: linear-gradient(180deg, #ffffff 0%, #f9f6ef 52%, #f0ede6 100%);
  box-shadow: 0 16px 24px rgba(5, 9, 18, 0.45);
  color: #1a2436;
  font-weight: 700;
  letter-spacing: 0.03em;
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border 0.16s ease;
}

.tile-hidden {
  padding: 0;
  border: none;
  background: none;
  box-shadow: none;
  color: transparent;
  pointer-events: none;
}

.tile-hidden::before {
  content: none;
}

.hand-opponent .tile {
  flex: 0 0;
}


.tile::before {
  content: '';
  position: absolute;
  inset: 4px;
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.85), rgba(211, 220, 245, 0.45));
  pointer-events: none;
  z-index: 0;
}

.tile:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 30px rgba(9, 16, 32, 0.6);
}

.tile.selected {
  border-color: rgba(104, 140, 255, 0.9);
  box-shadow: 0 22px 32px rgba(54, 90, 255, 0.48);
}

.tile.drawn {
  border-color: rgba(255, 207, 64, 0.9);
  box-shadow: 0 24px 36px rgba(255, 178, 45, 0.55);
}

.tile.drawn::before {
  background: linear-gradient(180deg, rgba(255, 247, 214, 0.95), rgba(255, 221, 150, 0.6));
}

.tile-small {
  min-width: 46px;
  height: 64px;
  font-size: 0.85rem;
  box-shadow: 0 12px 18px rgba(5, 9, 18, 0.4);
}

.tile-small::before {
  inset: 3px;
}

.tile-face {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.tile-small .tile-face {
  transform: scale(0.95);
}

.meld-chip {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(101, 130, 255, 0.2);
  color: #d6e3ff;
  font-size: 0.9rem;
  letter-spacing: 0.04em;
}

.tile-row {
  align-items: center;
}

.muted {
  color: rgba(176, 190, 235, 0.6);
}

.action-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.action-grid button {
  padding: 10px 20px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #4f6ef7, #6093ff);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
  letter-spacing: 0.05em;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.action-grid button:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 26px rgba(84, 118, 255, 0.45);
}

.action-grid .discard-action {
  background: linear-gradient(135deg, #ff6b5f, #ff445a);
  box-shadow: 0 12px 24px rgba(255, 81, 102, 0.45);
}

.action-grid .discard-action:hover:enabled {
  box-shadow: 0 16px 30px rgba(255, 81, 102, 0.55);
}

.action-grid .discard-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

@media (max-width: 860px) {
  .game-card {
    padding: 24px;
  }

  .game-header {
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
  }

  .header-status {
    width: 100%;
    text-align: left;
    align-items: flex-start;
  }

  .status-line {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .board {
    grid-template-columns: 1fr;
  }

  .label {
    flex-basis: 54px;
    font-size: 0.85rem;
  }

  .tile {
    min-width: 48px;
    height: 72px;
  }
}
</style>
