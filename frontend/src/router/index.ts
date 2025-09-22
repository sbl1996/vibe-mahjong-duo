import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'join',
      component: () => import('../views/JoinRoomView.vue'),
    },
    {
      path: '/game',
      name: 'game',
      component: () => import('../views/GameView.vue'),
    },
    {
      path: '/victory',
      name: 'victory',
      component: () => import('../views/VictoryView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

export default router
