<template>
  <div class="page">
    <div class="game-card">
      <header class="game-header">
        <div class="title-block">
          <h1>Mahjong Duo</h1>
        </div>
        <nav class="navigation" v-if="user">
          <router-link to="/join" class="nav-link" active-class="active">开一局</router-link>
          <router-link to="/profile" class="nav-link" active-class="active">个人信息</router-link>
          <button
            v-if="gameInProgress"
            class="endgame-btn"
            type="button"
            @click="handleEndGame"
          >
            结束对局
          </button>
          <button class="logout-btn" @click="handleLogout">退出登录</button>
        </nav>
        <div class="header-status">
          <div class="status-line">
            <span v-if="connected">
              <template v-if="status.players">
                座位 {{ seat ?? '?' }}｜对手 {{ opponent || '?' }}
                <span class="player-status">
                  <span class="player-status-item">
                    <span class="status-dot" :class="status.players[seat === 0 ? 0 : 1] ? 'online' : 'offline'"></span>
                    <span>我方</span>
                  </span>
                  <span class="player-status-item">
                    <span class="status-dot" :class="status.players[seat === 0 ? 1 : 0] ? 'online' : 'offline'"></span>
                    <span>对方</span>
                  </span>
                </span>
              </template>
              <template v-else>
                等待对手中
              </template>
            </span>
            <span v-else>未加入房间</span>
          </div>
        </div>
      </header>

      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'

const router = useRouter()
const store = useGameStore()
const {
  user,
  connected,
  status,
  seat,
  opponent,
  gameInProgress,
  endGame: requestEndGame,
} = store

const handleLogout = () => {
  store.setUser(null)
  store.clearRoomInfo()
  store.resetState()
  router.push('/')
}

const handleEndGame = () => {
  if (!gameInProgress.value) return
  const confirmed = window.confirm('确定要结束当前对局吗？')
  if (!confirmed) return
  requestEndGame()
}
</script>

<style>
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
  padding: 16px 16px 64px;
  box-sizing: border-box;
}

.game-card {
  width: min(1260px, 100%);
  background: linear-gradient(145deg, rgba(18, 26, 48, 0.95), rgba(7, 12, 24, 0.92));
  border-radius: 28px;
  padding: 32px;
  box-shadow:
    0 40px 80px rgba(4, 8, 16, 0.65),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(90, 122, 191, 0.24);
  backdrop-filter: blur(12px);
}

.game-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
}

.navigation {
  display: flex;
  gap: 16px;
  align-items: center;
}

.nav-link {
  color: #b9c9ff;
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.3s ease;
  border: 1px solid transparent;
}

.nav-link:hover {
  background: rgba(102, 126, 234, 0.2);
  color: #f9fbff;
}

.nav-link.active {
  background: rgba(102, 126, 234, 0.3);
  color: #f9fbff;
  border-color: rgba(102, 126, 234, 0.5);
}

.logout-btn {
  background: rgba(231, 76, 60, 0.2);
  color: #ff6b6b;
  border: 1px solid rgba(231, 76, 60, 0.4);
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.3s ease;
  cursor: pointer;
  text-decoration: none;
  font-size: 0.95rem;
}

.logout-btn:hover {
  background: rgba(231, 76, 60, 0.3);
  color: #ff5252;
  border-color: rgba(231, 76, 60, 0.6);
}

.endgame-btn {
  background: rgba(255, 193, 7, 0.18);
  color: #ffca60;
  border: 1px solid rgba(255, 193, 7, 0.4);
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.3s ease;
  cursor: pointer;
  text-decoration: none;
  font-size: 0.95rem;
}

.endgame-btn:hover {
  background: rgba(255, 193, 7, 0.28);
  color: #ffd88c;
  border-color: rgba(255, 193, 7, 0.6);
}

.title-block h1 {
  margin: 0;
  font-size: 2.4rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #f9fbff;
  text-shadow:
    0 0 18px rgba(82, 117, 255, 0.45),
    0 0 4px rgba(255, 255, 255, 0.2);
}

.header-status {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #b9c9ff;
  font-size: 0.98rem;
  letter-spacing: 0.04em;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-radius: 999px;
  background: rgba(16, 28, 58, 0.72);
  border: 1px solid rgba(88, 120, 210, 0.35);
  box-shadow: inset 0 0 12px rgba(9, 13, 29, 0.6);
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
  background: #8491b7;
  box-shadow: 0 0 8px rgba(132, 145, 183, 0.6);
}

.status-dot.online {
  background: #51ff9d;
  box-shadow:
    0 0 24px rgba(81, 255, 157, 0.8),
    0 0 6px rgba(81, 255, 157, 0.9);
}

.status-dot.offline {
  background: #ff6c6c;
  box-shadow: 0 0 16px rgba(255, 108, 108, 0.75);
}

.player-status {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin-left: 8px;
}

.player-status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.player-status-item .status-dot {
  width: 10px;
  height: 10px;
}

.connection-card {
  background: rgba(13, 20, 40, 0.9);
  border-radius: 22px;
  padding: 24px 28px;
  border: 1px solid rgba(96, 128, 212, 0.32);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 24px 48px rgba(10, 14, 32, 0.55);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-group label {
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: #9db3ff;
}

.field-group input {
  background: rgba(10, 16, 30, 0.9);
  border: 1px solid rgba(92, 120, 205, 0.4);
  border-radius: 14px;
  padding: 14px;
  color: #f3f6ff;
  font-size: 1.02rem;
  transition: border-color 0.2s ease;
}

.field-group input:focus {
  outline: none;
  border-color: rgba(119, 149, 255, 0.9);
  box-shadow: 0 0 0 2px rgba(82, 117, 255, 0.25);
}

.action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 8px;
}

button {
  border-radius: 14px;
  padding: 12px 24px;
  font-size: 1rem;
  letter-spacing: 0.04em;
  border: none;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  background: rgba(17, 30, 58, 0.85);
  color: #dce7ff;
  border: 1px solid rgba(101, 131, 213, 0.4);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

button:not(:disabled):hover {
  transform: translateY(-2px);
}

.ready-button {
  min-width: 140px;
  background: rgba(32, 49, 94, 0.88);
}

.ready-button.ready {
  background: rgba(71, 216, 142, 0.92);
  color: #072417;
  border-color: rgba(71, 216, 142, 0.95);
}

.ready-button:not(.ready):not(.connecting) {
  background: linear-gradient(135deg, #4f9aff, #5270ff);
  color: #fff;
  box-shadow: 0 12px 24px rgba(82, 112, 255, 0.35);
}

.ready-button:not(.ready):not(.connecting):hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 16px 28px rgba(82, 112, 255, 0.45);
}

.ready-button.connecting {
  background: rgba(32, 49, 94, 0.6);
  color: #b9c9ff;
  box-shadow: none;
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

.muted {
  color: rgba(180, 196, 244, 0.62);
}

@media (max-width: 768px) {
  .game-card {
    padding: 24px;
  }

  .game-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 18px;
  }

  .title-block h1 {
    font-size: 2rem;
  }

  .status-line {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
