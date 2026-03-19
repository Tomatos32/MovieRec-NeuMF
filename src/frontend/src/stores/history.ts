import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Movie } from '@/types'

export const useHistoryStore = defineStore('history', () => {
    // We store the full Movie object to display them easily in the history pages
    const browsingHistory = ref<Movie[]>(JSON.parse(localStorage.getItem('browsingHistory') || '[]'))
    const ratingHistory = ref<Movie[]>(JSON.parse(localStorage.getItem('ratingHistory') || '[]'))

    const addBrowsingHistory = (movie: Movie) => {
        // Remove if already exists to move it to the top
        browsingHistory.value = browsingHistory.value.filter(m => m.movieId !== movie.movieId)
        browsingHistory.value.unshift(movie)
        // Keep only top 50
        if (browsingHistory.value.length > 50) {
            browsingHistory.value.pop()
        }
        localStorage.setItem('browsingHistory', JSON.stringify(browsingHistory.value))
    }

    const addRatingHistory = (movie: Movie) => {
        ratingHistory.value = ratingHistory.value.filter(m => m.movieId !== movie.movieId)
        ratingHistory.value.unshift(movie)
        if (ratingHistory.value.length > 50) {
            ratingHistory.value.pop()
        }
        localStorage.setItem('ratingHistory', JSON.stringify(ratingHistory.value))
    }

    const clearHistory = () => {
        browsingHistory.value = []
        ratingHistory.value = []
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
