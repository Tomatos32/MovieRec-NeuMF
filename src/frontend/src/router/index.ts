import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/login',
            name: 'login',
            component: () => import('@/views/Login.vue'),
            meta: { requiresGuest: true }
        },
        {
            path: '/',
            name: 'home',
            component: () => import('@/views/Home.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/admin',
            name: 'admin',
            component: () => import('@/views/Admin.vue'),
            meta: { requiresAuth: true, requiresAdmin: true }
        }
    ]
})

router.beforeEach((to, _from, next) => {
    const userStore = useUserStore()

    if (to.meta.requiresAuth && !userStore.isAuthenticated) {
        return next('/login')
    }

    if (to.meta.requiresGuest && userStore.isAuthenticated) {
        if (userStore.user?.username === 'admin') {
            return next('/admin')
        }
        return next('/')
    }

    if (to.meta.requiresAdmin && userStore.user?.username !== 'admin') {
        return next('/')
    }

    next()
})

export default router
