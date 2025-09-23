# -*- coding: utf-8 -*-
import json, asyncio, random
from typing import Any, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from rules_core import *


app = FastAPI()
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    return FileResponse("static/index.html")


def _collect_meld_counts(player: PlayerState) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for meld in player.melds:
        counts[meld.kind] = counts.get(meld.kind, 0) + 1
    return counts


def _add_fan(entry: Dict[str, Any], name: str, fan: int, detail: Optional[str] = None) -> None:
    item = {"name": name, "fan": fan}
    if detail:
        item["detail"] = detail
    entry.setdefault("fan_breakdown", []).append(item)
    entry["fan_total"] = entry.get("fan_total", 0) + fan


def compute_score_summary(
    state: GameState,
    winner: Optional[int],
    reason: str,
    *,
    ron_from: Optional[int] = None,
) -> Dict[str, Any]:
    player_scores: Dict[int, Dict[str, Any]] = {
        0: {"fan_total": 0, "fan_breakdown": []},
        1: {"fan_total": 0, "fan_breakdown": []},
    }

    for seat in (0, 1):
        entry = player_scores[seat]
        meld_counts = _collect_meld_counts(state.players[seat])
        pong_count = meld_counts.get("pong", 0)
        if pong_count:
            _add_fan(entry, "碰", pong_count, f"{pong_count} 组碰牌，每组 +1 番")
        exposed_kong = meld_counts.get("kong_exposed", 0)
        if exposed_kong:
            fan = exposed_kong * 2
            _add_fan(entry, "明杠", fan, f"{exposed_kong} 组明杠，每组 +2 番")
        added_kong = meld_counts.get("kong_added", 0)
        if added_kong:
            fan = added_kong * 2
            _add_fan(entry, "加杠", fan, f"{added_kong} 次加杠，每次 +2 番")
        concealed_kong = meld_counts.get("kong_concealed", 0)
        if concealed_kong:
            fan = concealed_kong * 3
            _add_fan(entry, "暗杠", fan, f"{concealed_kong} 组暗杠，每组 +3 番")

    if winner is not None:
        win_entry = player_scores[winner]
        _add_fan(win_entry, "胡牌基础", 4, "胡牌基础番")
        if reason == "zimo":
            _add_fan(win_entry, "自摸", 2, "自摸额外奖励")
        elif reason == "ron":
            _add_fan(win_entry, "荣和", 1, "荣和他人弃牌")

        loser = 1 - winner
        if reason == "zimo":
            _add_fan(player_scores[loser], "被自摸", -2, "被对手自摸，扣 2 番")
        elif reason == "ron":
            target = ron_from if ron_from is not None else loser
            _add_fan(player_scores[target], "放铳", -2, "打出的牌被荣和，扣 2 番")

    players_payload: Dict[str, Dict[str, Any]] = {}
    for seat in (0, 1):
        entry = player_scores[seat]
        players_payload[str(seat)] = {
            "fan_total": entry["fan_total"],
            "fan_breakdown": entry["fan_breakdown"],
            "net_change": 0,
        }

    net_fan = 0
    if winner is not None:
        loser = 1 - winner
        net_fan = player_scores[winner]["fan_total"] - player_scores[loser]["fan_total"]
        if net_fan < 0:
            net_fan = 0
        players_payload[str(winner)]["net_change"] = net_fan
        players_payload[str(loser)]["net_change"] = -net_fan

    return {
        "fan_unit": "番",
        "net_fan": net_fan,
        "players": players_payload,
    }


class Session:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.room: Optional["Room"] = None
        self.seat: Optional[int] = None
        self.nickname: str = "Anon"

    async def send(self, data: dict):
        await self.ws.send_text(json.dumps(data, ensure_ascii=False))

