import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ShiftView from '../views/ShiftView.vue'
import LoginView from '../views/LoginView.vue' // LoginViewをインポート

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: ShiftView, // デフォルトをShiftViewに変更
      meta: { requiresAuth: true } // このルートは認証が必要
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/about', // Aboutページは残す場合
      name: 'about',
      component: () => import('../views/AboutView.vue')
    }
  ]
})

// ナビゲーションガード
router.beforeEach((to, from, next) => {
  const loggedIn = localStorage.getItem('access_token');

  if (to.matched.some(record => record.meta.requiresAuth) && !loggedIn) {
    // 認証が必要なページにアクセスしようとしていて、ログインしていない場合
    next('/login');
  } else {
    next(); // それ以外の場合は通常通り遷移
  }
});

export default router
