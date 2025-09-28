# -*- coding: utf-8 -*-
import json, asyncio, random, secrets
from pathlib import Path
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from rules_core import *
from advisor import advise_on_draw, advise_on_opponent_discard
from database import db, init_database

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

BASE_SCORE = 8  # 初始分为 1000 时，1 番起始变动约为 16 分


def fan_to_points(fan_total: int, base: int = BASE_SCORE) -> int:
    """根据番数计算积分变化"""
    fan_value = max(fan_total, 0)
    return base * (2 ** fan_value)

app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库"""
    await init_database()

@app.post("/api/login")
async def login(request: Request):
    """用户登录"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return JSONResponse(
                status_code=400,
                content={"error": "用户名和密码不能为空"}
            )

        # 验证用户
        user = await db.authenticate_user(username, password)
        if user:
            token = secrets.token_urlsafe(32)
            authenticated_sessions[token] = {
                "user_id": user["id"],
                "username": user["username"],
            }
            return JSONResponse(content={
                "success": True,
                "user": user,
                "token": token
            })
        else:
            return JSONResponse(
                status_code=401,
                content={"error": "用户名或密码错误"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"服务器错误: {str(e)}"}
        )

@app.get("/api/user/{username}")
async def get_user_info(username: str):
    """获取用户信息"""
    try:
        user = await db.get_user_by_username(username)
        if user:
            # 获取用户统计信息
            stats = await db.get_user_stats(user["id"])
            return JSONResponse(content={
                "user": user,
                "stats": stats
            })
        else:
            return JSONResponse(
                status_code=404,
                content={"error": "用户不存在"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"服务器错误: {str(e)}"}
        )

@app.get("/api/user/{username}/records")
async def get_user_records(username: str, limit: int = 20):
    """获取用户对局记录"""
    try:
        user = await db.get_user_by_username(username)
        if not user:
            return JSONResponse(
                status_code=404,
                content={"error": "用户不存在"}
            )

        records = await db.get_user_game_records(user["id"], limit)
        return JSONResponse(content={"records": records})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"服务器错误: {str(e)}"}
        )

@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    """获取排行榜"""
    try:
        leaderboard = await db.get_leaderboard(limit)
        return JSONResponse(content={"leaderboard": leaderboard})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"服务器错误: {str(e)}"}
        )

# 存储已登录的用户会话
authenticated_sessions: Dict[str, Dict] = {}


class Session:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.room: Optional["Room"] = None
        self.seat: Optional[int] = None
        self.user_id: Optional[int] = None
        self.username: Optional[str] = None
        self.vip_level: int = 0

    async def send(self, data: dict):
        await self.ws.send_text(json.dumps(data, ensure_ascii=False))

