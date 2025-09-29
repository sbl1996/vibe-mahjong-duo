# -*- coding: utf-8 -*-
# 最小规则核心：仅 3 门(万/条/筒) 1-9，共 27 种牌，每种 4 张 => 108 张
# 胡牌：经典四面子一将（允许暗顺子）。实现 碰/杠/胡 的基本合法性检查。
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import List, Tuple, Optional, Dict, Any, NamedTuple
import random
from functools import lru_cache

# 牌编码：0..26，0-8=万1..9，9-17=条1..9，18-26=筒1..9
TILE_TYPES = 27
COPIES_PER_TILE = 4
TOTAL_TILES = TILE_TYPES * COPIES_PER_TILE  # 108

def tile_to_str(t: int) -> str:
    suit = ["万","条","筒"][t // 9]
    rank = t % 9 + 1
    return f"{rank}{suit}"

def build_wall(seed: int) -> List[int]:
    rng = random.Random(seed)
    wall = []
    for i in range(TILE_TYPES):
        wall += [i] * COPIES_PER_TILE
    rng.shuffle(wall)
    return wall

@dataclass(frozen=True)
class Meld:
    kind: str            # "pong" | "kong_exposed" | "kong_concealed" | "kong_added"
    tiles: Tuple[int, ...]  # 三或四张同牌

@dataclass(frozen=True)
class PlayerState:
    hand: Tuple[int, ...]
    melds: Tuple[Meld, ...]
    discards: Tuple[int, ...]

@dataclass(frozen=True)
class GameState:
    seed: int
    wall: Tuple[int, ...]
    players: Tuple[PlayerState, PlayerState]
    turn: int                        # 轮到谁（0/1）
    last_discard: Optional[Tuple[int,int]] = None  # (seat, tile)
    step_no: int = 0
    started: bool = False
    ended: bool = False
    pending_kong_draw: Optional[int] = None          # 谁需要补杠牌
    last_draw_info: Optional[Tuple[int, str]] = None # (seat, draw_type)
    pending_rob_kong: Optional[Tuple[int, int]] = None  # (kong_owner, tile)

def sort_hand(arr: List[int]) -> List[int]:
    return sorted(arr)

def init_game(seed: int, *, first_turn: int = 0) -> GameState:
    wall = build_wall(seed)
    # 发牌：双方各13张（末尾为庄家先摸）
    p0 = sort_hand(wall[:13]); p1 = sort_hand(wall[13:26])
    wall_ptr = 26
    players = (
        PlayerState(tuple(p0), tuple(), tuple()),
        PlayerState(tuple(p1), tuple(), tuple()),
    )
    if first_turn not in (0, 1):
        raise ValueError("first_turn must be 0 or 1")
    return GameState(seed=seed, wall=tuple(wall[wall_ptr:]), players=players, turn=first_turn, started=True)

def counts_from_tiles(tiles: Tuple[int, ...]) -> Tuple[int, ...]:
    c = [0]*TILE_TYPES
    for t in tiles: c[t]+=1
    return tuple(c)

def can_peng(hand: Tuple[int,...], tile: int) -> bool:
    return hand.count(tile) >= 2

def can_kong_exposed(hand: Tuple[int,...], tile: int) -> bool:
    # 明杠（吃对家弃牌），需要手里有三张
    return hand.count(tile) >= 3

def can_kong_concealed(hand: Tuple[int,...]) -> Optional[int]:
    # 暗杠（自手 4 张相同），返回可暗杠的 tile 或 None
    for i in range(TILE_TYPES):
        if hand.count(i) == 4: return i
    return None

def can_kong_added(melds: Tuple[Meld,...], hand: Tuple[int,...]) -> Optional[int]:
    # 加杠：已有刻子(pong) + 手牌再有1张
    for m in melds:
        if m.kind=="pong":
            t = m.tiles[0]
            if hand.count(t)>=1:
                return t
    return None

def _try_meld_triplet(counts: List[int], i: int) -> bool:
    if counts[i] >= 3:
        counts[i] -= 3
        return True
    return False

def _try_meld_sequence(counts: List[int], i: int) -> bool:
    # 仅 0..26 且同花顺：i,i+1,i+2 且不跨花色
    suit = i // 9
    r = i % 9
    if suit < 3 and r <= 6:
        if counts[i] > 0 and counts[i+1] > 0 and counts[i+2] > 0:
            counts[i]-=1; counts[i+1]-=1; counts[i+2]-=1
            return True
    return False

@lru_cache(maxsize=128)
def _can_form_melds(counts: Tuple[int,...], need: int) -> bool:
    if need==0:
        return sum(counts)==0
    # 找第一张
    try:
        i = next(k for k,c in enumerate(counts) if c>0)
    except StopIteration:
        return False
    arr = list(counts)
    # 刻子
    if _try_meld_triplet(arr, i):
        if _can_form_melds(tuple(arr), need-1): return True
        arr = list(counts)
    # 顺子
    if _try_meld_sequence(arr, i):
        if _can_form_melds(tuple(arr), need-1): return True
    return False

def can_hu_four_plus_one(tiles: Tuple[int,...], melds: Tuple[Meld, ...] = ()) -> bool:
    # tiles：手里剩余的未成面子牌（自摸时14-3*melds张，荣和时需将对家牌并入）
    if len(tiles) < 2:
        return False
    remaining = len(tiles) - 2
    if remaining % 3 != 0:
        return False
    need = remaining // 3
    if len(melds) + need != 4:
        return False
    c0 = counts_from_tiles(tiles)
    for i in range(TILE_TYPES):
        if c0[i] >= 2:
            arr = list(c0); arr[i]-=2
            if _can_form_melds(tuple(arr), need):
                return True
    return False

def draw(state: GameState, seat: int) -> Tuple[GameState, Optional[int]]:
    if not state.wall:
        return state, None
    tile = state.wall[0]
    new_wall = state.wall[1:]
    draw_type = "kong" if state.pending_kong_draw == seat else "normal"
    pending_kong_draw = state.pending_kong_draw
    if pending_kong_draw == seat:
        pending_kong_draw = None
    ps = list(state.players)
    phand = list(ps[seat].hand); phand.append(tile); phand = sort_hand(phand)
    ps[seat] = replace(ps[seat], hand=tuple(phand))
    st = replace(
        state,
        wall=new_wall,
        players=tuple(ps),
        last_discard=None,
        step_no=state.step_no+1,
        pending_kong_draw=pending_kong_draw,
        last_draw_info=(seat, draw_type),
    )
    return st, tile

def discard(state: GameState, seat: int, tile: int) -> GameState:
    ps = list(state.players)
    hand = list(ps[seat].hand)
    if tile not in hand:
        raise ValueError("ILLEGAL_DISCARD")
    hand.remove(tile)
    disc = list(ps[seat].discards); disc.append(tile)
    ps[seat] = replace(ps[seat], hand=tuple(hand), discards=tuple(disc))
    st = replace(
        state,
        players=tuple(ps),
        last_discard=(seat, tile),
        step_no=state.step_no+1,
        turn=1-seat,
        last_draw_info=None,
    )
    return st

def claim_peng(state: GameState, claimer: int, from_seat: int, tile: int) -> GameState:
    hand = list(state.players[claimer].hand)
    if hand.count(tile) < 2: raise ValueError("ILLEGAL_PENG")
    # 移除两张
    hand.remove(tile); hand.remove(tile)
    melds = list(state.players[claimer].melds)
    melds.append(Meld("pong", (tile, tile, tile)))
    ps = list(state.players)
    ps[claimer] = replace(ps[claimer], hand=tuple(sort_hand(hand)), melds=tuple(melds))
    # 从对方弃牌末尾删除该 tile（仅展示用）
    opp_disc = list(ps[from_seat].discards)
    if opp_disc and opp_disc[-1] == tile:
        opp_disc.pop()
        ps[from_seat] = replace(ps[from_seat], discards=tuple(opp_disc))
    st = replace(
        state,
        players=tuple(ps),
        last_discard=None,
        turn=claimer,
        step_no=state.step_no+1,
        last_draw_info=None,
    )
    return st

def claim_kong_exposed(state: GameState, claimer: int, from_seat: int, tile: int) -> GameState:
    hand = list(state.players[claimer].hand)
    if hand.count(tile) < 3: raise ValueError("ILLEGAL_KONG_EXPOSED")
    hand.remove(tile); hand.remove(tile); hand.remove(tile)
    melds = list(state.players[claimer].melds)
    melds.append(Meld("kong_exposed", (tile, tile, tile, tile)))
    ps = list(state.players)
    ps[claimer] = replace(ps[claimer], hand=tuple(sort_hand(hand)), melds=tuple(melds))
    opp_disc = list(ps[from_seat].discards)
    if opp_disc and opp_disc[-1] == tile:
        opp_disc.pop()
        ps[from_seat] = replace(ps[from_seat], discards=tuple(opp_disc))
    st = replace(
        state,
        players=tuple(ps),
        last_discard=None,
        turn=claimer,
        step_no=state.step_no+1,
        pending_kong_draw=claimer,
        last_draw_info=None,
    )
    return st

def kong_concealed(state: GameState, seat: int, tile: int) -> GameState:
    hand = list(state.players[seat].hand)
    if hand.count(tile) != 4: raise ValueError("ILLEGAL_KONG_CONCEALED")
    for _ in range(4): hand.remove(tile)
    melds = list(state.players[seat].melds)
    melds.append(Meld("kong_concealed", (tile, tile, tile, tile)))
    ps = list(state.players)
    ps[seat] = replace(ps[seat], hand=tuple(sort_hand(hand)), melds=tuple(melds))
    st = replace(
        state,
        players=tuple(ps),
        step_no=state.step_no+1,
        pending_kong_draw=seat,
        last_draw_info=None,
    )
    return st

def kong_added(state: GameState, seat: int, tile: int) -> GameState:
    # 将已有的 pong 升级为 kong_added，手里需要 1 张
    ps = list(state.players)
    hand = list(ps[seat].hand)
    if tile not in hand: raise ValueError("ILLEGAL_KONG_ADDED")
    new_melds = []
    upgraded = False
    for m in ps[seat].melds:
        if not upgraded and m.kind=="pong" and m.tiles[0]==tile:
            new_melds.append(Meld("kong_added", (tile, tile, tile, tile)))
            upgraded = True
        else:
            new_melds.append(m)
    if not upgraded: raise ValueError("NO_PONG_TO_UPGRADE")
    hand.remove(tile)
    ps[seat] = replace(ps[seat], hand=tuple(sort_hand(hand)), melds=tuple(new_melds))
    return replace(
        state,
        players=tuple(ps),
        step_no=state.step_no+1,
        pending_kong_draw=seat,
        last_draw_info=None,
    )


class AddedKongResult(NamedTuple):
    state: GameState
    rob_pending: bool


class RobKongHuResult(NamedTuple):
    state: GameState
    kong_owner: int
    tile: int


class RobKongPassResult(NamedTuple):
    state: GameState
    kong_owner: int
    tile: int


def prepare_added_kong(state: GameState, seat: int, tile: int) -> AddedKongResult:
    """尝试执行加杠，若对手可抢杠则挂起抢杠状态并返回 rob_pending=True。"""
    ps = state.players
    hand = ps[seat].hand
    if tile not in hand:
        raise ValueError("ILLEGAL_KONG_ADDED")
    has_pong = any(m.kind == "pong" and m.tiles and m.tiles[0] == tile for m in ps[seat].melds)
    if not has_pong:
        raise ValueError("NO_PONG_TO_UPGRADE")

    robber = 1 - seat
    opponent = ps[robber]
    merged = tuple(sorted(opponent.hand + (tile,)))
    if can_hu_four_plus_one(merged, opponent.melds):
        st = replace(
            state,
            pending_rob_kong=(seat, tile),
            turn=robber,
        )
        return AddedKongResult(st, True)

    return AddedKongResult(kong_added(state, seat, tile), False)


def resolve_rob_kong_hu(state: GameState, robber: int, tile: Optional[int] = None) -> RobKongHuResult:
    """抢杠胡：返回新的状态、杠主座位和胡的牌。"""
    if state.pending_rob_kong is None:
        raise ValueError("NO_PENDING_ROB_KONG")
    kong_owner, pending_tile = state.pending_rob_kong
    if robber != 1 - kong_owner:
        raise ValueError("NOT_ROBBER")
    win_tile = tile if tile is not None else pending_tile

    st = state
    players = list(st.players)

    owner_player = players[kong_owner]
    owner_hand = list(owner_player.hand)
    if win_tile in owner_hand:
        owner_hand.remove(win_tile)
        players[kong_owner] = replace(owner_player, hand=tuple(owner_hand))

    winner_player = players[robber]
    winner_hand = list(winner_player.hand)
    winner_hand.append(win_tile)
    winner_hand = sort_hand(winner_hand)
    players[robber] = replace(winner_player, hand=tuple(winner_hand))

    new_state = replace(
        st,
        players=tuple(players),
        pending_rob_kong=None,
        ended=True,
        turn=robber,
        last_discard=None,
        pending_kong_draw=None,
        last_draw_info=None,
    )

    return RobKongHuResult(new_state, kong_owner, win_tile)


def resolve_rob_kong_pass(state: GameState, robber: int) -> RobKongPassResult:
    """抢杠放弃后继续执行加杠，返回新状态与相关信息。"""
    if state.pending_rob_kong is None:
        raise ValueError("NO_PENDING_ROB_KONG")
    kong_owner, tile = state.pending_rob_kong
    if robber != 1 - kong_owner:
        raise ValueError("NOT_ROBBER")

    base_state = replace(state, pending_rob_kong=None, turn=kong_owner)
    try:
        new_state = kong_added(base_state, kong_owner, tile)
    except Exception:
        new_state = base_state

    return RobKongPassResult(new_state, kong_owner, tile)


def legal_choices(state: GameState, seat: int) -> List[Dict]:
    me = state.players[seat]
    choices = []
    if state.pending_rob_kong is not None:
        kong_owner, tile = state.pending_rob_kong
        robber = 1 - kong_owner
        if seat == robber:
            merged = tuple(sorted(me.hand + (tile,)))
            if can_hu_four_plus_one(merged, me.melds):
                choices.append({"type": "hu", "style": "rob", "tile": tile, "from": kong_owner})
            choices.append({"type": "pass"})
        return choices
    # 若刚摸到14张，检查自摸胡、暗杠/加杠、打出
    if state.last_discard is None and len(me.hand) % 3 == 2 and seat == state.turn:
        if can_hu_four_plus_one(me.hand, me.melds):
            choices.append({"type":"hu","style":"self"})
        kc = can_kong_concealed(me.hand)
        if kc is not None:
            choices.append({"type":"kong","style":"concealed","tile":kc})
        ka = can_kong_added(me.melds, me.hand)
        if ka is not None:
            choices.append({"type":"kong","style":"added","tile":ka})
        # 所有打出
        for t in sorted(set(me.hand)):
            choices.append({"type":"discard","tile":t})
        return choices

    # 对方打出后我方可荣和/碰/明杠/过
    if state.last_discard is not None:
        from_seat, tile = state.last_discard
        if from_seat != seat:
            # 荣和：手牌+对家弃张能胡
            merged = tuple(sorted(me.hand + (tile,)))
            if can_hu_four_plus_one(merged, me.melds):
                choices.append({"type":"hu","style":"ron","tile":tile})
            if can_peng(me.hand, tile):
                choices.append({"type":"peng","tile":tile})
            if can_kong_exposed(me.hand, tile):
                choices.append({"type":"kong","style":"exposed","tile":tile})
            choices.append({"type":"pass"})
            return choices
    # 轮到我但只有13张：应当去摸
    if seat == state.turn and len(me.hand)%3==1:
        choices.append({"type":"draw"})
    return choices


# 番数计算相关函数

def check_yakuman(hand: Tuple[int, ...], melds: Tuple[Meld, ...], reason: str) -> int:
    """检查役满，返回番数（8）或0"""
    # 四暗刻
    if is_four_concealed_triplets(hand, melds):
        return 8

    # 四杠
    if is_four_kongs(melds):
        return 8

    # 清幺九
    if is_all_terminals(hand, melds):
        return 8

    return 0


def get_yakuman_description(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> str:
    """获取役满描述"""
    if is_four_concealed_triplets(hand, melds):
        return "四暗刻"
    elif is_four_kongs(melds):
        return "四杠"
    elif is_all_terminals(hand, melds):
        return "清幺九"
    return "役满"


class DecompMeld(NamedTuple):
    kind: str         # "triplet" | "sequence"
    tiles: Tuple[int, ...]
    concealed: bool   # True=手内形成；False=副露/明刻


def _melds_from_exposed(melds: Tuple[Meld, ...]) -> List[DecompMeld]:
    out: List[DecompMeld] = []
    for m in melds:
        if m.kind in ("pong", "kong_exposed", "kong_added", "kong_concealed"):
            # 统一当作“刻子”用于对对胡/暗刻计数；暗杠视作 concealed
            concealed = (m.kind == "kong_concealed")
            out.append(DecompMeld("triplet", m.tiles[:3], concealed))
        else:
            # 理论上不会出现顺子的副露（你的规则没有“吃”顺子），这里保守忽略
            pass
    return out


@lru_cache(maxsize=None)
def _decompose_tiles_all(counts: Tuple[int, ...], melds_left: int, pair_used: bool
    ) -> Tuple[Tuple[Tuple[str, int], ...], ...]:

    # ✅ 先处理“成功终止”
    if melds_left == 0:
        return (tuple(),) if (pair_used and sum(counts) == 0) else tuple()

    if melds_left < 0:
        return tuple()

    total = sum(counts)

    # ✅ 强剪枝：手内总数必须 = 3*面子数 + (将是否已用 ? 0 : 2)
    needed = 3 * melds_left + (0 if pair_used else 2)
    if total != needed:
        return tuple()

    # ✅ 到这里 total 一定 >= 2，不必再做 total<2 的剪枝了

    # 找第一张有计数的牌
    try:
        i = next(k for k, c in enumerate(counts) if c > 0)
    except StopIteration:
        return tuple()

    res_set = set()

    # 1) 选“将”（只在还没用将时可选）
    if not pair_used:
        for j in range(i, TILE_TYPES):
            if counts[j] >= 2:
                arr = list(counts)
                arr[j] -= 2
                for sol in _decompose_tiles_all(tuple(arr), melds_left, True):
                    res_set.add(tuple(sorted(sol)))

    # 2) 刻子
    if counts[i] >= 3:
        arr = list(counts); arr[i] -= 3
        for sol in _decompose_tiles_all(tuple(arr), melds_left - 1, pair_used):
            res_set.add(tuple(sorted((('t', i),) + sol)))

    # 3) 顺子（不跨花色）
    suit = i // 9
    r = i % 9
    if r <= 6:
        i1, i2 = i + 1, i + 2
        if (i1 // 9) == suit and (i2 // 9) == suit and counts[i] and counts[i1] and counts[i2]:
            arr = list(counts)
            arr[i] -= 1; arr[i1] -= 1; arr[i2] -= 1
            for sol in _decompose_tiles_all(tuple(arr), melds_left - 1, pair_used):
                res_set.add(tuple(sorted((('s', i),) + sol)))

    return tuple(res_set)


# 把 ('t'/'s', idx) 方案转成 DecompMeld 列表（concealed=True）
def _expand_plan_to_melds(plan: Tuple[Tuple[str, int], ...]) -> List[DecompMeld]:
    out: List[DecompMeld] = []
    for kind, i in plan:
        if kind == 't':
            out.append(DecompMeld("triplet", (i, i, i), True))
        else:
            out.append(DecompMeld("sequence", (i, i + 1, i + 2), True))
    return out


# 真·全解 —— 返回所有不重复的 4 面子分解（含副露/杠）
def decompose_final_all(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> List[List[DecompMeld]]:
    """
    若 hand+melds 能胡：返回“所有不重复”的 4 面子分解（DecompMeld 列表），
    - 来自副露/杠：concealed = (kong_concealed 为 True，其余 False)
    - 来自手牌：concealed=True
    """
    if not can_hu_four_plus_one(hand, melds):
        return []

    exposed = _melds_from_exposed(melds)
    need_from_hand = 4 - len(exposed)
    if need_from_hand < 0:
        return []

    counts = counts_from_tiles(hand)

    # 生成所有“手内面子”方案（每个方案是若干 ('t'/'s', idx) 组成的元组，已去重）
    plans = _decompose_tiles_all(tuple(counts), need_from_hand, False)
    if not plans:
        # 特例：若副露已达4个，手牌只需是“将”（多种将的选择都对应相同的面子解）
        return [exposed] if len(exposed) == 4 else []

    out: List[List[DecompMeld]] = []
    for plan in plans:
        from_hand = _expand_plan_to_melds(plan)  # 全部 concealed=True
        combo = exposed + from_hand
        if len(combo) == 4:
            # 规范化后去重（按 kind, tiles 排序）
            out.append(combo)

    # 结果去重：把每个分解规范成可哈希的键
    def key(melds_list: List[DecompMeld]) -> Tuple:
        norm = []
        for m in melds_list:
            tag = 0 if m.kind == "triplet" else 1
            norm.append((tag, m.tiles))  # concealed 不影响“面子类型”的唯一性，这里只用于记分
        return tuple(sorted(norm))

    uniq = {}
    for sol in out:
        uniq[key(sol)] = sol  # 后者覆盖前者 OK（它们等价）

    # 保留 concealed 标记：副露/暗杠的 concealed 按 _melds_from_exposed 逻辑，手内恒 True
    return list(uniq.values())


def is_four_concealed_triplets(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    # 有任何明副露（碰/明杠/加杠）则直接不可能四暗刻
    if any(m.kind in ("pong", "kong_exposed", "kong_added") for m in melds):
        return False

    sols = decompose_final_all(hand, melds)
    # 只要存在一种分解：四个面子全是刻子，且全部 concealed=True（手内或暗杠）
    return any(
        len(sol) == 4 and all(m.kind == "triplet" and m.concealed for m in sol)
        for sol in sols
    )


def is_four_kongs(melds: Tuple[Meld, ...]) -> bool:
    """检查是否四杠"""
    if len(melds) != 4:
        return False

    kong_kinds = ["kong_exposed", "kong_concealed", "kong_added"]
    return all(meld.kind in kong_kinds for meld in melds)


def is_all_terminals(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """检查是否清幺九（只有1和9的牌）"""
    all_tiles = list(hand)
    for meld in melds:
        all_tiles.extend(meld.tiles)

    for tile in all_tiles:
        rank = tile % 9 + 1
        if rank not in [1, 9]:
            return False

    return True

def is_tanyao(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """断幺九（全2-8）"""
    all_tiles = list(hand)
    for m in melds:
        all_tiles.extend(m.tiles)
    if not all_tiles:
        return False
    for t in all_tiles:
        r = t % 9 + 1
        if r == 1 or r == 9:
            return False
    return True  # 全部是2-8

def is_menzen(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """检查是否门前清（没有碰、明杠；暗杠不破门清）"""
    for meld in melds:
        if meld.kind in ["pong", "kong_exposed", "kong_added"]:
            return False
    return True


def is_all_triplets(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """是否存在一种分解使四面子全为刻子"""
    sols = decompose_final_all(hand, melds)
    return any(len(sol) == 4 and all(m.kind == "triplet" for m in sol) for sol in sols)


def is_all_sequences(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """是否存在一种分解使四面子全为顺子（用于平和判定）"""
    sols = decompose_final_all(hand, melds)
    return any(len(sol) == 4 and all(m.kind == "sequence" for m in sol) for sol in sols)


def count_concealed_triplets(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> int:
    """
    统计“暗刻”数量：对所有可能分解取最大值（更符合三暗刻计番应取最优的直觉）。
    若不可胡，返回 0。
    """
    sols = decompose_final_all(hand, melds)
    if not sols:
        return 0
    return max(sum(1 for m in sol if m.kind == "triplet" and m.concealed) for sol in sols)


def is_full_flush(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """检查是否清一色"""
    all_tiles = list(hand)
    for meld in melds:
        all_tiles.extend(meld.tiles)

    if not all_tiles:
        return False

    # 检查是否所有牌都是同一花色
    first_suit = all_tiles[0] // 9
    return all(tile // 9 == first_suit for tile in all_tiles)


def count_kongs(melds: Tuple[Meld, ...]) -> int:
    """计算杠子数量"""
    kong_kinds = ["kong_exposed", "kong_concealed", "kong_added"]
    return sum(1 for meld in melds if meld.kind in kong_kinds)


def _add_fan(entry: Dict[str, Any], name: str, fan: int, detail: Optional[str] = None) -> None:
    item = {"name": name, "fan": fan}
    if detail:
        item["detail"] = detail
    entry.setdefault("fan_breakdown", []).append(item)
    entry["fan_total"] = entry.get("fan_total", 0) + fan


def fan_to_points(fan_total: int, base: int = 8) -> int:
    """根据番数计算积分变化"""
    fan_value = max(fan_total, 0)
    return base * (2 ** fan_value)


def compute_score_summary(
    state: GameState,
    winner: Optional[int],
    reason: str,
) -> Dict[str, Any]:
    player_scores: Dict[int, Dict[str, Any]] = {
        0: {"fan_total": 0, "fan_breakdown": []},
        1: {"fan_total": 0, "fan_breakdown": []},
    }

    yakuman_fan = 0  # 需要在后面给负番用

    if winner is not None:
        win_player = state.players[winner]

        # 检查役满
        yakuman_fan = check_yakuman(win_player.hand, win_player.melds, reason)
        if yakuman_fan > 0:
            # 役满优先，固定8番
            _add_fan(player_scores[winner], "役满", yakuman_fan, get_yakuman_description(win_player.hand, win_player.melds))
        else:
            # 普通番数计算
            # 基础番
            _add_fan(player_scores[winner], "和底", 1, "胡牌基础番")

            # 行为与状态番
            if reason in ("zimo", "zimo_kong"):
                _add_fan(player_scores[winner], "自摸", 1, "自摸胡牌")
            if reason == "zimo_kong":
                _add_fan(player_scores[winner], "杠上开花", 1, "杠后补牌自摸")

            if is_menzen(win_player.hand, win_player.melds):
                _add_fan(player_scores[winner], "门前清", 1, "没有碰、明杠")

            # 牌型番 —— 对对胡 + 三暗刻的叠加规则
            toitoi = is_all_triplets(win_player.hand, win_player.melds)
            if toitoi:
                _add_fan(player_scores[winner], "对对胡", 2, "四个刻子+将眼")

            concealed_triplets = count_concealed_triplets(win_player.hand, win_player.melds)
            if concealed_triplets >= 3:
                if toitoi:
                    _add_fan(player_scores[winner], "三暗刻（与对对胡叠加）", 1, "三暗刻作为额外+1")
                else:
                    _add_fan(player_scores[winner], "三暗刻", 2, "三个暗刻")

            if is_full_flush(win_player.hand, win_player.melds):
                _add_fan(player_scores[winner], "清一色", 2, "同花色牌型")

            # 断幺九 +1
            if is_tanyao(win_player.hand, win_player.melds):
                _add_fan(player_scores[winner], "断幺九", 1, "全2-8")

            # 平和 +2（定义：门前清且四面子全顺子）
            if is_menzen(win_player.hand, win_player.melds) and is_all_sequences(win_player.hand, win_player.melds):
                _add_fan(player_scores[winner], "平和", 2, "门清四顺子")

            if reason == "rob_kong":
                _add_fan(player_scores[winner], "抢杠", 1, "抢杠胡")

            # 杠的番数（非役满时计算），每手上限 +2
            kong_count = count_kongs(win_player.melds)
            if kong_count > 0:
                kong_fan = min(kong_count, 2)  # 每手杠番上限 +2
                _add_fan(player_scores[winner], "杠", kong_fan, f"{kong_count}个杠（计入{kong_fan}番）")

            # 普通手封顶 7 番
            if player_scores[winner]["fan_total"] > 7:
                # 直接封顶为 7，不额外添加负项，保持 breakdown 简洁
                player_scores[winner]["fan_total"] = 7
                player_scores[winner]["fan_breakdown"].append(
                    {"name": "封顶", "fan": 0, "detail": "普通手封顶 7 番"}
                )

        # 计算负番
        loser = 1 - winner
        if yakuman_fan > 0:
            _add_fan(player_scores[loser], "役满负番", -8, "对手役满")
        else:
            win_fan = player_scores[winner]["fan_total"]
            _add_fan(player_scores[loser], "负番", -win_fan, "对手胡牌")

    players_payload: Dict[str, Dict[str, Any]] = {}
    for seat in (0, 1):
        entry = player_scores[seat]
        players_payload[str(seat)] = {
            "fan_total": entry["fan_total"],
            "fan_breakdown": entry["fan_breakdown"],
            "net_change": 0,
        }

    net_score = 0
    if winner is not None:
        loser = 1 - winner
        winner_fan = player_scores[winner]["fan_total"]
        # 计算积分变化
        score_change = fan_to_points(winner_fan)
        players_payload[str(winner)]["net_change"] = score_change
        players_payload[str(loser)]["net_change"] = -score_change
        net_score = score_change - (-score_change)  # 胜者得分减去败者失分

    return {
        "fan_unit": "番",
        "net_fan": net_score,  # 为了兼容性，保留这个字段
        "score_unit": "积分",
        "net_score": net_score,
        "players": players_payload,
    }
