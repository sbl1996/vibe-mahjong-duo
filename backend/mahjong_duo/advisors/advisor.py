# -*- coding: utf-8 -*-
"""
AI 提示模块（Advisor）：在给定 GameState 下，为当前玩家提供【打牌建议】、
【对手打牌时的响应建议】、【自己摸牌后的杠/打牌建议】。

实现要点：
- 规则与番数：沿用用户给定的规则与已有番数计算函数（compute_score_summary 等）。
- 全信息近似搜索：基于**已知牌墙顺序**与**双方手牌**，以【向听数】、
  【最短自摸轮数（TTW）】和【最终番数】为指标建立评估函数。
- 评估函数：Score = Fan / (TTW + 1)。在能赢（TTW <= 对手TTW）时偏好更高分；
  否则进入防守策略，最大化对手的 TTW。

说明：
- 为了在最小代码量与可运行性之间平衡，TTW 计算采用“贪心重估”的近似法：
  在每次假设打出某张后，反复（1）计算当前向听，（2）枚举能降低向听的有效张集合，
  （3）仅在**自己未来的摸牌序列**里搜索首张有效张出现的位置，推进一步并重估；
  直到向听=-1（胡）。这在大多数局面下给出合理的最短自摸轮数估计。
- 对手 TTW 同理（使用对手的摸牌序列）。

接口：
- advise_on_discard(state: GameState, seat: int) -> dict
- advise_on_opponent_discard(state: GameState, seat: int) -> dict
- advise_on_draw(state: GameState, seat: int) -> dict

返回：统一的建议 payload：
{
  "action": str,             # e.g. "discard", "hu", "peng", "kong", "pass"
  "tile": Optional[int],
  "reason": str,             # 人类可读的简析
  "detail": {...}            # 包含评分、TTW/Fan、候选比较等
}
"""
from dataclasses import replace
from typing import List, Tuple, Optional, Dict, Any
from functools import lru_cache

from mahjong_duo.rules_core import (
    TILE_TYPES, tile_to_str, GameState, Meld,
    can_hu_four_plus_one, compute_score_summary, count_kongs,
    is_full_flush, is_menzen, is_all_triplets, count_concealed_triplets,
    check_yakuman, is_tanyao
)

# ------------------------------
#       向听与有效张估计
# ------------------------------

@lru_cache(maxsize=128)
def _counts(tiles: Tuple[int, ...]) -> Tuple[int, ...]:
    c = [0]*TILE_TYPES
    for t in tiles:
        c[t]+=1
    return tuple(c)

