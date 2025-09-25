import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
    },
    {
      path: '/join',
      name: 'join',
      component: () => import('../views/JoinRoomView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/game',
      name: 'game',
      component: () => import('../views/GameView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/victory',
      name: 'victory',
      component: () => import('../views/VictoryView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../views/ProfileView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const isLoggedIn = localStorage.getItem('mahjong_logged_in') === 'true'

  if (to.meta.requiresAuth && !isLoggedIn) {
    // 需要认证但未登录，重定向到登录页
    next('/')
  } else if (to.path === '/' && isLoggedIn) {
    // 已登录用户访问登录页，重定向到加入房间页
    next('/join')
  } else {
    next()
  }
})

export default router
