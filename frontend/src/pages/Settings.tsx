import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  cancelBrowserLogin,
  checkStatus,
  getBrowserLoginStatus,
  getRuntimeSettings,
  getSystemInfo,
  logout,
  saveRuntimeSettings,
  startBrowserLogin,
  uploadSession,
  type AuthStatus,
  type BrowserLoginStatus,
  type RuntimeSettings,
  type SystemInfo,
} from '../api'
import { errorMessage } from '../api/client'
import {
  IconAlert,
  IconCheck,
  IconInfo,
  IconLogout,
  IconRefresh,
  IconShield,
  IconUpload,
  IconUser,
} from '../components/Icons'
import { Btn, Row, Spinner } from '../components/ui'
import { useToast } from '../components/Toast'

export default function Settings() {
  const toast = useToast()
  const [auth, setAuth] = useState<AuthStatus | null>(null)
  const [info, setInfo] = useState<SystemInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [token, setToken] = useState(localStorage.getItem('bb_access_token') || '')
  const inputRef = useRef<HTMLInputElement>(null)

  const [loginState, setLoginState] = useState<BrowserLoginStatus>({
    state: 'idle',
    message: '',
    cookie_count: 0,
    login_url: '',
  })
  const [starting, setStarting] = useState(false)

  const [params, setParams] = useState<RuntimeSettings>({
    default_poll_interval: 3,
    lead_minutes: 150,
    max_runtime_hours: 4,
  })
  const [savingParams, setSavingParams] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setAuth(await checkStatus())
      window.dispatchEvent(new Event('auth-changed'))
    } catch (err) {
      toast.error(errorMessage(err, '无法获取登录状态'))
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    refresh()
    getSystemInfo()
      .then(setInfo)
      .catch(() => undefined)
    getRuntimeSettings()
      .then(setParams)
      .catch(() => undefined)
    getBrowserLoginStatus()
      .then(setLoginState)
      .catch(() => undefined)
  }, [refresh])

  // Poll while the login window is open.
  useEffect(() => {
    if (!['starting', 'waiting'].includes(loginState.state)) return
    let alive = true
    const timer = window.setInterval(async () => {
      try {
        const next = await getBrowserLoginStatus()
        if (!alive) return
        setLoginState(next)
        if (next.state === 'success') {
          toast.success(next.message || '登录成功')
          await refresh()
        } else if (next.state === 'failed') {
          toast.error(next.message || '登录失败')
        }
      } catch {
        /* ignore polling errors */
      }
    }, 1500)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [loginState.state, refresh, toast])

  const handleLogin = async () => {
    setStarting(true)
    try {
      const result = await startBrowserLogin()
      setLoginState(result)
      if (result.state === 'failed') toast.error(result.message)
    } catch (err) {
      toast.error(errorMessage(err, '无法启动登录窗口'))
    } finally {
      setStarting(false)
    }
  }

  const handleCancelLogin = async () => {
    try {
      const result = await cancelBrowserLogin()
      setLoginState(result)
      toast.info('已取消登录')
    } catch (err) {
      toast.error(errorMessage(err, '取消失败'))
    }
  }

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.json')) {
      toast.error('请选择 venue_session.json 文件')
      return
    }
    setUploading(true)
    try {
      const result = await uploadSession(file)
      result.success ? toast.success(result.message) : toast.error(result.message)
      await refresh()
    } catch (err) {
      toast.error(errorMessage(err, '上传失败'))
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      const result = await logout()
      result.success ? toast.success(result.message) : toast.error(result.message)
      await refresh()
    } catch (err) {
      toast.error(errorMessage(err, '退出失败'))
    } finally {
      setLoggingOut(false)
    }
  }

  const saveToken = () => {
    const value = token.trim()
    if (value) localStorage.setItem('bb_access_token', value)
    else localStorage.removeItem('bb_access_token')
    toast.success(value ? '访问令牌已保存' : '已清除访问令牌')
    refresh()
  }

  const saveParams = async () => {
    setSavingParams(true)
    try {
      const saved = await saveRuntimeSettings({
        default_poll_interval: Number(params.default_poll_interval) || 3,
        lead_minutes: Math.round(Number(params.lead_minutes) || 0),
        max_runtime_hours: Number(params.max_runtime_hours) || 4,
      })
      setParams(saved)
      toast.success('抢场参数已保存')
      getSystemInfo().then(setInfo).catch(() => undefined)
    } catch (err) {
      toast.error(errorMessage(err, '保存失败'))
    } finally {
      setSavingParams(false)
    }
  }

  const waiting = ['starting', 'waiting'].includes(loginState.state)

  return (
    <div>
      <div className="page-head">
        <h1 className="page-title">设置</h1>
        <p className="page-sub">登录、抢场参数与运行信息</p>
      </div>

      <div className="card card--pad rise" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            className="stat__icon"
            style={{
              width: 42,
              height: 42,
              background: auth?.logged_in ? 'var(--brand-soft)' : 'var(--danger-soft)',
              color: auth?.logged_in ? 'var(--brand)' : 'var(--danger)',
            }}
          >
            <IconUser size={20} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>
              {auth?.logged_in ? '登录有效' : '未登录'}
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>{auth?.message}</div>
          </div>
          <span className={`pill ${auth?.logged_in ? 'pill--ok' : 'pill--bad'}`}>
            {auth?.logged_in ? '在线' : '离线'}
          </span>
        </div>

        <div className="divider" />

        <div className="task__rows" style={{ margin: 0 }}>
          <Row label="cookie 数">{auth?.cookie_count ?? 0} 条</Row>
          <Row label="导出时间">{auth?.captured_at || '—'}</Row>
          <Row label="文件状态">{auth?.has_cookie_file ? '已存在' : '不存在'}</Row>
        </div>

        <div style={{ display: 'grid', gap: 9, marginTop: 16 }}>
          <Btn variant="primary" className="btn--block" onClick={handleLogin} disabled={waiting || starting}>
            {starting || loginState.state === 'starting' ? (
              <Spinner size={15} />
            ) : (
              <IconUser size={15} />
            )}
            {waiting ? '等待窗口内登录完成…' : '一键登录（打开登录窗口）'}
          </Btn>

          {waiting ? (
            <Btn variant="ghost" className="btn--block" onClick={handleCancelLogin}>
              取消登录
            </Btn>
          ) : (
            <Btn
              variant="ghost"
              className="btn--block"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? <Spinner size={15} /> : <IconUpload size={15} />}
              {uploading ? '上传中…' : '导入 session 文件'}
            </Btn>
          )}

          {auth?.logged_in && (
            <Btn variant="danger" onClick={handleLogout} disabled={loggingOut}>
              {loggingOut ? <Spinner size={15} /> : <IconLogout size={15} />}
              退出登录
            </Btn>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".json,application/json"
          onChange={handleFile}
          style={{ display: 'none' }}
        />

        {waiting && (
          <div className="notice notice--info" style={{ marginTop: 12 }}>
            <IconInfo size={15} />
            <span>
              {loginState.message || '请在登录窗口中完成学校认证与场馆用户类型选择，验证成功后窗口会自动关闭。'}
            </span>
          </div>
        )}

        {loginState.state === 'success' && (
          <div
            className="notice"
            style={{ marginTop: 12, background: 'var(--brand-soft)', color: 'var(--brand)' }}
          >
            <IconCheck size={15} />
            <span>{loginState.message}</span>
          </div>
        )}

        {loginState.state === 'failed' && (
          <div className="notice" style={{ marginTop: 12 }}>
            <IconAlert size={15} />
            <span>{loginState.message}</span>
          </div>
        )}

        {loginState.state === 'idle' && !auth?.logged_in && (
          <div className="notice" style={{ marginTop: 12 }}>
            <IconAlert size={15} />
            <span>
              点「一键登录」会用 Edge 打开学校统一认证页，登录完成后 cookie
              自动写入，立即生效。若窗口没弹出来，可改用导出文件后导入。
            </span>
          </div>
        )}
      </div>

      <div className="card card--pad" style={{ marginBottom: 14 }}>
        <div className="section__head" style={{ marginBottom: 12 }}>
          <h2 className="section__title" style={{ fontSize: 15 }}>
            抢场参数
          </h2>
          <span className="section__hint">保存后立即生效</span>
        </div>

        <div className="form-row">
          <label className="field-label">默认轮询间隔（秒）</label>
          <input
            className="input"
            type="number"
            min={0.5}
            max={60}
            step={0.5}
            value={params.default_poll_interval}
            onChange={(event) =>
              setParams((prev) => ({
                ...prev,
                default_poll_interval: Number(event.target.value),
              }))
            }
          />
          <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>
            新建任务时的默认值，范围 0.5–60 秒。太小容易被场馆限流，建议 2–5 秒。
          </div>
        </div>

        <div className="form-row">
          <label className="field-label">提前启动（分钟）</label>
          <input
            className="input"
            type="number"
            min={0}
            max={720}
            step={10}
            value={params.lead_minutes}
            onChange={(event) =>
              setParams((prev) => ({ ...prev, lead_minutes: Number(event.target.value) }))
            }
          />
          <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>
            任务没填启动时间时，在最早目标时段开放前多少分钟开始盯场。
          </div>
        </div>

        <div className="form-row">
          <label className="field-label">最长运行（小时）</label>
          <input
            className="input"
            type="number"
            min={0.5}
            max={12}
            step={0.5}
            value={params.max_runtime_hours}
            onChange={(event) =>
              setParams((prev) => ({
                ...prev,
                max_runtime_hours: Number(event.target.value),
              }))
            }
          />
          <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>
            超过该时长仍未抢到会放弃并标记「超时未抢到」。
          </div>
        </div>

        <Btn variant="primary" onClick={saveParams} disabled={savingParams} style={{ width: '100%' }}>
          {savingParams ? <Spinner size={15} /> : <IconCheck size={15} />}
          {savingParams ? '保存中…' : '保存参数'}
        </Btn>
      </div>

      <div className="card card--pad" style={{ marginBottom: 14 }}>
        <div className="section__head" style={{ marginBottom: 10 }}>
          <h2 className="section__title" style={{ fontSize: 15 }}>
            访问令牌
          </h2>
          <span className="section__hint">{info?.auth_required ? '已启用' : '未启用'}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input"
            type="password"
            placeholder="服务器 config.json 中的 ACCESS_TOKEN"
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
          <Btn variant="soft" onClick={saveToken}>
            保存
          </Btn>
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 8, display: 'flex', gap: 6 }}>
          <IconShield size={14} />
          <span>只有把服务暴露到公网时才需要；本地自用留空即可。</span>
        </div>
      </div>

      <div className="card card--pad" style={{ marginBottom: 14 }}>
        <div className="section__head" style={{ marginBottom: 10 }}>
          <h2 className="section__title" style={{ fontSize: 15 }}>
            运行信息
          </h2>
          <Btn variant="ghost" size="sm" onClick={refresh}>
            <IconRefresh size={13} />
            刷新
          </Btn>
        </div>
        <div className="task__rows" style={{ margin: 0 }}>
          <Row label="程序版本">v{info?.version || '2.0.0'}</Row>
          <Row label="运行方式">{info?.frozen ? '独立 exe' : 'Python 源码'}</Row>
          <Row label="场馆编号">
            {info?.venue_no || '02'} / {info?.field_type || '021'}
          </Row>
          <Row label="默认轮询">{info?.poll_default ?? 3}s</Row>
          <Row label="提前启动">{info?.lead_minutes ?? 150} 分钟</Row>
          <Row label="最长运行">{info?.max_runtime_hours ?? 4} 小时</Row>
          <Row label="数据目录">
            <span className="mono" style={{ wordBreak: 'break-all' }}>
              {info?.data_dir || '—'}
            </span>
          </Row>
        </div>
      </div>

      <div className="card card--pad">
        <div className="section__head" style={{ marginBottom: 10 }}>
          <h2 className="section__title" style={{ fontSize: 15 }}>
            使用须知
          </h2>
        </div>
        <div style={{ display: 'grid', gap: 10, fontSize: 13, color: 'var(--ink-2)' }}>
          {[
            '本工具只做代下单，不修改、不绕过场馆系统的任何校验。',
            '登录有效期由学校场馆系统决定，失效后在此重新登录。',
            '请只预约自己真正要用的场地，恶意占场可能导致账号被限制。',
            '关闭程序时正在运行的任务会停止，重启后会自动恢复。',
          ].map((text) => (
            <div key={text} style={{ display: 'flex', gap: 8 }}>
              <span style={{ color: 'var(--brand)', marginTop: 1 }}>
                <IconCheck size={15} />
              </span>
              <span>{text}</span>
            </div>
          ))}
        </div>
        <div className="notice" style={{ marginTop: 14 }}>
          <IconAlert size={15} />
          <span>账号密码只在登录窗口里输入，程序不保存、不上传。</span>
        </div>
      </div>
    </div>
  )
}
