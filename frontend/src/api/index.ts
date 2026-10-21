import client from './client'

/* ------------------------------- types ------------------------------- */
export interface AuthStatus {
  logged_in: boolean
  message: string
  has_cookie_file: boolean
  cookie_count: number
  captured_at: string | null
}

export interface MessageResponse {
  success: boolean
  message: string
}

export interface Slot {
  begin_time: string
  end_time: string
  field_state: number
  time_status: number
}

export interface SlotsResponse {
  date: string
  slots: Slot[]
  error: string | null
}

export interface Field {
  field_no: string
  field_name: string
  field_type_no: string
  begin_time: string
  end_time: string
  price: string
  field_state: number
  time_status: number
}

export interface FieldsResponse {
  fields: Field[]
  error: string | null
}

export interface DatesResponse {
  dates: string[]
  error: string | null
}

export interface OrderResponse {
  success: boolean
  message: string
}

export interface BookingRecord {
  id: number
  task_id: number | null
  field_no: string
  field_name: string
  date: string
  begin_time: string
  end_time: string
  status: string
  message: string
  created_at: string
}

export interface Task {
  id: number
  name: string
  target_date: string
  target_times: string[]
  poll_interval: number
  start_at: string | null
  enabled: boolean
  status: string
  next_run_at: string | null
  created_at: string
  updated_at: string
}

export interface CreateTaskRequest {
  name: string
  target_date: string
  target_times: string[]
  poll_interval: number
  start_at: string | null
}

export interface SystemInfo {
  version: string
  frozen: boolean
  venue_no: string
  field_type: string
  auth_required: boolean
  poll_default: number
  lead_minutes: number
  max_runtime_hours: number
  data_dir: string
}

/* -------------------------------- auth -------------------------------- */
export async function checkStatus(): Promise<AuthStatus> {
  const { data } = await client.get<AuthStatus>('/auth/status')
  return data
}

export async function uploadSession(file: File): Promise<MessageResponse> {
  const form = new FormData()
  form.append('cookie_file', file)
  const { data } = await client.post<MessageResponse>('/auth/login', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function logout(): Promise<MessageResponse> {
  const { data } = await client.post<MessageResponse>('/auth/logout')
  return data
}

/* ------------------------------- venues ------------------------------- */
export async function getDates(): Promise<DatesResponse> {
  const { data } = await client.get<DatesResponse>('/venues/dates')
  return data
}

export async function getSlots(date: string, all = false): Promise<SlotsResponse> {
  const { data } = await client.get<SlotsResponse>('/venues/slots', {
    params: { date, all },
  })
  return data
}

export async function getFields(
  date: string,
  begin: string,
  end: string
): Promise<FieldsResponse> {
  const { data } = await client.get<FieldsResponse>('/venues/fields', {
    params: { date, begin_time: begin, end_time: end },
  })
  return data
}

/* ------------------------------ bookings ------------------------------ */
export async function placeOrder(payload: {
  date: string
  begin_time: string
  end_time: string
  field_no: string
}): Promise<OrderResponse> {
  const { data } = await client.post<OrderResponse>('/bookings/order', payload)
  return data
}

export async function getHistory(limit = 50): Promise<BookingRecord[]> {
  const { data } = await client.get<BookingRecord[]>('/bookings/history', {
    params: { limit },
  })
  return data
}

export async function deleteRecord(id: number): Promise<void> {
  await client.delete(`/bookings/history/${id}`)
}

export async function clearHistory(): Promise<void> {
  await client.delete('/bookings/history')
}

/* -------------------------------- tasks ------------------------------- */
export async function getTasks(): Promise<Task[]> {
  const { data } = await client.get<Task[]>('/tasks')
  return data
}

export async function createTask(payload: CreateTaskRequest): Promise<Task> {
  const { data } = await client.post<Task>('/tasks', payload)
  return data
}

export async function updateTask(
  id: number,
  payload: Partial<Pick<Task, 'enabled' | 'name' | 'target_times' | 'poll_interval' | 'start_at'>>
): Promise<Task> {
  const { data } = await client.put<Task>(`/tasks/${id}`, payload)
  return data
}

export async function deleteTask(id: number): Promise<MessageResponse> {
  const { data } = await client.delete<MessageResponse>(`/tasks/${id}`)
  return data
}

/* ------------------------------- system ------------------------------- */
export async function getSystemInfo(): Promise<SystemInfo> {
  const { data } = await client.get<SystemInfo>('/system/info')
  return data
}

export async function shutdownService(): Promise<void> {
  await client.post('/system/shutdown', {}, { headers: { 'X-Desktop-Action': 'shutdown' } })
}

export interface RuntimeSettings {
  default_poll_interval: number
  lead_minutes: number
  max_runtime_hours: number
}

export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  const { data } = await client.get<RuntimeSettings>('/system/settings')
  return data
}

export async function saveRuntimeSettings(
  payload: RuntimeSettings
): Promise<RuntimeSettings> {
  const { data } = await client.put<RuntimeSettings>('/system/settings', payload)
  return data
}

/* ---------------------------- in-app login ---------------------------- */
export interface BrowserLoginStatus {
  state: 'idle' | 'starting' | 'waiting' | 'success' | 'failed' | 'cancelled' | string
  message: string
  cookie_count: number
  login_url: string
}

export async function startBrowserLogin(): Promise<BrowserLoginStatus> {
  const { data } = await client.post<BrowserLoginStatus>('/auth/browser-login')
  return data
}

export async function getBrowserLoginStatus(): Promise<BrowserLoginStatus> {
  const { data } = await client.get<BrowserLoginStatus>('/auth/browser-login')
  return data
}

export async function cancelBrowserLogin(): Promise<BrowserLoginStatus> {
  const { data } = await client.delete<BrowserLoginStatus>('/auth/browser-login')
  return data
}
