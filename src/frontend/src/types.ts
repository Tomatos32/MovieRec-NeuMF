/** 电影推荐数据类型定义 */

export type Movie = {
    movieId: number
    title: string
    genres: string
    score: number
    posterUrl: string
    rating?: number
}

export type RecommendationResponse = {
    data: Movie[]
    mode: 'personalized' | 'cold-start'
    userId: number
}

export type FeedbackPayload = {
    userId: number
    movieId: number
    actionType: 'click' | 'dislike' | 'wishlist' | 'rate'
    rating?: number
    timestamp: number
}