class Room:
    def __init__(self, room_id: str):
        self.id = room_id
        self.sess: Dict[int, Session] = {}
        self.ready = {0: False, 1: False}
        self.state: Optional[GameState] = None
        self.lock = asyncio.Lock()
        self.player_names: Dict[int, str] = {}  # 座位对应的玩家名称
        self.ai_seat: Optional[int] = None
        self.practice_mode: bool = False
        self.ai_name = "AI陪练"

    def opponent(self, seat: int) -> Optional[Session]:
        return self.sess.get(1-seat)

    def get_player_name(self, seat: int) -> str:
        """获取指定座位玩家的名字"""
        session = self.sess.get(seat)
        if session and session.username:
            return session.username
        if seat in self.player_names:
            return self.player_names[seat]
        return f"Player{seat}"

    def is_ai_seat(self, seat: int) -> bool:
        return self.ai_seat is not None and self.ai_seat == seat

    def seat_active(self, seat: int) -> bool:
        return seat in self.sess or self.is_ai_seat(seat)

    def _ensure_ai_ready(self):
        if self.practice_mode and self.ai_seat is not None:
            self.ready[self.ai_seat] = True

    async def _broadcast_room_status(self):
        await self.broadcast({"type":"room_status","players":[self.seat_active(0), self.seat_active(1)]})

    def disable_ai_practice(self):
        if self.ai_seat is None:
            return
        seat = self.ai_seat
        self.practice_mode = False
        self.ai_seat = None
        if self.player_names.get(seat) == self.ai_name:
            self.player_names.pop(seat, None)
        self.ready[seat] = False

    async def enable_ai_practice(self, requester: Session):
        if requester.seat is None:
            return
        if self.state and not getattr(self.state, "ended", False):
            await requester.send({"type":"error","detail":"对局进行中，暂不可启用AI陪练"})
            return
        target = 1 - requester.seat
        if self.ai_seat is not None:
            target = self.ai_seat
        if target in self.sess and self.sess[target] is not requester:
            await requester.send({"type":"error","detail":"对面已有真人玩家，无法启用AI陪练"})
            return
        self.practice_mode = True
        self.ai_seat = target
        self.player_names[target] = self.ai_name
        self._ensure_ai_ready()
        await requester.send({"type":"practice_enabled","seat":target})
        await self._broadcast_room_status()
        await self.broadcast({"type":"ready_status","ready":dict(self.ready)})
        await self.try_start()

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

    async def _resolve_rob_kong_hu(self, robber: int, tile: int, *, lock_held: bool) -> None:
        if not self.state or self.state.pending_rob_kong is None:
            return
        kong_owner, pending_tile = self.state.pending_rob_kong
        if robber != 1 - kong_owner:
            return
        win_tile = tile if tile is not None else pending_tile
        st = self.state
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

        self.state = replace(
            st,
            players=tuple(players),
            pending_rob_kong=None,
            ended=True,
            turn=robber,
            last_discard=None,
            pending_kong_draw=None,
            last_draw_info=None,
        )

        await self.broadcast({"type": "event", "ev": {"type": "rob_kong", "seat": robber, "from": kong_owner, "tile": win_tile}})

        score_summary = compute_score_summary(self.state, robber, "rob_kong")
        await self.broadcast({
            "type": "game_end",
            "result": {"winner": robber, "reason": "rob_kong", "tile": win_tile, "score": score_summary},
            "final_view": self._final_view_payload(),
        })
        await update_game_scores(self, robber, "rob_kong", score_summary)

    async def _resolve_rob_kong_pass(self, robber: int, *, lock_held: bool) -> None:
        if not self.state or self.state.pending_rob_kong is None:
            return
        kong_owner, tile = self.state.pending_rob_kong
        if robber != 1 - kong_owner:
            return
        base_state = replace(self.state, pending_rob_kong=None, turn=kong_owner)
        try:
            new_state = kong_added(base_state, kong_owner, tile)
        except Exception:
            self.state = base_state
            return
        self.state = new_state
        await self.broadcast({"type": "event", "ev": {"type": "pass", "seat": robber}})
        await self.broadcast({"type": "event", "ev": {"type": "kong", "style": "added", "seat": kong_owner, "tile": tile}})
        await self.sync_all()
        await self.step_auto(lock_held=True)

    async def sync_player(self, seat: int):
        if not self.state: return
        sess = self.sess.get(seat)
        if not sess: return
        view = self._view_payload(seat)
        await sess.send({"type":"sync_hand","hand": view.get("hand", [])})
        # 在同步游戏状态时也要同步对手名字
        await sess.send({
            "type":"sync_view",
            **view,
            "opponent": self.get_player_name(1-seat),
        })

    async def sync_all(self):
        if not self.state: return
        for seat in (0,1):
            if seat in self.sess:
                await self.sync_player(seat)


    async def try_start(self):
        self._ensure_ai_ready()
        active_seats = [seat for seat in (0, 1) if self.seat_active(seat)]
        if len(active_seats) != 2:
            return
        if not (self.ready.get(0) and self.ready.get(1)):
            return

        if self.state is not None and not getattr(self.state, "ended", False):
            # 有未正常结束的旧对局，强制重置以允许重新开局
            self.state = None

        seed = random.randint(1, 10**9)
        first_turn = random.randint(0, 1)
        self.state = init_game(seed, first_turn=first_turn)
        self.ready = {0: False, 1: False}

        await self.broadcast({
            "type":"game_started",
            "seed": seed,
            "first_turn": first_turn,
        })
        # 给两位下发各自可见信息
        for seat, s in self.sess.items():
            view = self._view_payload(seat)
            await s.send({
                "type":"you_are",
                "seat": seat,
                "username": s.username,
                "opponent": self.get_player_name(1-seat),
                **view,
            })
        # 首回合：根据随机先手执行自动流程
        await self.step_auto()

    async def step_auto(self, *, lock_held: bool = False):
        # 自动下发当前行动方的 choices；如需要先摸牌则服务器执行摸并广播
        if not self.state or self.state.ended: return
        seat = self.state.turn
        me = self.sess.get(seat)
        ai_turn = self.is_ai_seat(seat)
        if not ai_turn and not me:
            return
        if self.state.pending_rob_kong is not None:
            kong_owner, tile = self.state.pending_rob_kong
            robber = 1 - kong_owner
            if seat != robber:
                return
            if not ai_turn and me:
                await self.sync_player(seat)
            actions = legal_choices(self.state, seat)
            if ai_turn:
                hu_action = next((a for a in actions if a.get("type") == "hu"), None)
                if hu_action:
                    await self._resolve_rob_kong_hu(seat, tile, lock_held=True)
                else:
                    await self._resolve_rob_kong_pass(seat, lock_held=True)
            elif me:
                await me.send({"type":"choices","actions":actions})
            return
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
        if ai_turn:
            await self._ai_take_turn(lock_held=lock_held)
            return
        if not me:
            return
        # 下发 choices
        choices = legal_choices(self.state, seat)
        await me.send({"type":"choices","actions":choices})

    async def step_after_discard(self, *, lock_held: bool = False):
        # 对手可响应：碰/杠/荣和/过
        if not self.state: return

        if self.is_ai_seat(self.state.turn):
            if lock_held:
                await self._ai_respond_to_discard(lock_held=True)
            else:
                async with self.lock:
                    await self._ai_respond_to_discard(lock_held=True)
            return

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

    async def _ai_take_turn(self, *, lock_held: bool):
        async def inner():
            if not self.state or self.state.ended:
                return
            seat = self.state.turn
            if not self.is_ai_seat(seat):
                return
            advice = advise_on_draw(self.state, seat) or {}
            action = advice.get("action")

            if action == "hu":
                is_kong_draw = (
                    self.state.last_draw_info is not None
                    and self.state.last_draw_info[0] == seat
                    and self.state.last_draw_info[1] == "kong"
                )
                reason = "zimo_kong" if is_kong_draw else "zimo"
                self.state = replace(self.state, ended=True)
                score_summary = compute_score_summary(self.state, seat, reason)
                await self.broadcast({
                    "type": "game_end",
                    "result": {"winner": seat, "reason": reason, "score": score_summary},
                    "final_view": self._final_view_payload(),
                })
                await update_game_scores(self, seat, reason, score_summary)
                return

            if action == "kong":
                tile = advice.get("tile")
                style = advice.get("style") or "concealed"
                if tile is None:
                    action = "discard"
                else:
                    try:
                        if style == "concealed":
                            self.state = kong_concealed(self.state, seat, tile)
                        elif style == "added":
                            if tile not in self.state.players[seat].hand:
                                raise ValueError("tile not in hand")
                            has_pong = any(
                                m.kind == "pong" and m.tiles and m.tiles[0] == tile
                                for m in self.state.players[seat].melds
                            )
                            if not has_pong:
                                raise ValueError("no pong to upgrade")
                            robber = 1 - seat
                            can_rob = can_hu_four_plus_one(
                                tuple(sorted(self.state.players[robber].hand + (tile,))),
                                self.state.players[robber].melds,
                            )
                            if can_rob:
                                self.state = replace(
                                    self.state,
                                    pending_rob_kong=(seat, tile),
                                    turn=robber,
                                )
                                await self.sync_all()
                                await self.step_auto(lock_held=True)
                                return
                            self.state = kong_added(self.state, seat, tile)
                        else:
                            # 默认按明杠处理（一般不会出现）
                            self.state = kong_concealed(self.state, seat, tile)
                            style = "concealed"
                    except Exception:
                        action = "discard"
                    else:
                        ev_payload = {"type": "kong", "style": style, "seat": seat}
                        if style != "concealed":
                            ev_payload["tile"] = tile
                        await self.broadcast({"type": "event", "ev": ev_payload})
                        await self.sync_all()
                        await self.step_auto(lock_held=True)
                        return

            if action != "discard":
                action = "discard"
            tile = advice.get("tile") if advice else None
            if tile is None:
                choices = legal_choices(self.state, seat)
                discard_choice = next((c for c in choices if c.get("type") == "discard"), None)
                if discard_choice:
                    tile = discard_choice.get("tile")
            if tile is None:
                return
            try:
                self.state = discard(self.state, seat, tile)
            except Exception:
                return
            await self.broadcast({"type": "event", "ev": {"type": "discard", "seat": seat, "tile": tile}})
            await self.sync_all()
            await self.step_after_discard(lock_held=True)

        if lock_held:
            await inner()
        else:
            async with self.lock:
                await inner()

    async def _ai_respond_to_discard(self, *, lock_held: bool):
        if not self.state or self.state.ended or self.state.last_discard is None:
            return

        async def inner():
            if not self.state or self.state.ended or self.state.last_discard is None:
                return
            seat = self.state.turn
            if not self.is_ai_seat(seat):
                return
            from_seat, tile_from = self.state.last_discard
            advice = advise_on_opponent_discard(self.state, seat) or {}
            action = advice.get("action") or "pass"
            tile = advice.get("tile") if advice.get("tile") is not None else tile_from

            if action == "hu":
                self.state = replace(self.state, ended=True)
                score_summary = compute_score_summary(self.state, seat, "ron")
                await self.broadcast({
                    "type": "game_end",
                    "result": {"winner": seat, "reason": "ron", "tile": tile, "score": score_summary},
                    "final_view": self._final_view_payload({seat: tile}),
                })
                await update_game_scores(self, seat, "ron", score_summary)
                return

            if action == "peng" and tile is not None:
                try:
                    self.state = claim_peng(self.state, seat, from_seat, tile)
                except Exception:
                    action = "pass"
                else:
                    await self.broadcast({"type": "event", "ev": {"type": "peng", "seat": seat, "tile": tile}})
                    await self.sync_all()
                    await self.step_auto(lock_held=True)
                    return

            if action == "kong" and tile is not None:
                try:
                    self.state = claim_kong_exposed(self.state, seat, from_seat, tile)
                except Exception:
                    action = "pass"
                else:
                    await self.broadcast({"type": "event", "ev": {"type": "kong", "style": "exposed", "seat": seat, "tile": tile}})
                    await self.sync_all()
                    await self.step_auto(lock_held=True)
                    return

            # pass 或无法执行其他动作
            self.state = replace(self.state, last_discard=None)
            await self.broadcast({"type": "event", "ev": {"type": "pass", "seat": seat}})
            await self.sync_all()
            await self.step_auto(lock_held=True)

        if lock_held:
            await inner()
        else:
            async with self.lock:
                await inner()

