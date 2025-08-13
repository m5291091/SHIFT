import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ShiftView from '../views/ShiftView.vue' // 1. ShiftViewをインポート

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/shifts', // 2. パスを/shiftsに変更
      name: 'shifts',   // 3. 名前をshiftsに変更
      component: ShiftView, // 4. コンポーネントをShiftViewに変更
    },
  ],
})

export default router