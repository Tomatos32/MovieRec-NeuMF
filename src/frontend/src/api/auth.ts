export const BASE_URL = '/api/auth'

export const loginApi = async (credentials: any) => {
    const response = await fetch(`${BASE_URL}/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(credentials)
    })

    if (!response.ok) {
        throw new Error('登录失败，请检查用户名或密码')
    }

    return response.json()
}

export const registerApi = async (userData: any) => {
    const response = await fetch(`${BASE_URL}/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(userData)
    })

    if (!response.ok) {
        throw new Error('注册失败，可能用户名已存在')
    }

    return response.json()
}
