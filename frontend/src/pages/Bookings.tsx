import { useCallback, useEffect, useState } from 'react'
import {
  clearHistory,
  deleteRecord,
  getHistory,
  type BookingRecord,
} from '../api'
import { errorMessage } from '../api/client'
import { IconAlert, IconList, IconRefresh, IconTrash } from '../components/Icons'
import { Btn, Empty, Loading, Sheet, Spinner } from '../components/ui'
import { useToast } from '../components/Toast'

export default function Bookings() {
  const toast = useToast()
  const [records, setRecords] = useState<BookingRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)
  const [clearing, setClearing] = useState(false)

  const load = useCallback(async () => {
    try {
      setRecords(await getHistory(200))
    } catch (err) {
      toast.error(errorMessage(err, '获取记录失败'))
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const remove = async (id: number) => {
    setBusyId(id)
    try {
      await deleteRecord(id)
      setRecords((prev) => prev.filter((item) => item.id !== id))
      toast.success('已删除该条记录')
    } catch (err) {
      toast.error(errorMessage(err, '删除失败'))
    } finally {
      setBusyId(null)
    }
  }

  const clearAll = async () => {
    setClearing(true)
    try {
      await clearHistory()
      setRecords([])
      setConfirmClear(false)
      toast.success('记录已清空')
    } catch (err) {
      toast.error(errorMessage(err, '清空失败'))
    } finally {
      setClearing(false)
    }
  }

  if (loading) return <Loading label="正在读取预约记录…" />

  const success = records.filter((item) => item.status === 'success').length

  return (
    <div>
      <div className="page-head">
        <h1 className="page-title">预约记录</h1>
        <p className="page-sub">
          {records.length === 0
            ? '还没有任何下单记录'
            : `共 ${records.length} 条 · 成功 ${success} 条`}
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        <Btn variant="ghost" size="sm" onClick={load}>
          <IconRefresh size={14} />
          刷新
        </Btn>
        {records.length > 0 && (
          <Btn variant="danger" size="sm" onClick={() => setConfirmClear(true)}>
            <IconTrash size={14} />
            清空全部
          </Btn>
        )}
      </div>

      {records.length === 0 ? (
        <Empty
          icon={<IconList size={22} />}
          title="暂无预约记录"
          desc="手动预约和自动任务的每次下单都会记录在这里"
        />
      ) : (
        records.map((item) => (
          <div className="card" key={item.id} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px' }}>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 12,
                  display: 'grid',
                  placeItems: 'center',
                  flex: 'none',
                  background:
                    item.status === 'success' ? 'var(--brand-soft)' : 'var(--danger-soft)',
                  color: item.status === 'success' ? 'var(--brand)' : 'var(--danger)',
                }}
              >
                {item.status === 'success' ? <IconList size={18} /> : <IconAlert size={18} />}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 650, fontSize: 14 }}>{item.field_name}</div>
                <div style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                  {item.date} · {item.begin_time}-{item.end_time}
                  {item.task_id ? ` · 任务 #${item.task_id}` : ''}
                </div>
              </div>

              <span className={`pill ${item.status === 'success' ? 'pill--ok' : 'pill--bad'}`}>
                {item.status === 'success' ? '成功' : '失败'}
              </span>

              <button
                className="sheet__close"
                onClick={() => remove(item.id)}
                disabled={busyId === item.id}
                aria-label="删除记录"
              >
                {busyId === item.id ? <Spinner size={13} /> : <IconTrash size={15} />}
              </button>
            </div>

            {(item.message || item.created_at) && (
              <div
                style={{
                  borderTop: '1px dashed var(--line)',
                  padding: '9px 16px',
                  fontSize: 12,
                  color: 'var(--ink-3)',
                  display: 'flex',
                  gap: 10,
                  justifyContent: 'space-between',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {item.message}
                </span>
                <span style={{ flex: 'none', fontVariantNumeric: 'tabular-nums' }}>
                  {item.created_at}
                </span>
              </div>
            )}
          </div>
        ))
      )}

      <Sheet
        open={confirmClear}
        title="清空全部记录"
        onClose={() => !clearing && setConfirmClear(false)}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setConfirmClear(false)} disabled={clearing}>
              取消
            </Btn>
            <Btn variant="danger" onClick={clearAll} disabled={clearing}>
              {clearing ? <Spinner size={15} /> : <IconTrash size={15} />}
              确认清空
            </Btn>
          </>
        }
      >
        <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--ink-2)' }}>
          将删除全部 {records.length} 条记录，包括自动任务的成功记录。
          删除后任务的防重复判断会失效，建议只删除明显无用的条目。
        </p>
      </Sheet>
    </div>
  )
}
