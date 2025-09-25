import { computed, ref, watch } from 'vue'

export type User = {
  id: number
  username: string
  score: number
}

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
  score_unit: string
  net_score: number
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

// 从localStorage恢复用户信息和房间信息
const savedUser = typeof localStorage !== 'undefined' ? localStorage.getItem('mahjong_user') : null
const savedRoomId = typeof localStorage !== 'undefined' ? localStorage.getItem('mahjong_room_id') : 'room1'

const user = ref<User | null>(savedUser ? (JSON.parse(savedUser) as User) : null)
const username = ref(user.value?.username || '')
const nickname = ref(user.value?.username || '')

watch(username, (newUsername) => {
  nickname.value = newUsername
})
const userScore = ref(user.value?.score || 1000)
const roomId = ref(savedRoomId || 'room1')
const ws = ref<WebSocket | null>(null)
const connected = ref(false)
const autoReadyRequested = ref(false)

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
  return players.map((p: boolean, idx: number) => {
    const label = idx === seat.value ? '我方' : '对方'
    return `${label}：${p ? '在线' : '离线'}`
  }).join('｜')
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
    score_unit: '点',
    net_score: 0,
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

const suitAssetCodes = ['m', 's', 'p', 'z'] as const

function tileImage(t: TileValue) {
  if (typeof t !== 'number' || !Number.isFinite(t) || t < 0) return ''

  // For regular suits (m/s/p): tiles 0-26 (0-8: m, 9-17: s, 18-26: p)
  // For honor suit (z): tiles 27-33 (1-7: z)
  if (t < 27) {
    const rank = t % 9
    const suitIndex = Math.floor(t / 9)
    const suitCode = suitAssetCodes[suitIndex] ?? 'm'
    return `/f${rank + 1}${suitCode}.png`
  } else {
    // Honor tiles
    const rank = (t - 27) + 1  // 1-7
    return `/f${rank}z.png`
  }
}

const tileBackImage = '/flat_back.png'

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

function resolveWebSocketUrl(auth: boolean = true): string {
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl && envUrl.trim().length > 0) {
    const trimmed = envUrl.trim()
    if (!auth) return trimmed

    // Ensure authenticated websocket URLs include the /auth suffix
    if (trimmed.endsWith('/auth')) return trimmed
    if (trimmed.endsWith('/')) return `${trimmed}auth`
    return `${trimmed}/auth`
  }

  if (typeof window === 'undefined') {
    return `ws://127.0.0.1:8000/ws${auth ? '/auth' : ''}`
  }

  const { protocol, hostname, port } = window.location
  const wsProtocol = protocol === 'https:' ? 'wss' : 'ws'
  const formatHost = (host: string) => (host.includes(':') && !host.startsWith('[') ? `[${host}]` : host)
  const safeHost = formatHost(hostname)

  if (import.meta.env.DEV) {
    return `${wsProtocol}://${safeHost}:8000/ws${auth ? '/auth' : ''}`
  }

  const portSegment = port ? `:${port}` : ''
  return `${wsProtocol}://${safeHost}${portSegment}/ws${auth ? '/auth' : ''}`
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

function saveRoomInfo() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('mahjong_room_id', roomId.value)
  }
}

function clearRoomInfo() {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('mahjong_room_id')
  }
}

function setUser(newUser: User | null) {
  user.value = newUser

  if (newUser) {
    username.value = newUser.username
    nickname.value = newUser.username
    userScore.value = typeof newUser.score === 'number' ? newUser.score : 1000

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('mahjong_user', JSON.stringify(newUser))
      localStorage.setItem('mahjong_logged_in', 'true')
    }
  } else {
    username.value = ''
    nickname.value = ''
    userScore.value = 1000

    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('mahjong_user')
      localStorage.removeItem('mahjong_logged_in')
    }
  }
}

function saveUserInfo() {
  if (user.value) {
    setUser({ ...user.value })
  }
}

function clearUserInfo() {
  setUser(null)
}