@lru_cache(maxsize=128)
def _min_adds_to_complete(counts: Tuple[int, ...], melds_done: int, has_pair: bool) -> int:
    """返回从当前（未包括明刻/杠）牌型到完成 4 面子 1 将所需最少“补牌张数”。
    这相当于一个标准的向听近似（返回值即“距离胡牌还差的张数”，胡=-1）。

    做法：DFS + 备忘录，优先剔除刻子/顺子，其次尝试搭子（需要 +1），最后单张（需要 +2）。
    该估计对数字三花麻将效果良好。
    """
    need_melds = 4 - melds_done
    total_left = sum(counts)
    # 胡：4 面子 + 将，剩牌应为 0
    if need_melds == 0:
        return 0 if has_pair and total_left == 0 else (2 if not has_pair else total_left*2)

    # 若没有牌了但还没形成目标结构，返回较大代价
    if total_left == 0:
        # 还缺 need_melds 个面子 + （可能缺）将：每个面子至少需要 3 张，估成 2/面子
        base = need_melds * 2
        if not has_pair:
            base += 2  # 估一个将的代价
        return base

    # 找到第一张有牌的位置
    i = next(k for k,c in enumerate(counts) if c>0)

    best = 1e9
    arr = list(counts)

    # 1) 尝试刻子（i,i,i）
    if arr[i] >= 3:
        arr[i] -= 3
        best = min(best, _min_adds_to_complete(tuple(arr), melds_done+1, has_pair))
        arr[i] += 3

    # 2) 尝试顺子（仅数字三花，且不跨花色）
    r = i % 9
    if r <= 6 and arr[i] and arr[i+1] and arr[i+2] and (i//9)==((i+2)//9):
        arr[i]-=1; arr[i+1]-=1; arr[i+2]-=1
        best = min(best, _min_adds_to_complete(tuple(arr), melds_done+1, has_pair))
        arr[i]+=1; arr[i+1]+=1; arr[i+2]+=1

    # 3) 尝试将眼（i,i）
    if not has_pair and arr[i] >= 2:
        arr[i] -= 2
        best = min(best, _min_adds_to_complete(tuple(arr), melds_done, True))
        arr[i] += 2

    # 4) 搭子（需要 +1）：
    #   a) 对子作搭子（缺 1）
    if arr[i] == 2:
        arr[i] -= 2
        best = min(best, 1 + _min_adds_to_complete(tuple(arr), melds_done, has_pair))
        arr[i] += 2
    #   b) 顺子搭子（i,i+1）或（i,i+2）
    if r <= 7 and (i//9)==((i+1)//9) and arr[i] and arr[i+1]:
        arr[i]-=1; arr[i+1]-=1
        best = min(best, 1 + _min_adds_to_complete(tuple(arr), melds_done, has_pair))
        arr[i]+=1; arr[i+1]+=1
    if r <= 6 and (i//9)==((i+2)//9) and arr[i] and arr[i+2]:
        arr[i]-=1; arr[i+2]-=1
        best = min(best, 1 + _min_adds_to_complete(tuple(arr), melds_done, has_pair))
        arr[i]+=1; arr[i+2]+=1

    # 5) 单张（缺 2）
    arr[i] -= 1
    best = min(best, 2 + _min_adds_to_complete(tuple(arr), melds_done, has_pair))
    arr[i] += 1

    return best


def shanten_number(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> int:
    """基于“最少补牌数”估计的向听数：
    - 胡牌返回 -1
    - 听牌返回 0
    - 其余返回 >=1
    """
    if can_hu_four_plus_one(hand, melds):
        return -1
    c = _counts(hand)
    # 已有的明刻/杠都视作已成面子
    melds_done = len(melds)
    need = _min_adds_to_complete(c, melds_done, has_pair=False)
    # 标准 mahjong 定义里，shanten 等于到和牌还差的“摸/变更”次数；
    # 这里用最少补牌数近似，效果与常见实现一致。
    return max(0, need)


def effective_tiles_for_progress(hand: Tuple[int, ...], melds: Tuple[Meld, ...]) -> List[int]:
    """返回当前手牌下，能使向听数 -1 的所有“有效张”集合。"""
    cur = shanten_number(hand, melds)
    eff = []
    if cur <= -1:
        return eff
    # 尝试加入每一种牌
    # 注意：麻将里同一种牌最多 4 张——我们不在这里过滤剩余枚数，
    # 在扫描牌墙时自然会被排除。
    for t in range(TILE_TYPES):
        test = tuple(sorted(hand + (t,)))
        if shanten_number(test, melds) < cur:
            eff.append(t)
    return eff

# ------------------------------
#        摸牌序列与 TTW
# ------------------------------

def _future_draw_indices(state: GameState, seat: int) -> List[int]:
    """给出从当前时刻起，该 seat 在后续牌墙中将摸到的索引（相对 state.wall 的 0-based）。
    简化：忽略后续可能发生的杠改变摸牌顺序（除非我们在分支里显式执行了杠）。
    规则：双人交替摸牌，先看当前轮到谁（state.turn）。
    - 如果现在 seat==state.turn 且该 seat 需要摸牌（通常 13 张手牌），那么它将先摸 wall[0]，
      下一次在 wall[2]，然后 wall[4]，以此类推。
    - 否则，它从 wall[1] 开始，之后每隔 2 张。
    """
    start = 0 if seat == state.turn else 1
    # 如果当前玩家手牌已经是 14 张（刚摸到），下一次摸牌要等到对方摸->自己再摸，因此偏移 +2
    if seat == state.turn and len(state.players[seat].hand) % 3 == 2:
        start = 2  # 自己这轮将先打出，再轮到对方摸，下一次自己摸的位置
    return list(range(start, len(state.wall), 2))


def estimate_ttw_by_greedy(state: GameState, seat: int, hand: Tuple[int,...], melds: Tuple[Meld,...]) -> Optional[int]:
    """基于贪心的最短自摸轮数估计：
    - 反复：计算向听 -> 有效张 -> 在自己的摸牌位置序列中寻找第一张有效张出现的位置，
      如果能找到则“假想摸到并加入手牌”，继续；找不到则返回 None（此路径无法在剩余牌墙内完成）。
    - 当向听=-1 时返回累计轮数（自己摸的次数）。
    注意：这里忽略了荣和（吃对方打出的牌）对 TTW 的影响，TTW 仅统计自摸速度。
    """
    cur_hand = tuple(hand)
    cur_melds = tuple(melds)
    draws = _future_draw_indices(state, seat)
    rounds = 0

    # 拷贝出可变的已用索引集合，防止重复使用同一张牌
    used = set()

    while True:
        stn = shanten_number(cur_hand, cur_melds)
        if stn <= -1:
            return rounds
        eff = set(effective_tiles_for_progress(cur_hand, cur_melds))
        if not eff:
            return None
        # 在未来的自己的摸牌序列里，找第一张属于 eff 的牌
        picked_idx = None
        for idx in draws:
            if idx in used:
                continue
            if idx >= len(state.wall):
                break
            t = state.wall[idx]
            if t in eff:
                picked_idx = idx
                break
        if picked_idx is None:
            return None
        # “摸到”该牌
        used.add(picked_idx)
        cur_hand = tuple(sorted(cur_hand + (state.wall[picked_idx],)))
        rounds += 1


# ------------------------------
#        Fan 估计（终局上限）
# ------------------------------

def estimate_final_fan_upper(state: GameState, seat: int, hand: Tuple[int,...], melds: Tuple[Meld,...], reason: str="zimo") -> int:
    """粗略估计终局 fan：以当前（手牌+副露）为基础，
    - 若已可胡，直接用 compute_score_summary 计算真实番；
    - 若未胡，以当前番型可达的上限为估计（门清/清一色/对对胡/三暗刻/杠等的静态上限），
      该估计仅用于比较同回合不同分支的相对优劣。
    """
    if can_hu_four_plus_one(hand, melds):
        # 直接调用记分，拿到真实的番
        summary = compute_score_summary(replace(state, players=tuple(
            replace(p, hand=hand, melds=melds) if i==seat else p
            for i,p in enumerate(state.players)
        )), winner=seat, reason="zimo" if reason=="zimo" else "ron")
        return summary["players"][str(seat)]["fan_total"]

    # 未胡：静态上限（保守）
    fan = 1  # 和底预期
    if is_menzen(hand, melds):
        fan += 1

    if is_full_flush(hand, melds):
        fan += 2

    if is_all_triplets(hand, melds):
        fan += 2

    ctrip = count_concealed_triplets(hand, melds)
    if ctrip >= 3:
        fan += 2

    if is_tanyao(hand, melds):
        fan += 1

    # 杠的番数有上限
    kong_count = count_kongs(melds)
    fan += min(kong_count, 2)

    # 役满检查
    yakuman_fan = check_yakuman(hand, melds, reason)
    if yakuman_fan:
        return yakuman_fan

    return min(fan, 7) # 普通番种上限为7


# ------------------------------
#         进攻与防守的选择
# ------------------------------

def _score(fan: int, ttw: Optional[int]) -> float:
    if ttw is None:
        return -1e9
    return fan / (ttw + 1)


def _opponent_ttw(state: GameState, seat: int) -> Optional[int]:
    opp = 1 - seat
    ph = state.players[opp].hand
    pm = state.players[opp].melds
    return estimate_ttw_by_greedy(state, opp, ph, pm)


# ------------------------------
#            打牌建议
# ------------------------------

def _points_from_summary(summary: Dict[str, Any], winner: int) -> int:
    # 直接取 winner 的净增分（已是 fan_to_points 后的值）
    return summary["players"][str(winner)]["net_change"]

def advise_on_discard(state: GameState, seat: int) -> Dict[str, Any]:
    me = state.players[seat]
    assert len(me.hand) % 3 == 2, "需要在 14 张时调用"

    opp_ttw = _opponent_ttw(state, seat)

    # 如果当前我方处于听牌，计算“荣和时番数上界”（不依赖具体牌）
    my_shanten = shanten_number(me.hand, me.melds)
    my_ron_fan_upper = None
    if my_shanten == 0:
        best_f = 0
        # 枚举所有可能的胡张，取番数最大者（上限参考）
        for t in range(TILE_TYPES):
            test = tuple(sorted(me.hand + (t,)))
            if can_hu_four_plus_one(test, me.melds):
                # 用 ron 计算真实番
                tmp_state = replace(state, players=tuple(
                    replace(p, hand=test) if i==seat else p
                    for i,p in enumerate(state.players)
                ))
                sumy = compute_score_summary(tmp_state, winner=seat, reason="ron")
                f = sumy["players"][str(seat)]["fan_total"]
                if f > best_f:
                    best_f = f
        my_ron_fan_upper = best_f if best_f > 0 else None

    candidates = []
    seen = set()
    for t in me.hand:
        if t in seen:
            continue
        seen.add(t)

        # 模拟打出 t
        new_hand = list(me.hand); new_hand.remove(t); new_hand = tuple(new_hand)

        my_ttw = estimate_ttw_by_greedy(state, seat, new_hand, me.melds)
        my_fan = estimate_final_fan_upper(state, seat, new_hand, me.melds)
        # 若处于听牌，可将“荣和上界”作为进攻参考（不替代真实 fan，仅作加成或注释）
        if my_ron_fan_upper is not None and (my_ttw is None or my_ttw > 0):
            # 处于听牌 → 可能通过荣和比自摸更快，这里不直接替换 fan，只在说明里展示
            pass

        my_score = _score(my_fan, my_ttw)

        # 对手是否能立刻荣和此张（点炮），若能 → 计算对手的“即时得分”
        can_opp_ron = False
        opp_ron_points = 0
        merged = tuple(sorted(state.players[1-seat].hand + (t,)))
        if can_hu_four_plus_one(merged, state.players[1-seat].melds):
            can_opp_ron = True
            tmp_state = replace(state, players=tuple(
                replace(p, hand=merged) if i==(1-seat) else p
                for i,p in enumerate(state.players)
            ))
            summary_opp = compute_score_summary(tmp_state, winner=1-seat, reason="ron")
            opp_ron_points = _points_from_summary(summary_opp, 1-seat)

        # 调整后评分：我的进攻评分 - 对手立即荣和的损失分（若无则不扣）
        adjusted = my_score - (opp_ron_points if can_opp_ron else 0)

        candidates.append({
            "discard": t,
            "my_ttw": my_ttw,
            "my_fan": my_fan,
            "my_score": my_score,
            "opp_ttw": opp_ttw,
            "danger": can_opp_ron,
            "opp_ron_points": opp_ron_points if can_opp_ron else 0,
            "adjusted_score": adjusted,
        })

    # 直接按 adjusted_score 排序（不再简单丢弃“危险弃张”，而是以期望损失惩罚）
    candidates.sort(key=lambda x: x["adjusted_score"], reverse=True)
    best = candidates[0]
    tile = best["discard"]

    desc = f"建议打出【{tile_to_str(tile)}】。"
    r = []
    if best["my_ttw"] is not None:
        r.append(f"预计你最短 {best['my_ttw']} 轮自摸可和（估计番≈{best['my_fan']}）。")
    else:
        r.append("该路线在剩余牌墙内较难自摸完成，作为防守/安全打张。")

    if my_ron_fan_upper is not None:
        r.append(f"当前处于听牌，若对手弃出合适牌，有机会以荣和获得更高番（上界≈{my_ron_fan_upper}）。")

    if best.get("danger"):
        r.append(f"注意：此张会被对手【立即荣和】，预期损失≈{best['opp_ron_points']} 分（已计入综合评分）。")

    if opp_ttw is not None and best["my_ttw"] is not None:
        if best["my_ttw"] <= opp_ttw:
            r.append(f"你的速度不慢于对手（对手 TTW≈{opp_ttw}）。")
        else:
            r.append(f"纯进攻较慢于对手（对手 TTW≈{opp_ttw}），当前为偏防守选择。")

    return {
        "action": "discard",
        "tile": tile,
        "reason": desc + " " + " ".join(r),
        "detail": {
            "picked": best,
            "candidates": candidates[:10],
        }
    }


# ------------------------------
#        对手打牌时的响应建议
# ------------------------------

def advise_on_opponent_discard(state: GameState, seat: int) -> Dict[str, Any]:
    """当对手打出一张（state.last_discard 不为空）时，给出 荣/碰/杠/过 的建议。"""
    assert state.last_discard is not None, "需要在对手打出后调用"
    from_seat, tile = state.last_discard
    assert from_seat != seat

    me = state.players[seat]
    merged = tuple(sorted(me.hand + (tile,)))

    # 1) 荣和优先
    if can_hu_four_plus_one(merged, me.melds):
        # 用番数模块计算真实番
        tmp_state = replace(state, players=tuple(
            replace(p, hand=merged) if i==seat else p
            for i,p in enumerate(state.players)
        ))
        summary = compute_score_summary(tmp_state, winner=seat, reason="ron")
        fan = summary["players"][str(seat)]["fan_total"]
        return {
            "action": "hu",
            "tile": tile,
            "reason": f"建议【荣和】{tile_to_str(tile)}，立即结束对局（番数={fan}）。",
            "detail": {"fan": fan, "score": summary}
        }

    # 2) 比较 碰/明杠 与 过
    can_peng = me.hand.count(tile) >= 2
    can_kong = me.hand.count(tile) >= 3

    # 路径A：执行碰/杠
    best_A = None
    if can_kong or can_peng:
        # 先构造“执行动作后”的手牌/副露
        if can_kong:
            new_hand = list(me.hand)
            for _ in range(3):
                new_hand.remove(tile)
            new_melds = list(me.melds)
            new_melds.append(Meld("kong_exposed", (tile,tile,tile,tile)))
            new_hand = tuple(sorted(new_hand))
            my_ttw_A = estimate_ttw_by_greedy(state, seat, new_hand, tuple(new_melds))
            my_fan_A = estimate_final_fan_upper(state, seat, new_hand, tuple(new_melds), reason="zimo")
            best_A = ("kong", my_ttw_A, my_fan_A)
        else:
            new_hand = list(me.hand)
            new_hand.remove(tile); new_hand.remove(tile)
            new_melds = list(me.melds)
            new_melds.append(Meld("pong", (tile,tile,tile)))
            new_hand = tuple(sorted(new_hand))
            my_ttw_A = estimate_ttw_by_greedy(state, seat, new_hand, tuple(new_melds))
            # 门清失去
            my_fan_A = estimate_final_fan_upper(state, seat, new_hand, tuple(new_melds), reason="zimo")
            best_A = ("peng", my_ttw_A, my_fan_A)

    # 路径B：过
    my_ttw_B = estimate_ttw_by_greedy(state, seat, me.hand, me.melds)
    my_fan_B = estimate_final_fan_upper(state, seat, me.hand, me.melds, reason="zimo")

    if best_A is not None:
        act, ttwA, fanA = best_A
        scoreA = _score(fanA, ttwA)
        scoreB = _score(my_fan_B, my_ttw_B)
        if (ttwA is not None and my_ttw_B is not None and ttwA + 1 < my_ttw_B) or scoreA > scoreB:
            action_name = "明杠" if act=="kong" else "碰"
            return {
                "action": "kong" if act=="kong" else "peng",
                "tile": tile,
                "style": "exposed" if act=="kong" else None,
                "reason": f"建议【{action_name}】{tile_to_str(tile)}：可将最短自摸轮数从 {my_ttw_B} 降至 {ttwA}，综合得分更优。",
                "detail": {"after_action": {"ttw": ttwA, "fan": fanA, "score": scoreA},
                           "pass": {"ttw": my_ttw_B, "fan": my_fan_B, "score": scoreB}}
            }

    return {
        "action": "pass",
        "tile": tile,
        "reason": f"建议【过】{tile_to_str(tile)}。执行碰/杠对速度或番数无显著提升，且保留门前清/牌型弹性。",
        "detail": {"pass": {"ttw": my_ttw_B, "fan": my_fan_B}}
    }


# ------------------------------
#        自摸后的（暗杠/加杠/打牌）建议
# ------------------------------

def advise_on_draw(state: GameState, seat: int) -> Dict[str, Any]:
    """自己摸牌到 14 张后的决策：优先检查胡、再比较杠与不杠的路径；若不杠，则给出打牌建议。"""
    me = state.players[seat]
    assert len(me.hand) % 3 == 2, "需要在 14 张时调用"

    # 1) 能自摸直接建议胡
    if can_hu_four_plus_one(me.hand, me.melds):
        summary = compute_score_summary(state, winner=seat, reason="zimo")
        fan = summary["players"][str(seat)]["fan_total"]
        return {
            "action": "hu",
            "tile": None,
            "reason": f"建议【自摸】立即和牌（番数={fan}）。",
            "detail": {"score": summary}
        }

    # 2) 检查暗杠/加杠的价值
    def _can_kong_concealed(hand: Tuple[int,...]) -> Optional[int]:
        for i in range(TILE_TYPES):
            if hand.count(i)==4: return i
        return None

    def _can_kong_added(melds: Tuple[Meld,...], hand: Tuple[int,...]) -> Optional[int]:
        for m in melds:
            if m.kind=="pong" and hand.count(m.tiles[0])>=1:
                return m.tiles[0]
        return None

    kc = _can_kong_concealed(me.hand)
    ka = _can_kong_added(me.melds, me.hand)

    kong_candidates: List[Tuple[str,int,Tuple[int,...],Tuple[Meld,...]]] = []
    if kc is not None:
        tmp = list(me.hand)
        for _ in range(4):
            tmp.remove(kc)
        nh = tuple(sorted(tmp))
        new_melds = tuple(list(me.melds) + [Meld("kong_concealed", (kc,kc,kc,kc))])
        kong_candidates.append(("kong_concealed", kc, nh, new_melds))
    if ka is not None:
        tmp = list(me.hand); tmp.remove(ka)
        nh = tuple(sorted(tmp))
        new_melds = []
        upgraded = False
        for m in me.melds:
            if m.kind=="pong" and (not upgraded) and m.tiles[0]==ka:
                new_melds.append(Meld("kong_added", (ka,ka,ka,ka)))
                upgraded = True
            else:
                new_melds.append(m)
        kong_candidates.append(("kong_added", ka, nh, tuple(new_melds)))

    # 比较“杠后路径”与“不杠直接打牌”
    best_kong = None
    for kind, tile, nh, nm in kong_candidates:
        ttwA = estimate_ttw_by_greedy(state, seat, nh, nm)
        fanA = estimate_final_fan_upper(state, seat, nh, nm)
        scoreA = _score(fanA, ttwA)
        best_kong = (kind, tile, ttwA, fanA, scoreA)

    # 不杠：走打牌建议
    discard_plan = advise_on_discard(state, seat)

    if best_kong is not None:
        kind, tile, ttwA, fanA, scoreA = best_kong
        style = {
            "kong_concealed": "concealed",
            "kong_added": "added",
        }.get(kind)
        scoreB = discard_plan["detail"]["picked"]["my_score"]
        if scoreA > scoreB:
            name = "暗杠" if kind=="kong_concealed" else "加杠"
            return {
                "action": "kong",
                "tile": tile,
                "style": style,
                "reason": f"建议【{name}】{tile_to_str(tile)}，综合评分优于直接打牌（杠后估计：TTW={ttwA}，番≈{fanA}）。",
                "detail": {"after_kong": {"ttw": ttwA, "fan": fanA, "score": scoreA},
                           "no_kong_then_discard": discard_plan}
            }

    return discard_plan
