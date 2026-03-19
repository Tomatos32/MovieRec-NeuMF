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
            redirect: '/popular'
        },
        {
            path: '/popular',
            name: 'popular',
            component: () => import('@/views/Home.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/personalized',
            name: 'personalized',
            component: () => import('@/views/Home.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/all',
            name: 'all-movies',
            component: () => import('@/views/Home.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/history/browsing',
            name: 'browsing-history',
            component: () => import('@/views/Home.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/history/rating',
            name: 'rating-history',
            component: () => import('@/views/Home.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/profile',
            name: 'profile',
            component: () => import('@/views/Profile.vue'),
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
