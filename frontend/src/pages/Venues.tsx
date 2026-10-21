import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getDates,
  getFields,
  getSlots,
  placeOrder,
  type Field,
  type Slot,
} from '../api'
import { errorMessage } from '../api/client'
import {
  IconAlert,
  IconCheck,
  IconChevron,
  IconCourt,
  IconRefresh,
} from '../components/Icons'
import { Btn, Empty, Loading, Sheet, Spinner } from '../components/ui'
import { useToast } from '../components/Toast'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function dateMeta(mmdd: string) {
  const [month, day] = mmdd.split('-').map(Number)
  const now = new Date()
  let date = new Date(now.getFullYear(), month - 1, day)
  if (date < new Date(now.getFullYear(), now.getMonth(), now.getDate())) {
    date = new Date(now.getFullYear() + 1, month - 1, day)
  }
  const today = new Date()
  const isToday =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate()
  return {
    day: String(day).padStart(2, '0'),
    month: `${month} 月`,
    weekday: isToday ? '今天' : WEEKDAYS[date.getDay()],
  }
}

function slotState(slot: Slot) {
  if (slot.field_state !== 0) return { key: 'full', label: '已满', pill: 'pill--bad' }
  if (slot.time_status !== 1)
    return { key: 'closed', label: '未开放', pill: 'pill--warn' }
  return { key: 'free', label: '可订', pill: 'pill--ok' }
}

