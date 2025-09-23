import { computed, ref, watch } from 'vue'

export type Action = { type: string; tile?: number; style?: string }
export type TileValue = number | null
export type Meld = { kind: string; tiles: TileValue[] }

export type FanBreakdownItem = { name: string; fan: number; detail?: string }
export type FanPlayerScore = {
  fan_total: number
  fan_breakdown: FanBreakdownItem[]
  net_change: number
}
export type FanSummary = {
  fan_unit: string
  net_fan: number
  players: Record<string, FanPlayerScore>
}

type FinalSeatView = {
  hand: number[]
  melds: Meld[]
  discards: number[]
}

type FinalViewPayload = {
  players: Record<string, FinalSeatView>
  wall_remaining?: number[]
}

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
const finalView = ref<FinalViewPayload | null>(null)

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

const liveFanSummary = computed<FanSummary>(() => {
  const players: Record<string, FanPlayerScore> = {
    '0': { fan_total: 0, fan_breakdown: [], net_change: 0 },
    '1': { fan_total: 0, fan_breakdown: [], net_change: 0 },
  }

  const seatValue = seat.value
  const seats = [0, 1] as const

  for (const seatId of seats) {
    let melds: Meld[] = []

    if (seatValue === null) {
      melds = seatId === 0 ? meldsSelf.value : meldsOpp.value
    } else if (seatId === seatValue) {
      melds = meldsSelf.value
    } else if (seatId === 1 - seatValue) {
      melds = meldsOpp.value
    }

    const entry = players[String(seatId)]
    if (!entry) continue

    // 杠的番数（每个杠1番）
    const counts = collectMeldKindCounts(melds)
    const totalKongs = (counts['kong_exposed'] ?? 0) + (counts['kong_concealed'] ?? 0) + (counts['kong_added'] ?? 0)
    if (totalKongs > 0) {
      addFanSummaryEntry(entry, '杠', totalKongs, `${totalKongs}个杠，每个+1番`)
    }
  }

  const seat0Entry = players['0']
  const seat1Entry = players['1']
  const seat0Total = seat0Entry?.fan_total ?? 0
  const seat1Total = seat1Entry?.fan_total ?? 0
  let netFan = seat0Total - seat1Total
  if (netFan < 0) netFan = 0
  if (seat0Entry) seat0Entry.net_change = netFan
  if (seat1Entry) seat1Entry.net_change = -netFan

  return {
    fan_unit: '番',
    net_fan: netFan,
    players,
  }
})

const finalHandSelf = computed<number[]>(() => {
  if (!finalView.value || seat.value === null) return []
  const entry = finalView.value.players[String(seat.value)]
  return entry?.hand ?? []
})

const finalHandOpp = computed<number[]>(() => {
  if (!finalView.value || seat.value === null) return []
  const oppSeat = 1 - seat.value
  const entry = finalView.value.players[String(oppSeat)]
  return entry?.hand ?? []
})

const finalMeldsSelf = computed<Meld[]>(() => {
  if (!finalView.value || seat.value === null) return []
  const entry = finalView.value.players[String(seat.value)]
  return entry?.melds ?? []
})

const finalMeldsOpp = computed<Meld[]>(() => {
  if (!finalView.value || seat.value === null) return []
  const oppSeat = 1 - seat.value
  const entry = finalView.value.players[String(oppSeat)]
  return entry?.melds ?? []
})

const suitAssetCodes = ['m', 's', 'p'] as const

function tileImage(t: TileValue) {
  if (typeof t !== 'number' || !Number.isFinite(t) || t < 0) return ''
  const rank = (t % 9) + 1
  const suitIndex = Math.floor(t / 9)
  const suitCode = suitAssetCodes[suitIndex] ?? 'm'
  return `/static/f${rank}${suitCode}.png`
}

const tileBackImage = '/static/flat_back.png'

function collectMeldKindCounts(melds: Meld[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const meld of melds) {
    const key = meld?.kind
    if (!key) continue
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
}

function addFanSummaryEntry(entry: FanPlayerScore, name: string, fan: number, detail?: string) {
  if (!Number.isFinite(fan) || fan === 0) return
  const payload: FanBreakdownItem = { name, fan }
  if (detail) payload.detail = detail
  entry.fan_breakdown.push(payload)
  entry.fan_total += fan
}

function resolveWebSocketUrl(): string {
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl
  }

  if (typeof window === 'undefined') {
    return 'ws://127.0.0.1:8000/ws'
  }

  const { protocol, hostname, port } = window.location
  const wsProtocol = protocol === 'https:' ? 'wss' : 'ws'
  const formatHost = (host: string) => (host.includes(':') && !host.startsWith('[') ? `[${host}]` : host)
  const safeHost = formatHost(hostname)

  if (import.meta.env.DEV) {
    return `${wsProtocol}://${safeHost}:8000/ws`
  }

  const portSegment = port ? `:${port}` : ''
  return `${wsProtocol}://${safeHost}${portSegment}/ws`
}

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

function t2s(t: TileValue) {
  if (typeof t !== 'number' || !Number.isFinite(t) || t < 0) return '未知'
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
  ws.value = new WebSocket(resolveWebSocketUrl())
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
      finalView.value = null
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
      if (evv.type === 'peng' || evv.type === 'pong') {
        if (evv.seat !== seat.value) {
          oppHandCount.value = Math.max(0, oppHandCount.value - 2)
        }
      }
      if (evv.type === 'kong') {
        if (evv.seat !== seat.value) {
          const deduction = evv.style === 'added' ? 1 : evv.style === 'concealed' ? 4 : 3
          oppHandCount.value = Math.max(0, oppHandCount.value - deduction)
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
      finalView.value = msg.final_view ?? null
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
  finalView.value = null
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
    finalView,
    finalHandSelf,
    finalHandOpp,
    finalMeldsSelf,
    finalMeldsOpp,
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
    liveFanSummary,
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
