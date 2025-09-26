# -*- coding: utf-8 -*-
# 最小规则核心：仅 3 门(万/条/筒) 1-9，共 27 种牌，每种 4 张 => 108 张
# 胡牌：经典四面子一将（允许暗顺子）。实现 碰/杠/胡 的基本合法性检查。
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import List, Tuple, Optional, Dict, Any
import random
from functools import lru_cache

# 牌编码：0..26，0-8=万1..9，9-17=条1..9，18-26=筒1..9
TILE_TYPES = 27
COPIES_PER_TILE = 4
TOTAL_TILES = TILE_TYPES * COPIES_PER_TILE  # 108

def tile_to_str(t: int) -> str:
    suit = ["m","s","p"][t // 9]
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

@lru_cache(maxsize=None)
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
    ps = list(state.players)
    phand = list(ps[seat].hand); phand.append(tile); phand = sort_hand(phand)
    ps[seat] = replace(ps[seat], hand=tuple(phand))
    st = replace(state, wall=new_wall, players=tuple(ps), last_discard=None, step_no=state.step_no+1)
    return st, tile

def discard(state: GameState, seat: int, tile: int) -> GameState:
    ps = list(state.players)
    hand = list(ps[seat].hand)
    if tile not in hand:
        raise ValueError("ILLEGAL_DISCARD")
    hand.remove(tile)
    disc = list(ps[seat].discards); disc.append(tile)
    ps[seat] = replace(ps[seat], hand=tuple(hand), discards=tuple(disc))
    st = replace(state, players=tuple(ps), last_discard=(seat, tile), step_no=state.step_no+1, turn=1-seat)
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
    st = replace(state, players=tuple(ps), last_discard=None, turn=claimer, step_no=state.step_no+1)
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
    st = replace(state, players=tuple(ps), last_discard=None, turn=claimer, step_no=state.step_no+1)
    return st

def kong_concealed(state: GameState, seat: int, tile: int) -> GameState:
    hand = list(state.players[seat].hand)
    if hand.count(tile) != 4: raise ValueError("ILLEGAL_KONG_CONCEALED")
    for _ in range(4): hand.remove(tile)
    melds = list(state.players[seat].melds)
    melds.append(Meld("kong_concealed", (tile, tile, tile, tile)))
    ps = list(state.players)
    ps[seat] = replace(ps[seat], hand=tuple(sort_hand(hand)), melds=tuple(melds))
    st = replace(state, players=tuple(ps), step_no=state.step_no+1)
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
    return replace(state, players=tuple(ps), step_no=state.step_no+1)

def legal_choices(state: GameState, seat: int) -> List[Dict]:
    me = state.players[seat]
    choices = []
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


def is_four_concealed_triplets(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """检查是否四暗刻"""
    # 需要手牌中有四个暗刻（包括暗杠）
    if len(melds) != 4:
        return False

    for meld in melds:
        if meld.kind == "kong_exposed":
            return False  # 有明杠不算暗刻
        if meld.kind not in ["pong", "kong_concealed"]:
            return False

    return True


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


def is_menzen(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """检查是否门前清（没有碰、明杠）"""
    for meld in melds:
        if meld.kind in ["pong", "kong_exposed"]:
            return False
    return True


def is_all_triplets(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> bool:
    """检查是否对对胡（四个刻子+将眼）"""
    if len(melds) != 4:
        return False

    # 所有melds必须是刻子或杠子
    triplet_kinds = ["pong", "kong_exposed", "kong_concealed", "kong_added"]
    return all(meld.kind in triplet_kinds for meld in melds)


def count_concealed_triplets(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> int:
    """计算暗刻数量"""
    count = 0
    for meld in melds:
        if meld.kind in ["pong", "kong_concealed"]:
            count += 1
    return count


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
            if reason == "zimo":
                _add_fan(player_scores[winner], "自摸", 1, "自摸胡牌")

            if is_menzen(win_player.hand, win_player.melds):
                _add_fan(player_scores[winner], "门前清", 1, "没有碰、明杠")

            # 牌型番
            if is_all_triplets(win_player.hand, win_player.melds):
                _add_fan(player_scores[winner], "对对胡", 2, "四个刻子+将眼")

            concealed_triplets = count_concealed_triplets(win_player.hand, win_player.melds)
            if concealed_triplets >= 3:
                _add_fan(player_scores[winner], "三暗刻", 2, f"三个暗刻")

            if is_full_flush(win_player.hand, win_player.melds):
                _add_fan(player_scores[winner], "清一色", 5, "同花色牌型")

            # 杠的番数（非役满时计算）
            kong_count = count_kongs(win_player.melds)
            if kong_count > 0:
                _add_fan(player_scores[winner], "杠", kong_count, f"{kong_count}个杠")

        # 计算负番
        loser = 1 - winner
        if yakuman_fan > 0:
            # 役满时负番固定为8番
            _add_fan(player_scores[loser], "役满负番", -yakuman_fan, "对手役满")
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