class Room:
    def __init__(self, room_id: str):
        self.id = room_id
        self.sess: Dict[int, Session] = {}
        self.ready = {0: False, 1: False}
        self.state: Optional[GameState] = None
        self.lock = asyncio.Lock()

    def opponent(self, seat: int) -> Optional[Session]:
        return self.sess.get(1-seat)

    async def broadcast(self, data: dict):
        for s in self.sess.values():
            try:
                await s.send(data)
            except:
                pass

    def _serialize_melds(self, melds, *, reveal_hidden: bool):
        serialized = []
        for m in melds:
            if m.kind == "kong_concealed" and not reveal_hidden:
                # 对手不可见暗杠的具体牌
                tiles = [None] * len(m.tiles)
            else:
                tiles = list(m.tiles)
            serialized.append({"kind": m.kind, "tiles": tiles})
        return serialized

    def _view_payload(self, seat: int) -> dict:
        if not self.state:
            return {}
        you = self.state.players[seat]
        opp = self.state.players[1-seat]
        return {
            "hand": list(you.hand),
            "melds_self": self._serialize_melds(you.melds, reveal_hidden=True),
            "melds_opp": self._serialize_melds(opp.melds, reveal_hidden=False),
            "discards_self": list(you.discards),
            "discards_opp": list(opp.discards),
        }

    def _final_view_payload(self, bonus_tiles: Optional[Dict[int, int]] = None) -> dict:
        if not self.state:
            return {}
        players = {}
        for seat in (0, 1):
            player = self.state.players[seat]
            tiles = list(player.hand)
            if bonus_tiles and seat in bonus_tiles:
                tiles = sort_hand(tiles + [bonus_tiles[seat]])
            players[str(seat)] = {
                "hand": tiles,
                "melds": self._serialize_melds(player.melds, reveal_hidden=True),
                "discards": list(player.discards),
            }
        return {
            "players": players,
            "wall_remaining": list(self.state.wall),
        }

    async def sync_player(self, seat: int):
        if not self.state: return
        sess = self.sess.get(seat)
        if not sess: return
        view = self._view_payload(seat)
        await sess.send({"type":"sync_hand","hand": view.get("hand", [])})
        await sess.send({"type":"sync_view", **view})

    async def sync_all(self):
        if not self.state: return
        for seat in (0,1):
            if seat in self.sess:
                await self.sync_player(seat)

    async def try_start(self):
        if len(self.sess) != 2:
            return
        if not (self.ready.get(0) and self.ready.get(1)):
            return

        if self.state is not None and not getattr(self.state, "ended", False):
            # 有未正常结束的旧对局，强制重置以允许重新开局
            self.state = None

        if self.state is not None and not getattr(self.state, "ended", False):
            return

        seed = random.randint(1, 10**9)
        self.state = init_game(seed)
        self.ready = {0: False, 1: False}

        await self.broadcast({
            "type":"game_started",
            "seed": seed,
        })
        # 给两位下发各自可见信息
        for seat, s in self.sess.items():
            view = self._view_payload(seat)
            await s.send({
                "type":"you_are",
                "seat": seat,
                "nickname": s.nickname,
                "opponent": getattr(self.opponent(seat), "nickname", "??"),
                **view,
            })
        # 首回合：轮到0先摸
        await self.step_auto()

    async def step_auto(self, *, lock_held: bool = False):
        # 自动下发当前行动方的 choices；如需要先摸牌则服务器执行摸并广播
        if not self.state or self.state.ended: return
        seat = self.state.turn
        me = self.sess.get(seat)
        if not me: return
        # 如果需要摸牌（自己13张）
        if len(self.state.players[seat].hand)%3==1 and self.state.last_discard is None:
            if not self.state.wall:
                self.state = replace(self.state, ended=True)
                score_summary = compute_score_summary(self.state, None, "wall")
                await self.broadcast({
                    "type": "game_end",
                    "result": {"reason": "wall", "score": score_summary},
                    "final_view": self._final_view_payload(),
                })
                return
            if lock_held:
                self.state, tile = draw(self.state, seat)
            else:
                async with self.lock:
                    self.state, tile = draw(self.state, seat)
            await self.broadcast({"type":"event","ev":{"type":"draw","seat":seat,"tile": (tile if True else None)}})
        await self.sync_player(seat)
        # 下发 choices
        choices = legal_choices(self.state, seat)
        await me.send({"type":"choices","actions":choices})

    async def step_after_discard(self, *, lock_held: bool = False):
        # 对手可响应：碰/杠/荣和/过
        if not self.state: return

        async def _inner():
            if not self.state: return
            seat = self.state.turn
            opp = self.sess.get(seat)
            if not opp: return
            actions = legal_choices(self.state, seat)
            if not actions:
                return
            if len(actions) == 1 and actions[0].get("type") == "pass":
                self.state = replace(self.state, last_discard=None)
                await self.broadcast({"type":"event","ev":{"type":"pass","seat":seat}})
                await self.sync_all()
                await self.step_auto(lock_held=True)
                return
            await opp.send({"type":"choices","actions":actions})

        if lock_held:
            await _inner()
        else:
            async with self.lock:
                await _inner()