function attemptAutoReady() {
  if (!autoReadyRequested.value) return
  if (!connected.value) return
  if (isReady.value) {
    autoReadyRequested.value = false
    return
  }
  if (seat.value === null) return
  ready()
}

function connect() {
  if (ws.value) return
  if (!user.value) {
    console.error('用户未登录，无法连接')
    return
  }

  ws.value = new WebSocket(resolveWebSocketUrl(true))
  ws.value.onopen = () => {
    // 先进行用户认证
    const savedUser = localStorage.getItem('mahjong_user')
    if (savedUser) {
      const userData = JSON.parse(savedUser)
      send({
        type: 'authenticate',
        username: userData.username,
        password: userData.username // 密码与用户名相同
      })
    }
  }
  ws.value.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.type === 'authentication_success') {
      // 认证成功，更新用户信息
      setUser(msg.user)
      connected.value = true
      saveRoomInfo()
      // 认证成功后加入房间
      send({ type: 'join_room', room_id: roomId.value })
    } else if (msg.type === 'room_joined') {
      seat.value = msg.seat
      attemptAutoReady()
    } else if (msg.type === 'room_status') {
      status.value = msg
    } else if (msg.type === 'ready_status') {
      readyStatus.value = msg.ready
      if (isReady.value) {
        autoReadyRequested.value = false
      } else {
        attemptAutoReady()
      }
    } else if (msg.type === 'game_started') {
      gameResult.value = null
      events.value = []
      actions.value = []
      gameInProgress.value = true
      readyStatus.value = null
      finalView.value = null
    } else if (msg.type === 'you_are') {
      opponent.value = msg.opponent
      username.value = msg.username
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
      // 更新对手名字
      if (msg.opponent) {
        opponent.value = msg.opponent
      }
      // 如果接收到 sync_view 消息，说明有游戏状态，设置为游戏进行中
      gameInProgress.value = true
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
      if (msg.detail.includes('用户名已被') || msg.detail.includes('请先登录')) {
        // 用户名被占用或未登录，清除本地存储的房间信息
        clearRoomInfo()
        resetState()
      }
    } else if (msg.type === 'player_kicked') {
      alert(`您被踢出房间，因为有其他玩家用了相同名字"${msg.username}"`)
      clearRoomInfo()
      connected.value = false
      ws.value = null
      gameInProgress.value = false
      readyStatus.value = null
      seat.value = null
    } else if (msg.type === 'player_disconnected') {
      // 可以在这里添加掉线提示
      console.log(`玩家 ${msg.username} 掉线了`)
    } else if (msg.type === 'player_reconnected') {
      // 可以在这里添加重连提示
      console.log(`玩家 ${msg.username} 重新连接了`)
    } else if (msg.type === 'mutual_replacement_completed') {
      // 双方相互顶替重连完成
      console.log('双方相互顶替重连完成，座位和手牌已交换')
      // 座位和手牌交换会在 sync_view 消息中自动处理
    }
  }
  ws.value.onclose = () => {
    connected.value = false
    ws.value = null
    gameInProgress.value = false
    oppHandCount.value = 13
    readyStatus.value = null
    autoReadyRequested.value = false
  }
}

function ready() {
  if (!connected.value) return
  if (isReady.value) {
    autoReadyRequested.value = false
    return
  }
  autoReadyRequested.value = false
  send({ type: 'ready' })
}

function joinAndReady() {
  if (isReady.value) {
    autoReadyRequested.value = false
    return
  }
  if (!connected.value) {
    autoReadyRequested.value = true
    connect()
    return
  }
  ready()
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
  username.value = user.value?.username || ''
  nickname.value = user.value?.username || ''
  roomId.value = 'room1'
  connected.value = false
  seat.value = null
  opponent.value = ''
  status.value = {}
  readyStatus.value = null
  autoReadyRequested.value = false
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
    user,
    username,
    nickname,
    userScore,
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
    joinAndReady,
    selectTile,
    confirmDiscard,
    doAction,
    send,
    disconnect,
    resetState,
    saveRoomInfo,
    clearRoomInfo,
    setUser,
    saveUserInfo,
    clearUserInfo,
  }
}
