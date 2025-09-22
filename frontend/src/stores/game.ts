import { computed, ref, watch } from 'vue'

export type Action = { type: string; tile?: number; style?: string }
export type Meld = { kind: string; tiles: number[] }

const nickname = ref('A')
const roomId = ref('room1')
const ws = ref<WebSocket | null>(null)
const connected = ref(false)

const seat = ref<number | null>(null)
const opponent = ref('')
const status = ref<any>({})
const readyStatus = ref<any>(null)

const hand = ref<number[]>([])
const meldsSelf = ref<Meld[]>([])
const meldsOpp = ref<Meld[]>([])
const discSelf = ref<number[]>([])
const discOpp = ref<number[]>([])
const oppHandCount = ref(13)

const actions = ref<Action[]>([])
const events = ref<any[]>([])
const gameResult = ref<any | null>(null)

const selectedHandIndex = ref<number | null>(null)
const lastDrawnIndex = ref<number | null>(null)
const pendingDrawTile = ref<number | null>(null)
const gameInProgress = ref(false)

const discardActions = computed(() => actions.value.filter((a) => a.type === 'discard'))
const visibleActions = computed(() => actions.value.filter((a) => a.type !== 'discard'))
const selectedTileValue = computed(() => (selectedHandIndex.value !== null ? hand.value[selectedHandIndex.value] : null))
const selectedDiscardAction = computed(() => {
  if (selectedTileValue.value === null) return null
  return discardActions.value.find((a) => a.tile === selectedTileValue.value) || null
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

const suitAssetCodes = ['m', 's', 'p'] as const

function tileImage(t: number) {
  if (!Number.isFinite(t) || t < 0) return ''
  const rank = (t % 9) + 1
  const suitIndex = Math.floor(t / 9)
  const suitCode = suitAssetCodes[suitIndex] ?? 'm'
  return `/static/f${rank}${suitCode}.png`
}

const tileBackImage = '/static/flat_back.png'

watch(
  hand,
  (newHand, oldHand) => {
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

    if (selectedHandIndex.value === null) return
    if (newHand.length === 0 || selectedHandIndex.value >= newHand.length) {
      selectedHandIndex.value = null
    }
  }
)

watch(discardActions, (newActions) => {
  if (selectedHandIndex.value === null) return
  if (!newActions.length) {
    selectedHandIndex.value = null
    return
  }
  const tile = selectedTileValue.value
  if (tile === null) {
    selectedHandIndex.value = null
    return
  }
  const stillAllowed = newActions.some((a) => a.tile === tile)
  if (!stillAllowed) {
    selectedHandIndex.value = null
  }
})

function t2s(t: number) {
  const suit = ['万', '条', '筒'][Math.floor(t / 9)]
  const r = (t % 9) + 1
  return `${r}${suit}`
}
function kindText(kind: string) {
  switch (kind) {
    case 'pong':
    case 'peng':
      return '碰'
    case 'chow':
      return '吃'
    case 'kong_concealed':
      return '暗杠'
    case 'kong_added':
      return '加杠'
    case 'kong_exposed':
      return '明杠'
    case 'kong':
      return '杠'
    case 'hu':
      return '胡'
    default:
      if (kind.startsWith('kong')) return '杠'
      return kind
  }
}
function meldKindClass(kind: string) {
  if (kind === 'pong' || kind === 'peng') return 'meld-card--pong'
  if (kind === 'chow') return 'meld-card--chow'
  if (kind === 'kong' || kind.startsWith('kong_')) return 'meld-card--kong'
  if (kind === 'hu') return 'meld-card--hu'
  return 'meld-card--other'
}
function kongStyleText(style: string | undefined): string {
  if (style === 'concealed') return '暗杠'
  if (style === 'exposed') return '明杠'
  if (style === 'added') return '加杠'
  return '杠'
}
function actText(a: Action) {
  if (a.type === 'discard') return `打出 ${t2s(a.tile ?? -1)}`
  if (a.type === 'draw') return '摸牌'
  if (a.type === 'peng' || a.type === 'pong') return `碰 ${t2s(a.tile ?? -1)}`
  if (a.type === 'kong') return `${kongStyleText(a.style)} ${t2s(a.tile ?? -1)}`
  if (a.type === 'hu') return a.style === 'self' ? '自摸胡' : `荣和 ${t2s(a.tile ?? -1)}`
  if (a.type === 'pass') return '过'
  return JSON.stringify(a)
}

function connect() {
  if (ws.value) return
  ws.value = new WebSocket(`ws://127.0.0.1:8000/ws`)
  ws.value.onopen = () => {
    connected.value = true
    send({ type: 'join_room', room_id: roomId.value, nickname: nickname.value })
  }
  ws.value.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.type === 'room_joined') {
      seat.value = msg.seat
    } else if (msg.type === 'room_status') {
      status.value = msg
    } else if (msg.type === 'ready_status') {
      readyStatus.value = msg.ready
    } else if (msg.type === 'game_started') {
      gameResult.value = null
      events.value = []
      actions.value = []
      gameInProgress.value = true
      readyStatus.value = null
    } else if (msg.type === 'you_are') {
      opponent.value = msg.opponent
      hand.value = msg.hand || []
      meldsSelf.value = msg.melds_self || []
      meldsOpp.value = msg.melds_opp || []
      oppHandCount.value = typeof msg.opp_hand_count === 'number' ? msg.opp_hand_count : oppHandCount.value
      discSelf.value = msg.discards_self || []
      discOpp.value = msg.discards_opp || []
    } else if (msg.type === 'sync_hand') {
      hand.value = msg.hand || []
    } else if (msg.type === 'sync_view') {
      hand.value = msg.hand || []
      meldsSelf.value = msg.melds_self || []
      meldsOpp.value = msg.melds_opp || []
      oppHandCount.value = typeof msg.opp_hand_count === 'number' ? msg.opp_hand_count : oppHandCount.value
      discSelf.value = msg.discards_self || []
      discOpp.value = msg.discards_opp || []
    } else if (msg.type === 'choices') {
      actions.value = msg.actions || []
    } else if (msg.type === 'event') {
      events.value.push(msg.ev)
      const evv = msg.ev
      if (evv.type === 'discard') {
        if (evv.seat === seat.value) {
          discSelf.value = [...discSelf.value, evv.tile]
        } else {
          discOpp.value = [...discOpp.value, evv.tile]
          oppHandCount.value = Math.max(0, oppHandCount.value - 1)
        }
      }
      if (evv.type === 'draw') {
        if (evv.seat === seat.value) {
          lastDrawnIndex.value = null
          pendingDrawTile.value = typeof evv.tile === 'number' ? evv.tile : null
        } else {
          oppHandCount.value = Math.min(14, oppHandCount.value + 1)
        }
      } else {
        lastDrawnIndex.value = null
        pendingDrawTile.value = null
      }
    } else if (msg.type === 'game_end') {
      gameResult.value = msg.result
      actions.value = []
      oppHandCount.value = 13
      gameInProgress.value = false
      readyStatus.value = null
    } else if (msg.type === 'error') {
      alert(`错误：${msg.detail}`)
    }
  }
  ws.value.onclose = () => {
    connected.value = false
    ws.value = null
    gameInProgress.value = false
    oppHandCount.value = 13
    readyStatus.value = null
  }
}