rooms: Dict[str, Room] = {}

async def attach(ws: WebSocket) -> Session:
    await ws.accept()
    return Session(ws)

@app.websocket("/ws/auth")
async def auth_ws_endpoint(ws: WebSocket):
    """需要认证的WebSocket端点"""
    sess = await attach(ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")

            if t == "authenticate":
                # 用户认证
                username = msg.get("username")
                password = msg.get("password")
                token = msg.get("token")  # token 认证更安全，优先使用

                if token:
                    session_info = authenticated_sessions.get(token)
                    if not session_info:
                        await sess.send({
                            "type": "error",
                            "detail": "登录状态已过期，请重新登录"
                        })
                        continue

                    user = await db.get_user_by_username(session_info.get("username", ""))
                    if not user:
                        await sess.send({
                            "type": "error",
                            "detail": "用户信息不存在，请重新登录"
                        })
                        continue

                    session_info["user_id"] = user["id"]
                    authenticated_sessions[token] = session_info

                    sess.user_id = user["id"]
                    sess.username = user["username"]
                    sess.vip_level = int(user.get("vip_level", 0))
                    await sess.send({
                        "type": "authentication_success",
                        "user": user
                    })
                    continue

                if username and password:
                    user = await db.authenticate_user(username, password)
                    if user:
                        sess.user_id = user["id"]
                        sess.username = user["username"]
                        sess.vip_level = int(user.get("vip_level", 0))
                        await sess.send({
                            "type": "authentication_success",
                            "user": user
                        })
                        continue
                    else:
                        await sess.send({
                            "type": "error",
                            "detail": "用户名或密码错误"
                        })
                        continue
                else:
                    await sess.send({
                        "type": "error",
                        "detail": "缺少认证信息"
                    })
                    continue

            elif t == "join_room":
                # 检查用户是否已认证
                if not sess.user_id or not sess.username:
                    await sess.send({"type":"error","detail":"请先登录"})
                    continue

                # 使用原始的join_room逻辑
                rid = msg.get("room_id","default")
                room = rooms.setdefault(rid, Room(rid))

                # 检查是否允许加入
                # 1. 检查是否房间已满且没有掉线的同名额玩家
                if len(room.sess) == 2:
                    # 检查是否有掉线的同名额玩家
                    seat_to_replace = None
                    for seat, existing_username in room.player_names.items():
                        if existing_username == sess.username and seat not in room.sess:
                            seat_to_replace = seat
                            break

                    if seat_to_replace is not None:
                        # 找到掉线的同名额玩家，允许重连
                        seat = seat_to_replace

                    else:
                        await sess.send({"type":"error","detail":"房间已满且没有找到匹配的离线玩家"})
                        continue
                else:
                    # 分配新座位
                    if 0 not in room.sess:
                        seat = 0
                    elif 1 not in room.sess:
                        seat = 1
                    else:
                        await sess.send({"type":"error","detail":"房间已满"})
                        continue

                # 检查重名限制：不允许同一个房间有两个相同名字的玩家
                for existing_seat, existing_username in room.player_names.items():
                    if existing_username == sess.username and existing_seat != seat:
                        if existing_seat in room.sess:
                            # 如果同名玩家已经在线，不允许新玩家加入并提示昵称已被使用
                            await sess.send({"type":"error","detail":"用户名已被此房间其他玩家使用"})
                            continue
                        else:
                            # 如果同名玩家离线，不允许新玩家加入
                            await sess.send({"type":"error","detail":"用户名已被此房间其他玩家占用"})
                            continue

                # 加入房间
                if room.is_ai_seat(seat):
                    room.disable_ai_practice()
                room.sess[seat] = sess
                room.player_names[seat] = sess.username
                sess.room, sess.seat = room, seat
                room.ready[seat] = False
                await sess.send({"type":"room_joined","room_id":rid,"seat":seat})
                room._ensure_ai_ready()
                await room.broadcast({"type":"ready_status","ready":dict(room.ready)})
                await room._broadcast_room_status()

                # 通知房间有玩家重新加入
                await room.broadcast({"type":"player_reconnected","seat":seat,"username":sess.username})

                # 如果房间有游戏状态，同步给重新加入的玩家
                if room.state:
                    await room.sync_player(seat)
                    # 如果游戏进行中且轮到该玩家，重新发送可执行操作
                    if room.state and not room.state.ended and room.state.turn == seat:
                        choices = legal_choices(room.state, seat)
                        await sess.send({"type":"choices","actions":choices})
                    # 如果是对家响应阶段，检查是否需要发送操作
                    elif room.state and not room.state.ended and room.state.last_discard is not None:
                        # 检查是否是对家的回合（可以响应）
                        if room.state.turn == seat:
                            choices = legal_choices(room.state, seat)
                            if choices:
                                await sess.send({"type":"choices","actions":choices})

            elif t == "ready":
                if not sess.room or sess.seat is None: continue
                sess.room.ready[sess.seat] = True
                sess.room._ensure_ai_ready()
                await sess.room.broadcast({"type":"ready_status","ready":dict(sess.room.ready)})
                await sess.room.try_start()

            elif t == "practice_ai":
                if not sess.room:
                    continue
                await sess.room.enable_ai_practice(sess)

            elif t == "request_hint":
                await handle_ai_hint_request(sess)

            elif t == "end_game":
                await handle_end_game_request(sess)

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
                                if tile not in st.players[sess.seat].hand:
                                    await sess.send({"type": "error", "detail": "tile not in hand"})
                                    continue
                                has_pong = any(
                                    m.kind == "pong" and m.tiles and m.tiles[0] == tile
                                    for m in st.players[sess.seat].melds
                                )
                                if not has_pong:
                                    await sess.send({"type": "error", "detail": "no pong to upgrade"})
                                    continue
                                robber = 1 - sess.seat
                                can_rob = can_hu_four_plus_one(
                                    tuple(sorted(st.players[robber].hand + (tile,))),
                                    st.players[robber].melds,
                                )
                                if can_rob:
                                    room.state = replace(
                                        st,
                                        pending_rob_kong=(sess.seat, tile),
                                        turn=robber,
                                    )
                                    await room.sync_all()
                                    await room.step_auto(lock_held=True)
                                    continue
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
                                is_kong_draw = (
                                    st.last_draw_info is not None
                                    and st.last_draw_info[0] == sess.seat
                                    and st.last_draw_info[1] == "kong"
                                )
                                reason = "zimo_kong" if is_kong_draw else "zimo"
                                room.state = replace(st, ended=True)
                                score_summary = compute_score_summary(room.state, sess.seat, reason)
                                await room.broadcast({
                                    "type": "game_end",
                                    "result": {"winner": sess.seat, "reason": reason, "score": score_summary},
                                    "final_view": room._final_view_payload(),
                                })
                                # 更新积分和记录
                                await update_game_scores(room, sess.seat, reason, score_summary)
                            else:
                                await sess.send({"type":"error","detail":"not hu"})
                        elif action.get("type") == "draw":
                            room.state, tile = draw(st, sess.seat)
                            await room.broadcast({"type":"event","ev":{"type":"draw","seat":sess.seat,"tile":tile}})
                            await room.sync_all()
                            await room.step_auto(lock_held=True)
                        else:
                            await sess.send({"type":"error","detail":"illegal or unsupported action in turn"})

                    # 对家响应阶段（有人刚出牌或存在抢杠）
                    else:
                        if st.pending_rob_kong is not None:
                            kong_owner, pending_tile = st.pending_rob_kong
                            robber = 1 - kong_owner
                            if sess.seat != robber:
                                await sess.send({"type": "error", "detail": "not your rob opportunity"})
                                continue
                            style = action.get("type")
                            if style == "hu" and action.get("style") == "rob":
                                merged = tuple(sorted(st.players[sess.seat].hand + (pending_tile,)))
                                if can_hu_four_plus_one(merged, st.players[sess.seat].melds):
                                    await room._resolve_rob_kong_hu(sess.seat, pending_tile, lock_held=True)
                                else:
                                    await sess.send({"type": "error", "detail": "not hu"})
                            elif style == "pass":
                                await room._resolve_rob_kong_pass(sess.seat, lock_held=True)
                            else:
                                await sess.send({"type": "error", "detail": "unsupported rob_kong action"})
                            continue

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
                                score_summary = compute_score_summary(room.state, sess.seat, "ron")
                                await room.broadcast({
                                    "type": "game_end",
                                    "result": {"winner": sess.seat, "reason": "ron", "tile": tile, "score": score_summary},
                                    "final_view": room._final_view_payload({sess.seat: tile}),
                                })
                                # 更新积分和记录
                                await update_game_scores(room, sess.seat, "ron", score_summary)
                            else:
                                await sess.send({"type":"error","detail":"not hu"})
                        else:
                            await sess.send({"type":"error","detail":"unsupported claim action"})

            else:
                await sess.send({"type":"error","detail":"unknown message type"})

    except WebSocketDisconnect:
        # 处理断线：保留玩家名称记录，允许重新加入
        r = sess.room
        seat = sess.seat
        if r and seat in r.sess:
            del r.sess[seat]
            if seat in r.ready:
                r.ready[seat] = False
            # 保留 player_names 记录，允许重新加入
            # 只有当两个玩家都断线时才重置游戏
            if len(r.sess) == 0:
                r.disable_ai_practice()
                r.state = None
                r.ready = {0: False, 1: False}
                # 清理玩家名称记录
                r.player_names.clear()
            # 通知房间玩家状态变化（包含在线/离线状态）
            await r._broadcast_room_status()
            await r.broadcast({"type":"ready_status","ready":dict(r.ready)})
            # 通知有玩家掉线
            await r.broadcast({"type":"player_disconnected","seat":seat,"username":sess.username})

async def update_game_scores(room: Room, winner_seat: int, reason: str, score_summary: dict):
    """更新游戏积分和记录"""
    try:
        loser_seat = 1 - winner_seat
        winner_session = room.sess.get(winner_seat)
        loser_session = room.sess.get(loser_seat)

        if not winner_session or not loser_session:
            return

        # 计算积分变化（基于番数）
        winner_fan = score_summary.get("players", {}).get(str(winner_seat), {}).get("fan_total", 0)

        # 积分变化规则：胜者获得 base * 2^fan，败者扣除同等积分
        score_change = fan_to_points(winner_fan)

        # 更新胜者积分
        await db.update_user_score(winner_session.user_id, score_change)

        # 更新败者积分
        await db.update_user_score(loser_session.user_id, -score_change)

        # 获取当前积分
        winner_info = await db.get_user_by_username(winner_session.username)
        loser_info = await db.get_user_by_username(loser_session.username)

        if winner_info and loser_info:
            # 添加对局记录
            await db.add_game_record(
                winner_session.user_id,
                loser_session.username,
                winner_seat == 0,  # 先手
                score_change,
                "win",
                winner_info["score"]
            )

            await db.add_game_record(
                loser_session.user_id,
                winner_session.username,
                loser_seat == 0,  # 先手
                -score_change,
                "lose",
                loser_info["score"]
            )

    except Exception as e:
        print(f"更新积分错误: {e}")


async def handle_ai_hint_request(sess: Session):
    """处理玩家请求AI提示的逻辑"""
    if not sess.room or sess.seat is None:
        await sess.send({"type": "ai_hint", "error": "尚未加入房间"})
        return

    if (sess.vip_level or 0) < 1:
        await sess.send({"type": "ai_hint", "error": "VIP等级不足，无法使用AI提示"})
        return

    room = sess.room
    hint_payload: Optional[dict] = None
    phase: Optional[str] = None

    async with room.lock:
        state = room.state
        if state is None or getattr(state, "ended", False):
            await sess.send({"type": "ai_hint", "error": "当前没有进行中的对局"})
            return

        if state.turn != sess.seat:
            await sess.send({"type": "ai_hint", "error": "当前不是你的操作回合"})
            return

        try:
            if state.last_discard is None:
                hand_len = len(state.players[sess.seat].hand)
                if hand_len % 3 != 2:
                    raise ValueError("hand not ready for advice")
                hint_payload = advise_on_draw(state, sess.seat) or {}
                phase = "self_turn"
            else:
                hint_payload = advise_on_opponent_discard(state, sess.seat) or {}
                phase = "opponent_discard"
        except AssertionError:
            await sess.send({"type": "ai_hint", "error": "当前状态无法生成AI提示"})
            return
        except Exception as e:
            print(f"AI hint error: {e}")
            await sess.send({"type": "ai_hint", "error": "AI提示计算失败，请稍后重试"})
            return

    if not hint_payload:
        await sess.send({"type": "ai_hint", "error": "AI暂时没有可用提示"})
        return

    await sess.send({"type": "ai_hint", "hint": hint_payload, "phase": phase})


async def handle_end_game_request(sess: Session):
    """允许当前玩家强制结束正在进行的对局"""
    if not sess.room or sess.seat is None:
        return

    room = sess.room
    final_view: Optional[dict] = None

    async with room.lock:
        state = room.state
        if state is None or getattr(state, "ended", False):
            return

        room.state = replace(state, ended=True)
        final_view = room._final_view_payload()
        room.ready = {0: False, 1: False}

    payload = {
        "type": "game_end",
        "result": {"winner": None, "reason": "abort", "by": sess.seat},
        "final_view": final_view,
    }
    await room.broadcast(payload)
    await room.broadcast({"type": "ready_status", "ready": dict(room.ready)})

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
                # 检查用户是否已认证
                if not sess.user_id or not sess.username:
                    await sess.send({"type":"error","detail":"请先登录"})
                    continue

                room = rooms.setdefault(rid, Room(rid))
                room = rooms.setdefault(rid, Room(rid))

                # 检查是否允许加入
                # 1. 检查是否房间已满且没有掉线的同名额玩家
                if len(room.sess) == 2:
                    # 检查是否有掉线的同名额玩家
                    seat_to_replace = None
                    for seat, existing_username in room.player_names.items():
                        if existing_username == sess.username and seat not in room.sess:
                            seat_to_replace = seat
                            break

                    if seat_to_replace is not None:
                        # 找到掉线的同名额玩家，允许重连
                        seat = seat_to_replace

                    else:
                        await sess.send({"type":"error","detail":"Room full and no matching offline player found"})
                        continue
                else:
                    # 分配新座位
                    if 0 not in room.sess:
                        seat = 0
                    elif 1 not in room.sess:
                        seat = 1
                    else:
                        await sess.send({"type":"error","detail":"Room full"})
                        continue

                # 检查重名限制：不允许同一个房间有两个相同名字的玩家
                for existing_seat, existing_username in room.player_names.items():
                    if existing_username == sess.username and existing_seat != seat:
                        if existing_seat in room.sess:
                            # 如果同名玩家已经在线，不允许新玩家加入并提示昵称已被使用
                            await sess.send({"type":"error","detail":"用户名已被此房间其他玩家使用"})
                            continue
                        else:
                            # 如果同名玩家离线，不允许新玩家加入
                            await sess.send({"type":"error","detail":"用户名已被此房间其他玩家占用"})
                            continue

                # 加入房间
                if room.is_ai_seat(seat):
                    room.disable_ai_practice()
                room.sess[seat] = sess
                room.player_names[seat] = sess.username
                sess.room, sess.seat = room, seat
                room.ready[seat] = False
                await sess.send({"type":"room_joined","room_id":rid,"seat":seat})
                room._ensure_ai_ready()
                await room.broadcast({"type":"ready_status","ready":dict(room.ready)})
                await room._broadcast_room_status()

                # 通知房间有玩家重新加入
                await room.broadcast({"type":"player_reconnected","seat":seat,"username":sess.username})

                # 如果房间有游戏状态，同步给重新加入的玩家
                if room.state:
                    await room.sync_player(seat)
                    # 如果游戏进行中且轮到该玩家，重新发送可执行操作
                    if room.state and not room.state.ended and room.state.turn == seat:
                        choices = legal_choices(room.state, seat)
                        await sess.send({"type":"choices","actions":choices})
                    # 如果是对家响应阶段，检查是否需要发送操作
                    elif room.state and not room.state.ended and room.state.last_discard is not None:
                        # 检查是否是对家的回合（可以响应）
                        if room.state.turn == seat:
                            choices = legal_choices(room.state, seat)
                            if choices:
                                await sess.send({"type":"choices","actions":choices})

            elif t == "ready":
                if not sess.room or sess.seat is None: continue
                sess.room.ready[sess.seat] = True
                sess.room._ensure_ai_ready()
                await sess.room.broadcast({"type":"ready_status","ready":dict(sess.room.ready)})
                await sess.room.try_start()

            elif t == "practice_ai":
                if not sess.room:
                    continue
                await sess.room.enable_ai_practice(sess)

            elif t == "end_game":
                await handle_end_game_request(sess)

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
                                if tile not in st.players[sess.seat].hand:
                                    await sess.send({"type": "error", "detail": "tile not in hand"})
                                    continue
                                has_pong = any(
                                    m.kind == "pong" and m.tiles and m.tiles[0] == tile
                                    for m in st.players[sess.seat].melds
                                )
                                if not has_pong:
                                    await sess.send({"type": "error", "detail": "no pong to upgrade"})
                                    continue
                                robber = 1 - sess.seat
                                can_rob = can_hu_four_plus_one(
                                    tuple(sorted(st.players[robber].hand + (tile,))),
                                    st.players[robber].melds,
                                )
                                if can_rob:
                                    room.state = replace(
                                        st,
                                        pending_rob_kong=(sess.seat, tile),
                                        turn=robber,
                                    )
                                    await room.sync_all()
                                    await room.step_auto(lock_held=True)
                                    continue
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
                                is_kong_draw = (
                                    st.last_draw_info is not None
                                    and st.last_draw_info[0] == sess.seat
                                    and st.last_draw_info[1] == "kong"
                                )
                                reason = "zimo_kong" if is_kong_draw else "zimo"
                                room.state = replace(st, ended=True)
                                score_summary = compute_score_summary(room.state, sess.seat, reason)
                                await room.broadcast({
                                    "type": "game_end",
                                    "result": {"winner": sess.seat, "reason": reason, "score": score_summary},
                                    "final_view": room._final_view_payload(),
                                })
                                await update_game_scores(room, sess.seat, reason, score_summary)
                            else:
                                await sess.send({"type":"error","detail":"not hu"})
                        elif action.get("type") == "draw":
                            room.state, tile = draw(st, sess.seat)
                            await room.broadcast({"type":"event","ev":{"type":"draw","seat":sess.seat,"tile":tile}})
                            await room.sync_all()
                            await room.step_auto(lock_held=True)
                        else:
                            await sess.send({"type":"error","detail":"illegal or unsupported action in turn"})

                    # 对家响应阶段（有人刚出牌或存在抢杠）
                    else:
                        if st.pending_rob_kong is not None:
                            kong_owner, pending_tile = st.pending_rob_kong
                            robber = 1 - kong_owner
                            if sess.seat != robber:
                                await sess.send({"type": "error", "detail": "not your rob opportunity"})
                                continue
                            style = action.get("type")
                            if style == "hu" and action.get("style") == "rob":
                                merged = tuple(sorted(st.players[sess.seat].hand + (pending_tile,)))
                                if can_hu_four_plus_one(merged, st.players[sess.seat].melds):
                                    await room._resolve_rob_kong_hu(sess.seat, pending_tile, lock_held=True)
                                else:
                                    await sess.send({"type": "error", "detail": "not hu"})
                            elif style == "pass":
                                await room._resolve_rob_kong_pass(sess.seat, lock_held=True)
                            else:
                                await sess.send({"type": "error", "detail": "unsupported rob_kong action"})
                            continue

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
                                score_summary = compute_score_summary(room.state, sess.seat, "ron")
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
        # 处理断线：保留玩家名称记录，允许重新加入
        r = sess.room
        seat = sess.seat
        if r and seat in r.sess:
            del r.sess[seat]
            if seat in r.ready:
                r.ready[seat] = False
            # 保留 player_names 记录，允许重新加入
            # 只有当两个玩家都断线时才重置游戏
            if len(r.sess) == 0:
                r.disable_ai_practice()
                r.state = None
                r.ready = {0: False, 1: False}
                # 清理玩家名称记录
                r.player_names.clear()
            # 通知房间玩家状态变化（包含在线/离线状态）
            await r._broadcast_room_status()
            await r.broadcast({"type":"ready_status","ready":dict(r.ready)})
            # 通知有玩家掉线
            await r.broadcast({"type":"player_disconnected","seat":seat,"username":sess.username})


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    return FileResponse(INDEX_FILE)


def _resolve_static_file(path_segment: str) -> Optional[Path]:
    target = (STATIC_DIR / path_segment).resolve()
    try:
        target.relative_to(STATIC_DIR)
    except ValueError:
        return None
    return target if target.is_file() else None


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_assets(full_path: str) -> FileResponse:
    if full_path.startswith("api"):
        raise HTTPException(status_code=404)

    static_file = _resolve_static_file(full_path)
    if static_file:
        return FileResponse(static_file)

    if "." in full_path.rsplit("/", 1)[-1]:
        raise HTTPException(status_code=404)

    return FileResponse(INDEX_FILE)
