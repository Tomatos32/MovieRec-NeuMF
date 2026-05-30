import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { Movie } from '@/types'
import { useUserStore } from './user'

export const useHistoryStore = defineStore('history', () => {
    const userStore = useUserStore()

    const browsingHistory = ref<Movie[]>([])
    const ratingHistory = ref<Movie[]>([])

    const loadHistory = () => {
        const userId = userStore.userId
        if (userId) {
            // 迁移旧的未隔离历史数据并在迁移后销毁，避免后续登录的用户重复继承
            const legacyBrowsing = localStorage.getItem('browsingHistory')
            if (legacyBrowsing) {
                if (!localStorage.getItem(`browsingHistory_${userId}`)) {
                    localStorage.setItem(`browsingHistory_${userId}`, legacyBrowsing)
                }
                localStorage.removeItem('browsingHistory')
            }

            const legacyRating = localStorage.getItem('ratingHistory')
            if (legacyRating) {
                if (!localStorage.getItem(`ratingHistory_${userId}`)) {
                    localStorage.setItem(`ratingHistory_${userId}`, legacyRating)
                }
                localStorage.removeItem('ratingHistory')
            }

            browsingHistory.value = JSON.parse(localStorage.getItem(`browsingHistory_${userId}`) || '[]')
            ratingHistory.value = JSON.parse(localStorage.getItem(`ratingHistory_${userId}`) || '[]')
        } else {
            browsingHistory.value = []
            ratingHistory.value = []
        }
    }

    // 初始加载
    loadHistory()

    // 监听用户变动，自动切换对应用户的历史记录
    watch(() => userStore.userId, () => {
        loadHistory()
    })

    const addBrowsingHistory = (movie: Movie) => {
        const userId = userStore.userId
        if (!userId) return

        browsingHistory.value = browsingHistory.value.filter(m => m.movieId !== movie.movieId)
        browsingHistory.value.unshift(movie)
        // 保持最多 50 条
        if (browsingHistory.value.length > 50) {
            browsingHistory.value.pop()
        }
        localStorage.setItem(`browsingHistory_${userId}`, JSON.stringify(browsingHistory.value))
    }

    const addRatingHistory = (movie: Movie) => {
        const userId = userStore.userId
        if (!userId) return

        ratingHistory.value = ratingHistory.value.filter(m => m.movieId !== movie.movieId)
        ratingHistory.value.unshift(movie)
        if (ratingHistory.value.length > 50) {
            ratingHistory.value.pop()
        }
        localStorage.setItem(`ratingHistory_${userId}`, JSON.stringify(ratingHistory.value))
    }

    const clearHistory = () => {
        const userId = userStore.userId
        if (!userId) return

        browsingHistory.value = []
        ratingHistory.value = []

        // 彻底清理当前用户的隔离沙盒
        localStorage.removeItem(`browsingHistory_${userId}`)
        localStorage.removeItem(`ratingHistory_${userId}`)

        // 斩草除根：额外强制清理任何可能残留的公共沙盒键名
        localStorage.removeItem('browsingHistory')
        localStorage.removeItem('ratingHistory')
    }

    return {
        browsingHistory,
        ratingHistory,
        addBrowsingHistory,
        addRatingHistory,
        clearHistory
    }
})
