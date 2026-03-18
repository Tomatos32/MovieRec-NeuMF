import { useUserStore } from '@/stores/user'

export const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
    const userStore = useUserStore()
    const headers = new Headers(options.headers || {})

    if (userStore.token) {
        headers.set('Authorization', `Bearer ${userStore.token}`)
    }
    if (!headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json')
    }

    const response = await fetch(url, {
        ...options,
        headers
    })

    if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
            userStore.logout()
        }
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `Request failed with status ${response.status}`)
    }

    return response.json()
}