export default function Venues() {
  const toast = useToast()
  const [dates, setDates] = useState<string[]>([])
  const [activeDate, setActiveDate] = useState('')
  const [slots, setSlots] = useState<Slot[]>([])
  const [loadingDates, setLoadingDates] = useState(true)
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [openSlot, setOpenSlot] = useState('')
  const [fields, setFields] = useState<Record<string, Field[]>>({})
  const [loadingFields, setLoadingFields] = useState('')
  const [confirm, setConfirm] = useState<Field | null>(null)
  const [ordering, setOrdering] = useState(false)
  const [banner, setBanner] = useState('')

  const loadDates = useCallback(async () => {
    setLoadingDates(true)
    try {
      const result = await getDates()
      setDates(result.dates)
      setBanner(result.error || '')
      if (result.dates.length > 0) {
        setActiveDate((prev) => (prev && result.dates.includes(prev) ? prev : result.dates[0]))
      }
    } catch (err) {
      setBanner(errorMessage(err, '获取日期失败'))
      setDates([])
    } finally {
      setLoadingDates(false)
    }
  }, [])

  const loadSlots = useCallback(
    async (date: string, keepBanner = false) => {
      setLoadingSlots(true)
      setOpenSlot('')
      try {
        const result = await getSlots(date, true)
        setSlots(result.slots)
        if (!keepBanner) setBanner(result.error || '')
        if (result.error) setBanner(result.error)
      } catch (err) {
        setSlots([])
        setBanner(errorMessage(err, '获取时段失败'))
      } finally {
        setLoadingSlots(false)
      }
    },
    []
  )

  useEffect(() => {
    loadDates()
  }, [loadDates])

  useEffect(() => {
    if (activeDate) loadSlots(activeDate)
  }, [activeDate, loadSlots])

  const freeCount = useMemo(
    () => slots.filter((slot) => slot.field_state === 0 && slot.time_status === 1).length,
    [slots]
  )

  const toggleSlot = async (slot: Slot) => {
    const key = `${slot.begin_time}-${slot.end_time}`
    if (slotState(slot).key !== 'free') return
    if (openSlot === key) {
      setOpenSlot('')
      return
    }
    setOpenSlot(key)
    if (fields[key]) return
    setLoadingFields(key)
    try {
      const result = await getFields(activeDate, slot.begin_time, slot.end_time)
      if (result.error) toast.error(result.error)
      setFields((prev) => ({ ...prev, [key]: result.fields }))
    } catch (err) {
      toast.error(errorMessage(err, '获取场地失败'))
      setFields((prev) => ({ ...prev, [key]: [] }))
    } finally {
      setLoadingFields('')
    }
  }

  const submitOrder = async () => {
    if (!confirm) return
    setOrdering(true)
    try {
      const result = await placeOrder({
        date: activeDate,
        begin_time: confirm.begin_time,
        end_time: confirm.end_time,
        field_no: confirm.field_no,
      })
      if (result.success) {
        toast.success(result.message || '预约成功')
        setConfirm(null)
        setFields({})
        await loadSlots(activeDate, true)
      } else {
        toast.error(result.message || '预约失败')
      }
    } catch (err) {
      toast.error(errorMessage(err, '预约失败'))
    } finally {
      setOrdering(false)
    }
  }

  if (loadingDates) return <Loading label="正在获取可预约日期…" />

  return (
    <div>
      <div className="page-head">
        <h1 className="page-title">浏览场地</h1>
        <p className="page-sub">
          {activeDate
            ? `${activeDate} 共 ${slots.length} 个时段，${freeCount} 个可订`
            : '选择日期查看时段'}
        </p>
      </div>

      <div className="datestrip">
        {dates.map((date) => {
          const meta = dateMeta(date)
          return (
            <button
              key={date}
              className={`date-chip${date === activeDate ? ' is-active' : ''}`}
              onClick={() => setActiveDate(date)}
            >
              <span>{meta.weekday}</span>
              <b>{meta.day}</b>
            </button>
          )
        })}
        <button
          className="date-chip"
          onClick={() => {
            loadDates()
            if (activeDate) loadSlots(activeDate)
          }}
          style={{ display: 'grid', placeItems: 'center' }}
          aria-label="刷新"
        >
          <IconRefresh size={17} />
        </button>
      </div>

      {banner && (
        <div className="notice" style={{ marginBottom: 12 }}>
          <IconAlert size={16} />
          <span>{banner}</span>
        </div>
      )}

      {loadingSlots ? (
        <div className="center-box">
          <Spinner size={26} />
          <span style={{ fontSize: 13, color: 'var(--ink-3)' }}>正在获取时段…</span>
        </div>
      ) : dates.length === 0 ? (
        <Empty
          icon={<IconCourt size={22} />}
          title="没有可预约的日期"
          desc="通常是登录过期或场馆系统未开放"
        />
      ) : slots.length === 0 ? (
        <Empty
          icon={<IconCourt size={22} />}
          title="这一天没有时段数据"
          desc="换个日期看看，或稍后刷新"
        />
      ) : (
        <div>
          {slots.map((slot) => {
            const key = `${slot.begin_time}-${slot.end_time}`
            const state = slotState(slot)
            const isOpen = openSlot === key
            const list = fields[key]

            return (
              <div key={key} className={`slot${isOpen ? ' is-open' : ''}`}>
                <div className="slot__head" onClick={() => toggleSlot(slot)}>
                  <div>
                    <div className="slot__time">
                      {slot.begin_time} – {slot.end_time}
                    </div>
                    <div className="slot__dur">1 小时 · 2 片场地</div>
                  </div>
                  <div className="slot__spacer" />
                  <span className={`pill ${state.pill}`}>{state.label}</span>
                  {state.key === 'free' && (
                    <span className="slot__chev">
                      <IconChevron size={16} />
                    </span>
                  )}
                </div>

                {isOpen && (
                  <div className="slot__body">
                    {loadingFields === key ? (
                      <div className="center-box" style={{ padding: 20 }}>
                        <Spinner size={20} />
                      </div>
                    ) : !list || list.length === 0 ? (
                      <div
                        style={{
                          textAlign: 'center',
                          color: 'var(--ink-3)',
                          fontSize: 13,
                          padding: '10px 0',
                        }}
                      >
                        这个时段暂时没有可下单的场地
                      </div>
                    ) : (
                      list.map((field) => (
                        <div key={field.field_no} className="field">
                          <div className="field__grow">
                            <div className="field__name">{field.field_name}</div>
                            <div className="field__meta">
                              {field.price && Number(field.price) > 0
                                ? `¥${field.price}`
                                : '免费'}
                              <span style={{ opacity: 0.6 }}> · {field.field_no}</span>
                            </div>
                          </div>
                          <Btn
                            variant="primary"
                            size="sm"
                            onClick={() => setConfirm(field)}
                          >
                            预约
                          </Btn>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <Sheet
        open={Boolean(confirm)}
        title="确认预约"
        onClose={() => !ordering && setConfirm(null)}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setConfirm(null)} disabled={ordering}>
              取消
            </Btn>
            <Btn variant="primary" onClick={submitOrder} disabled={ordering}>
              {ordering ? <Spinner size={15} /> : <IconCheck size={15} />}
              {ordering ? '提交中' : '确认预约'}
            </Btn>
          </>
        }
      >
        {confirm && (
          <div style={{ display: 'grid', gap: 12, padding: '4px 0 10px' }}>
            {[
              ['日期', activeDate],
              ['时段', `${confirm.begin_time} – ${confirm.end_time}`],
              ['场地', confirm.field_name],
              [
                '费用',
                confirm.price && Number(confirm.price) > 0 ? `¥${confirm.price}` : '免费',
              ],
            ].map(([label, value]) => (
              <div
                key={label}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 16,
                  fontSize: 14,
                }}
              >
                <span style={{ color: 'var(--ink-3)' }}>{label}</span>
                <span style={{ fontWeight: 600 }}>{value}</span>
              </div>
            ))}
            <div className="notice" style={{ marginTop: 4 }}>
              <IconAlert size={15} />
              <span>提交后名额立即占用，请确认时间无误。</span>
            </div>
          </div>
        )}
      </Sheet>
    </div>
  )
}