rooms: Dict[str, Room] = {}

async def attach(ws: WebSocket) -> Session:
    await ws.accept()
    return Session(ws)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    sess = await attach(ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")

            if t == "join_room":
                rid = msg.get("room_id","default")
                sess.nickname = msg.get("nickname","Anon")
                room = rooms.setdefault(rid, Room(rid))
                # 分配座位
                if 0 not in room.sess:
                    seat = 0
                elif 1 not in room.sess:
                    seat = 1
                else:
                    await sess.send({"type":"error","detail":"Room full"})
                    continue
                room.sess[seat] = sess
                sess.room, sess.seat = room, seat
                room.ready[seat] = False
                await sess.send({"type":"room_joined","room_id":rid,"seat":seat})
                await room.broadcast({"type":"ready_status","ready":dict(room.ready)})
                if room.opponent(seat):
                    await room.broadcast({"type":"room_status","players":[0 in room.sess, 1 in room.sess]})

            elif t == "ready":
                if not sess.room: continue
                sess.room.ready[sess.seat] = True
                await sess.room.broadcast({"type":"ready_status","ready":dict(sess.room.ready)})
                await sess.room.try_start()

            elif t == "act":
                if not sess.room or sess.seat is None: continue
                action = msg.get("action",{})
                room = sess.room
                async with room.lock:
                    st = room.state
                    if st is None: continue

                    # 自己回合的行动
                    if st.turn == sess.seat and st.last_discard is None:
                        if action.get("type") == "discard":
                            tile = int(action["tile"])
                            room.state = discard(st, sess.seat, tile)
                            await room.broadcast({"type":"event","ev":{"type":"discard","seat":sess.seat,"tile":tile}})
                            await room.sync_all()
                            await sess.send({"type":"choices","actions":[]})
                            # 出牌后让对家选择响应
                            await room.step_after_discard(lock_held=True)

                        elif action.get("type") == "kong":
                            style = action.get("style")
                            tile = int(action["tile"])
                            if style == "concealed":
                                room.state = kong_concealed(st, sess.seat, tile)
                            elif style == "added":
                                room.state = kong_added(st, sess.seat, tile)
                            else:
                                await sess.send({"type":"error","detail":"bad kong style"}); continue
                            ev_payload = {"type":"kong","style":style,"seat":sess.seat}
                            if style != "concealed":
                                ev_payload["tile"] = tile
                            await room.broadcast({"type":"event","ev":ev_payload})
                            # 杠后继续摸牌
                            await room.sync_all()
                            await room.step_auto(lock_held=True)

                        elif action.get("type") == "hu" and action.get("style")=="self":
                            # 自摸胡
                            if can_hu_four_plus_one(st.players[sess.seat].hand, st.players[sess.seat].melds):
                                room.state = replace(st, ended=True)
                                score_summary = compute_score_summary(room.state, sess.seat, "zimo")
                                await room.broadcast({
                                    "type": "game_end",
                                    "result": {"winner": sess.seat, "reason": "zimo", "score": score_summary},
                                    "final_view": room._final_view_payload(),
                                })
                            else:
                                await sess.send({"type":"error","detail":"not hu"})
                        elif action.get("type") == "draw":
                            room.state, tile = draw(st, sess.seat)
                            await room.broadcast({"type":"event","ev":{"type":"draw","seat":sess.seat,"tile":tile}})
                            await room.sync_all()
                            await room.step_auto(lock_held=True)
                        else:
                            await sess.send({"type":"error","detail":"illegal or unsupported action in turn"})

                    # 对家响应阶段（有人刚出牌）
                    else:
                        if st.last_discard is None:
                            await sess.send({"type":"error","detail":"no claimable discard"}); continue
                        from_seat, tile = st.last_discard
                        if from_seat == sess.seat:
                            await sess.send({"type":"error","detail":"cannot claim own discard"}); continue

                        style = action.get("type")
                        if style == "pass":
                            # 放弃权利，轮到出牌方的对家（st.turn 已是对家），自动进入其抽牌流程
                            room.state = replace(st, last_discard=None)
                            await room.broadcast({"type":"event","ev":{"type":"pass","seat":sess.seat}})
                            await room.sync_all()
                            await room.step_auto(lock_held=True)
                        elif style == "peng":
                            if not can_peng(st.players[sess.seat].hand, tile):
                                await sess.send({"type":"error","detail":"cannot peng"}); continue
                            room.state = claim_peng(st, sess.seat, from_seat, tile)
                            await room.broadcast({"type":"event","ev":{"type":"peng","seat":sess.seat,"tile":tile}})
                            # 碰后必须打出一张
                            await room.sync_all()
                            await room.step_auto(lock_held=True)
                        elif style == "kong" and action.get("style")=="exposed":
                            if not can_kong_exposed(st.players[sess.seat].hand, tile):
                                await sess.send({"type":"error","detail":"cannot exposed kong"}); continue
                            room.state = claim_kong_exposed(st, sess.seat, from_seat, tile)
                            await room.broadcast({"type":"event","ev":{"type":"kong","style":"exposed","seat":sess.seat,"tile":tile}})
                            # 杠后继续摸牌
                            await room.sync_all()
                            await room.step_auto(lock_held=True)
                        elif style == "hu" and action.get("style")=="ron":
                            merged = tuple(sorted(st.players[sess.seat].hand + (tile,)))
                            if can_hu_four_plus_one(merged, st.players[sess.seat].melds):
                                room.state = replace(st, ended=True)
                                score_summary = compute_score_summary(room.state, sess.seat, "ron", ron_from=from_seat)
                                await room.broadcast({
                                    "type": "game_end",
                                    "result": {"winner": sess.seat, "reason": "ron", "tile": tile, "score": score_summary},
                                    "final_view": room._final_view_payload({sess.seat: tile}),
                                })
                            else:
                                await sess.send({"type":"error","detail":"not hu"})
                        else:
                            await sess.send({"type":"error","detail":"unsupported claim action"})

            else:
                await sess.send({"type":"error","detail":"unknown message type"})

    except WebSocketDisconnect:
        # 简易处理：断线即移除
        r = sess.room
        seat = sess.seat
        if r and seat in r.sess:
            del r.sess[seat]
            if seat in r.ready:
                r.ready[seat] = False
            if len(r.sess) < 2:
                r.state = None
                r.ready = {0: False, 1: False}
            await r.broadcast({"type":"room_status","players":[0 in r.sess, 1 in r.sess]})
            await r.broadcast({"type":"ready_status","ready":dict(r.ready)})
