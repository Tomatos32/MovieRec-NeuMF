import { ref } from 'vue'
import type { Movie, RecommendationResponse, FeedbackPayload } from '../types'
import { fetchWithAuth } from '../api/fetch'

/**
 * 推荐数据获取与反馈上报 composable
 * 封装所有与后端 Spring Boot API 的交互逻辑
 */
export const useRecommendations = () => {
    const movies = ref<Movie[]>([])
    const isLoading = ref(false)
    const hasError = ref(false)
    const errorMessage = ref('')
    const isColdStart = ref(false)

    /**
     * 拉取推荐列表
     * GET /api/recommendations?userId={id}
     */
    const fetchRecommendations = async (userId: number) => {
        isLoading.value = true
        hasError.value = false
        errorMessage.value = ''

        const url = `/api/recommendations?userId=${userId}`
        console.log('[Recommendations] 请求:', url)

        try {
            const result: RecommendationResponse = await fetchWithAuth(url)
            console.log('[Recommendations] 响应数据:', result)

            movies.value = result.data ?? []
            isColdStart.value = result.mode === 'cold-start'
        } catch (err) {
            console.error('[Recommendations] 请求失败:', err)
            hasError.value = true
            errorMessage.value = err instanceof Error ? err.message : '网络请求失败'
            // 降级为空列表，不阻塞 UI
            movies.value = []
        } finally {
            isLoading.value = false
        }
    }

    /**
     * 上报用户行为至 Kafka 管道
     * POST /api/feedback
     */
    const sendFeedback = async (payload: FeedbackPayload) => {
        try {
            await fetchWithAuth('/api/feedback', {
                method: 'POST',
                // fetchWithAuth already adds Content-Type
                body: JSON.stringify(payload),
            })
        } catch {
            // 反馈上报失败不阻塞前端交互
            console.warn('[Feedback] 上报失败，将在下次请求时重试')
        }
    }

    return {
        movies,
        isLoading,
        hasError,
        errorMessage,
        isColdStart,
        fetchRecommendations,
        sendFeedback,
    }
}
