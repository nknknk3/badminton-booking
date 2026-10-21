import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'bb_access_token'

function bootstrapToken() {
  const url = new URL(window.location.href)
  const token = url.searchParams.get('token')
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
    url.searchParams.delete('token')
    window.history.replaceState({}, '', url.toString())
  }
}

bootstrapToken()

export const getToken = () => localStorage.getItem(TOKEN_KEY) || ''

const client = axios.create({
  baseURL: '/api',
  timeout: 25000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers['X-Access-Token'] = token
  }
  return config
})

export interface ApiFailure {
  status: number
  message: string
}

export function errorMessage(err: unknown, fallback = '操作失败'): string {
  const axiosErr = err as AxiosError<{ detail?: unknown; message?: string }>
  const data = axiosErr?.response?.data
  if (data) {
    const detail = data.detail
    if (typeof detail === 'string' && detail) return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string }
      if (first?.msg) return first.msg
    }
    if (typeof data.message === 'string' && data.message) return data.message
  }
  if (axiosErr?.response?.status === 401) return '访问令牌无效，请在设置页填写'
  if (axiosErr?.code === 'ECONNABORTED') return '请求超时，请检查场馆网络'
  if (axiosErr?.message === 'Network Error') return '无法连接本地服务'
  return fallback
}

export default client
