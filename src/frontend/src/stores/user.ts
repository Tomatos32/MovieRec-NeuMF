import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { loginApi, registerApi } from '@/api/auth'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
    const token = ref(localStorage.getItem('token') || '')
    const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

    const isAuthenticated = computed(() => !!token.value)

    /** 当前登录用户的数字 ID（来自后端 AuthResponse.userId） */
    const userId = computed<number | null>(() => user.value?.id ?? null)

    const login = async (credentials: any) => {
        try {
            const data = await loginApi(credentials)
            const { token: newToken, username, userId: uid } = data
            const savedUser = { username, id: uid }

            token.value = newToken
            user.value = savedUser

            localStorage.setItem('token', newToken)
            localStorage.setItem('user', JSON.stringify(savedUser))

            return { token: newToken, user: savedUser }
        } catch (error) {
            throw error
        }
    }

    const register = async (userData: any) => {
        try {
            const data = await registerApi(userData)
            // 注册成功后也可直接登录
            if (data?.token) {
                const { token: newToken, username, userId: uid } = data
                const savedUser = { username, id: uid }
                token.value = newToken
                user.value = savedUser
                localStorage.setItem('token', newToken)
                localStorage.setItem('user', JSON.stringify(savedUser))
            }
            return data
        } catch (error) {
            throw error
        }
    }

    const logout = () => {
        token.value = ''
        user.value = null
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        if (router.currentRoute.value.path !== '/login') {
            router.push('/login')
        }
    }

    return {
        token,
        user,
        userId,
        isAuthenticated,
        login,
        register,
        logout
    }
})