function ready() {
  if (!connected.value || isReady.value) return
  send({ type: 'ready' })
}

function selectTile(index: number) {
  const tile = hand.value[index]
  if (tile === undefined) return
  const canDiscardTile = discardActions.value.some((a) => a.tile === tile)
  if (!canDiscardTile) {
    selectedHandIndex.value = null
    return
  }
  if (selectedHandIndex.value === index) {
    selectedHandIndex.value = null
    return
  }
  selectedHandIndex.value = index
}

function confirmDiscard() {
  const action = selectedDiscardAction.value
  if (!action) return
  doAction(action)
}

function doAction(a: Action) {
  send({ type: 'act', action: a })
}

function send(obj: any) {
  ws.value?.send(JSON.stringify(obj))
}

function disconnect() {
  ws.value?.close()
}

function resetState() {
  disconnect()
  nickname.value = 'A'
  roomId.value = 'room1'
  connected.value = false
  seat.value = null
  opponent.value = ''
  status.value = {}
  readyStatus.value = null
  hand.value = []
  meldsSelf.value = []
  meldsOpp.value = []
  discSelf.value = []
  discOpp.value = []
  oppHandCount.value = 13
  actions.value = []
  events.value = []
  gameResult.value = null
  selectedHandIndex.value = null
  lastDrawnIndex.value = null
  pendingDrawTile.value = null
  gameInProgress.value = false
}

function findAddedIndex(newHand: number[], oldHand: number[]): number {
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

function findAddedIndexForTile(newHand: number[], oldHand: number[], tile: number): number {
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

export function useGameStore() {
  return {
    nickname,
    roomId,
    ws,
    connected,
    seat,
    opponent,
    status,
    readyStatus,
    hand,
    meldsSelf,
    meldsOpp,
    discSelf,
    discOpp,
    oppHandCount,
    actions,
    events,
    gameResult,
    selectedHandIndex,
    lastDrawnIndex,
    pendingDrawTile,
    gameInProgress,
    discardActions,
    visibleActions,
    selectedTileValue,
    selectedDiscardAction,
    canDiscardSelected,
    showActionFooter,
    onlineSummary,
    readySummary,
    isReady,
    oppHandPlaceholders,
    tileImage,
    tileBackImage,
    t2s,
    kindText,
    meldKindClass,
    kongStyleText,
    actText,
    connect,
    ready,
    selectTile,
    confirmDiscard,
    doAction,
    send,
    disconnect,
    resetState,
  }
}
