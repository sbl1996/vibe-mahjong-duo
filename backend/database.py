# -*- coding: utf-8 -*-
import asyncio
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib

class Database:
    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """连接到数据库"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            await self._connection.execute("PRAGMA foreign_keys = ON")
            await self._connection.execute("PRAGMA journal_mode = WAL")
            await self._connection.commit()

    async def close(self):
        """关闭数据库连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def init_tables(self):
        """初始化数据库表"""
        await self.connect()

        # 创建用户表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                score INTEGER DEFAULT 1000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建对局记录表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS game_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                opponent_username TEXT NOT NULL,
                game_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_first_hand BOOLEAN NOT NULL,
                score_change INTEGER NOT NULL,
                result TEXT NOT NULL,
                final_score INTEGER NOT NULL,
                FOREIGN KEY (player_id) REFERENCES users(id)
            )
        ''')

        await self._connection.commit()

    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    async def create_user(self, username: str, password: str, initial_score: int = 1000) -> bool:
        """创建用户"""
        try:
            await self.connect()
            password_hash = self._hash_password(password)

            await self._connection.execute(
                "INSERT INTO users (username, password_hash, score) VALUES (?, ?, ?)",
                (username, password_hash, initial_score)
            )
            await self._connection.commit()
            return True
        except aiosqlite.IntegrityError:
            # 用户名已存在
            return False
        except Exception as e:
            print(f"创建用户错误: {e}")
            return False

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户登录"""
        try:
            await self.connect()
            password_hash = self._hash_password(password)

            cursor = await self._connection.execute(
                "SELECT id, username, score FROM users WHERE username = ? AND password_hash = ?",
                (username, password_hash)
            )
            result = await cursor.fetchone()

            if result:
                return {
                    "id": result[0],
                    "username": result[1],
                    "score": result[2]
                }
            return None
        except Exception as e:
            print(f"验证用户错误: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户信息"""
        try:
            await self.connect()
            cursor = await self._connection.execute(
                "SELECT id, username, score FROM users WHERE username = ?",
                (username,)
            )
            result = await cursor.fetchone()

            if result:
                return {
                    "id": result[0],
                    "username": result[1],
                    "score": result[2]
                }
            return None
        except Exception as e:
            print(f"获取用户信息错误: {e}")
            return None

    async def update_user_score(self, user_id: int, score_change: int) -> bool:
        """更新用户积分"""
        try:
            await self.connect()
            await self._connection.execute(
                "UPDATE users SET score = score + ? WHERE id = ?",
                (score_change, user_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            print(f"更新积分错误: {e}")
            return False

    async def add_game_record(self, player_id: int, opponent_username: str,
                            is_first_hand: bool, score_change: int,
                            result: str, final_score: int) -> bool:
        """添加对局记录"""
        try:
            await self.connect()
            await self._connection.execute(
                """INSERT INTO game_records
                   (player_id, opponent_username, is_first_hand, score_change, result, final_score)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (player_id, opponent_username, is_first_hand, score_change, result, final_score)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            print(f"添加对局记录错误: {e}")
            return False

    async def get_user_game_records(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户对局记录"""
        try:
            await self.connect()
            cursor = await self._connection.execute(
                """SELECT id, opponent_username, game_time, is_first_hand,
                          score_change, result, final_score
                   FROM game_records
                   WHERE player_id = ?
                   ORDER BY game_time DESC
                   LIMIT ?""",
                (user_id, limit)
            )
            rows = await cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "opponent_username": row[1],
                    "game_time": row[2],
                    "is_first_hand": bool(row[3]),
                    "score_change": row[4],
                    "result": row[5],
                    "final_score": row[6]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"获取对局记录错误: {e}")
            return []

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """获取用户统计信息"""
        try:
            await self.connect()

            # 获取总对局数
            cursor = await self._connection.execute(
                "SELECT COUNT(*) FROM game_records WHERE player_id = ?",
                (user_id,)
            )
            total_games = (await cursor.fetchone())[0]

            # 获取胜利次数
            cursor = await self._connection.execute(
                "SELECT COUNT(*) FROM game_records WHERE player_id = ? AND result = 'win'",
                (user_id,)
            )
            wins = (await cursor.fetchone())[0]

            # 获取失败次数
            cursor = await self._connection.execute(
                "SELECT COUNT(*) FROM game_records WHERE player_id = ? AND result = 'lose'",
                (user_id,)
            )
            losses = (await cursor.fetchone())[0]

            # 获取平局次数
            cursor = await self._connection.execute(
                "SELECT COUNT(*) FROM game_records WHERE player_id = ? AND result = 'draw'",
                (user_id,)
            )
            draws = (await cursor.fetchone())[0]

            # 获取最大积分变化
            cursor = await self._connection.execute(
                "SELECT MAX(ABS(score_change)) FROM game_records WHERE player_id = ?",
                (user_id,)
            )
            max_score_change = (await cursor.fetchone())[0] or 0

            return {
                "total_games": total_games,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": (wins / total_games * 100) if total_games > 0 else 0,
                "max_score_change": max_score_change
            }
        except Exception as e:
            print(f"获取统计信息错误: {e}")
            return {}

    async def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取排行榜"""
        try:
            await self.connect()
            cursor = await self._connection.execute(
                """SELECT id, username, score, created_at
                   FROM users
                   ORDER BY score DESC
                   LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "username": row[1],
                    "score": row[2],
                    "created_at": row[3]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"获取排行榜错误: {e}")
            return []

# 全局数据库实例
db = Database()

async def init_database():
    """初始化数据库"""
    await db.init_tables()

    # 创建默认用户
    default_users = [
        {"username": "A", "password": "A", "score": 1000},
        {"username": "B", "password": "B", "score": 1000},
        {"username": "C", "password": "C", "score": 1000},
    ]

    for user in default_users:
        exists = await db.get_user_by_username(user["username"])
        if not exists:
            await db.create_user(user["username"], user["password"], user["score"])
            print(f"创建默认用户: {user['username']}")