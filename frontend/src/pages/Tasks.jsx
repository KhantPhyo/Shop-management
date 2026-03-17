import { useState, useEffect, useCallback } from 'react';
import { Plus, Eye, Pencil, Trash2, DollarSign, X, RefreshCw, Download, ChevronDown, ChevronRight, Calendar, List, LayoutList, Repeat, Clock, CalendarDays, CalendarRange, Megaphone, Send } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import PriorityBadge from '../components/PriorityBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import isoWeek from 'dayjs/plugin/isoWeek';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import api from '../api';

dayjs.extend(relativeTime);
dayjs.extend(isoWeek);
dayjs.extend(weekOfYear);

/* ───── Report Type Labels ───── */
const REPORT_TYPE_LABELS = {
  photo: { label: 'Photo Report', icon: '📸', color: 'bg-purple-100 text-purple-700' },
  excel: { label: 'Excel/File Report', icon: '📊', color: 'bg-green-100 text-green-700' },
  file: { label: 'File Report', icon: '📄', color: 'bg-blue-100 text-blue-700' },
  text: { label: 'Text Report', icon: '💬', color: 'bg-amber-100 text-amber-700' },
};

function ReportTypeBadge({ type }) {
  const config = REPORT_TYPE_LABELS[type] || { label: type, icon: '📋', color: 'bg-gray-100 text-gray-700' };
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.color}`}>{config.icon} {config.label}</span>;
}

/* ───── Task Detail Modal ───── */
function TaskDetailModal({ taskId, shops, onClose, onReload }) {
  const [task, setTask] = useState(null);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [reassignShop, setReassignShop] = useState('');
  const [reassigning, setReassigning] = useState(false);

  useEffect(() => {
    if (taskId) api.get(`/tasks/${taskId}`).then(r => setTask(r.data)).catch(() => {});
  }, [taskId]);

  // Auto-refresh detail every 10 seconds
  useEffect(() => {
    if (!taskId) return;
    const interval = setInterval(() => {
      api.get(`/tasks/${taskId}`).then(r => setTask(r.data)).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [taskId]);

  if (!taskId) return null;
  if (!task) return <ModalShell onClose={onClose}><p className="text-center py-10">Loading...</p></ModalShell>;

  const handleReassign = async () => {
    if (!reassignShop) return;
    setReassigning(true);
    try {
      await api.post(`/tasks/${task.id}/reassign`, { new_shop_id: Number(reassignShop) });
      setReassignOpen(false);
      // Reload task detail
      const { data } = await api.get(`/tasks/${task.id}`);
      setTask(data);
      if (onReload) onReload();
    } catch (err) {
      alert(err.response?.data?.error || 'Reassign failed');
    } finally {
      setReassigning(false);
    }
  };

  const requiredTypes = (task.required_report_type || 'photo').split(',').map(t => t.trim());

  return (
    <ModalShell onClose={onClose} wide>
      <h3 className="text-lg font-semibold mb-4">Task Details</h3>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <Info label="Task ID" value={<span className="font-mono">{task.task_id}</span>} />
        <Info label="Shop" value={task.shop_name} />
        <Info label="Title" value={task.title} />
        <Info label="Priority" value={<PriorityBadge priority={task.priority} />} />
        <Info label="Status" value={<StatusBadge status={task.status} />} />
        <Info label="Deadline" value={task.deadline ? dayjs(task.deadline).format('YYYY-MM-DD HH:mm') : 'N/A'} />
        <Info label="Fine" value={`${task.fine_amount_mmk || 0} MMK`} />
        <Info label="Required Report" value={<div className="flex flex-wrap gap-1">{requiredTypes.map(t => <ReportTypeBadge key={t} type={t} />)}</div>} />
        <div className="col-span-2"><Info label="Description" value={task.description || '-'} /></div>
      </div>

      {/* Reassign Button */}
      <div className="mt-4 flex gap-2">
        <button
          onClick={() => { setReassignShop(task.shop_id); setReassignOpen(true); }}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-orange-300 text-orange-700 rounded-lg hover:bg-orange-50"
        >
          <RefreshCw size={14} /> Reassign
        </button>
      </div>

      {/* Reassign Panel */}
      {reassignOpen && (
        <div className="mt-3 p-4 bg-orange-50 rounded-lg border border-orange-200">
          <p className="text-sm font-medium text-orange-800 mb-2">Reassign to:</p>
          <div className="flex gap-2">
            <select
              value={reassignShop}
              onChange={e => setReassignShop(e.target.value)}
              className="flex-1 px-3 py-2 border rounded-lg text-sm"
            >
              <option value="">Select shop...</option>
              {shops?.map(s => <option key={s.id} value={s.id}>{s.shop_name} {s.id === task.shop_id ? '(current)' : ''}</option>)}
            </select>
            <button
              onClick={handleReassign}
              disabled={reassigning || !reassignShop}
              className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 text-sm"
            >
              {reassigning ? '...' : 'Confirm'}
            </button>
            <button onClick={() => setReassignOpen(false)} className="px-3 py-2 bg-gray-200 rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Status Timeline */}
      <div className="mt-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-3">Status Timeline</h4>
        <div className="flex items-center gap-2 text-xs">
          {['created', 'accepted', 'in_progress', 'done'].map((step, i) => {
            const times = { created: task.created_at, accepted: task.accepted_at, in_progress: task.started_at, done: task.completed_at };
            const active = times[step];
            return (
              <div key={step} className="flex items-center gap-2">
                {i > 0 && <div className={`h-0.5 w-8 ${active ? 'bg-blue-500' : 'bg-gray-200'}`} />}
                <div className={`px-3 py-1.5 rounded-full ${active ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'}`}>
                  <div className="capitalize">{step.replace('_', ' ')}</div>
                  {active && <div className="text-[10px] mt-0.5">{dayjs(active).format('MM/DD HH:mm')}</div>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Completion Reports */}
      <div className="mt-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-3">
          Completion Reports {task.reports?.length > 0 ? `(${task.reports.length})` : ''}
        </h4>
        {task.reports?.length > 0 ? (
          <div className="space-y-3">
            {/* Photo reports - grid */}
            {task.reports.filter(r => r.report_type === 'photo').length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-2">Photos</p>
                <div className="grid grid-cols-3 gap-2">
                  {task.reports.filter(r => r.report_type === 'photo').map(r => (
                    <a
                      key={r.id}
                      href={`/api/reports/download/${r.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block aspect-square bg-gray-100 rounded-lg overflow-hidden border hover:border-blue-400 relative group"
                    >
                      <img src={`/api/reports/download/${r.id}`} alt={r.file_name} className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                        <Download size={20} className="text-white opacity-0 group-hover:opacity-100" />
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
            {/* File/Excel reports */}
            {task.reports.filter(r => ['file', 'excel'].includes(r.report_type)).length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-2">Files</p>
                <div className="space-y-1">
                  {task.reports.filter(r => ['file', 'excel'].includes(r.report_type)).map(r => (
                    <a
                      key={r.id}
                      href={`/api/reports/download/${r.id}`}
                      className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                      <span className="text-lg">{r.report_type === 'excel' ? '📊' : '📄'}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{r.file_name}</p>
                        <p className="text-xs text-gray-400">{dayjs(r.submitted_at).format('MM/DD HH:mm')}</p>
                      </div>
                      <Download size={16} className="text-gray-400" />
                    </a>
                  ))}
                </div>
              </div>
            )}
            {/* Text reports */}
            {task.reports.filter(r => r.report_type === 'text').length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-2">Text Reports</p>
                <div className="space-y-2">
                  {task.reports.filter(r => r.report_type === 'text').map(r => (
                    <div key={r.id} className="p-3 bg-amber-50 rounded-lg border border-amber-100">
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">{r.text_content}</p>
                      <p className="text-xs text-gray-400 mt-2">{dayjs(r.submitted_at).format('MM/DD HH:mm')}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-400 italic">No reports submitted yet</p>
        )}
      </div>

      {/* Logs */}
      {task.logs?.length > 0 && (
        <div className="mt-6">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Activity Log</h4>
          <div className="space-y-2">
            {task.logs.map(l => (
              <div key={l.id} className="flex items-start gap-3 text-sm">
                <div className="w-2 h-2 rounded-full bg-blue-400 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium capitalize">{l.action}</span>
                  <span className="text-gray-400 ml-2">by {l.actor}</span>
                  {l.details && <span className="text-gray-500 ml-2">{l.details}</span>}
                  <span className="text-xs text-gray-400 ml-2">{dayjs(l.created_at).format('MM/DD HH:mm')}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </ModalShell>
  );
}

/* ───── Create/Edit Task Modal ───── */
function TaskFormModal({ isOpen, task, shops, onClose, onSave }) {
  const empty = { shop_id: '', title: '', description: '', priority: 'medium', deadline: getDefaultDeadline(), fine_amount_mmk: 0, schedule_type: 'one_time', schedule_day: '', schedule_time: '', required_report_type: 'photo' };
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (task) {
      setForm({
        shop_id: task.shop_id, title: task.title, description: task.description || '',
        priority: task.priority, deadline: task.deadline ? task.deadline.slice(0, 16) : '',
        fine_amount_mmk: task.fine_amount_mmk || 0, schedule_type: task.schedule_type || 'one_time',
        schedule_day: task.schedule_day || '', schedule_time: task.schedule_time || '',
        required_report_type: task.required_report_type || 'photo'
      });
    } else {
      setForm(empty);
    }
  }, [task, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = { ...form, shop_id: Number(form.shop_id), fine_amount_mmk: Number(form.fine_amount_mmk) };
      if (form.schedule_day) payload.schedule_day = Number(form.schedule_day);
      if (task) await api.put(`/tasks/${task.id}`, payload);
      else await api.post('/tasks', payload);
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const set = (k, v) => setForm({ ...form, [k]: v });

  return (
    <ModalShell onClose={onClose} wide>
      <h3 className="text-lg font-semibold mb-4">{task ? 'Edit Task' : 'Create Task'}</h3>
      {error && <div className="bg-red-50 text-red-600 px-4 py-2 rounded-lg text-sm mb-4">{error}</div>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Shop</label>
          <select value={form.shop_id} onChange={e => set('shop_id', e.target.value)} required className="w-full px-3 py-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Select shop...</option>
            {shops.map(s => <option key={s.id} value={s.id}>{s.shop_name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
          <input type="text" value={form.title} onChange={e => set('title', e.target.value)} required maxLength={200} className="w-full px-3 py-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea value={form.description} onChange={e => set('description', e.target.value)} rows={3} className="w-full px-3 py-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
            <div className="flex gap-2">
              {['low', 'medium', 'high', 'urgent'].map(p => (
                <label key={p} className={`flex-1 text-center py-2 rounded-lg cursor-pointer text-sm border capitalize ${form.priority === p ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-gray-50'}`}>
                  <input type="radio" name="priority" value={p} checked={form.priority === p} onChange={() => set('priority', p)} className="sr-only" />
                  {p}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Deadline</label>
            <input type="datetime-local" value={form.deadline} onChange={e => set('deadline', e.target.value)} required className="w-full px-3 py-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Fine (MMK)</label>
            <div className="flex gap-2">
              {[0, 500, 1000].map(f => (
                <label key={f} className={`flex-1 text-center py-2 rounded-lg cursor-pointer text-sm border ${form.fine_amount_mmk == f ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-gray-50'}`}>
                  <input type="radio" name="fine" value={f} checked={form.fine_amount_mmk == f} onChange={() => set('fine_amount_mmk', f)} className="sr-only" />
                  {f === 0 ? 'None' : `${f}`}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Schedule</label>
            <select value={form.schedule_type} onChange={e => set('schedule_type', e.target.value)} className="w-full px-3 py-2 border rounded-lg outline-none">
              <option value="one_time">One Time</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
        </div>
        {/* Required Report Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Required Report Type</label>
          <div className="flex flex-wrap gap-2">
            {[
              { value: 'photo', label: '📸 Photo', desc: 'Shop leader submits photos' },
              { value: 'excel', label: '📊 Excel', desc: 'Excel/spreadsheet file' },
              { value: 'file', label: '📄 File', desc: 'PDF, docs, etc.' },
              { value: 'text', label: '💬 Text', desc: 'Text reply' },
            ].map(rt => {
              const selected = (form.required_report_type || '').split(',').map(t => t.trim()).includes(rt.value);
              return (
                <label key={rt.value} className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm border transition-colors ${selected ? 'bg-blue-50 border-blue-400 text-blue-700' : 'hover:bg-gray-50'}`}>
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => {
                      const current = (form.required_report_type || '').split(',').map(t => t.trim()).filter(Boolean);
                      let next;
                      if (selected) {
                        next = current.filter(t => t !== rt.value);
                      } else {
                        next = [...current, rt.value];
                      }
                      if (next.length === 0) next = ['photo']; // at least one required
                      set('required_report_type', next.join(','));
                    }}
                    className="sr-only"
                  />
                  <span>{rt.label}</span>
                </label>
              );
            })}
          </div>
          <p className="text-xs text-gray-400 mt-1">Select the type(s) of report the shop leader needs to submit</p>
        </div>

        {form.schedule_type !== 'one_time' && (
          <div className="grid grid-cols-2 gap-4">
            {(form.schedule_type === 'weekly' || form.schedule_type === 'monthly') && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {form.schedule_type === 'weekly' ? 'Day (0=Mon-6=Sun)' : 'Day of Month (1-31)'}
                </label>
                <input type="number" value={form.schedule_day} onChange={e => set('schedule_day', e.target.value)} className="w-full px-3 py-2 border rounded-lg outline-none" />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Time</label>
              <input type="time" value={form.schedule_time} onChange={e => set('schedule_time', e.target.value)} className="w-full px-3 py-2 border rounded-lg outline-none" />
            </div>
          </div>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200">Cancel</button>
          <button type="submit" disabled={saving} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Saving...' : task ? 'Update' : 'Create Task'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

/* ───── Shared Modal Shell ───── */
function ModalShell({ children, onClose, wide }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className={`bg-white rounded-xl p-6 ${wide ? 'max-w-2xl' : 'max-w-lg'} w-full mx-4 shadow-xl max-h-[90vh] overflow-y-auto relative`}>
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"><X size={20} /></button>
        {children}
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <div className="mt-0.5 text-gray-900">{value}</div>
    </div>
  );
}

/* ───── Schedule Summary Cards ───── */
function ScheduleSummary({ tasks }) {
  const counts = { one_time: 0, daily: 0, weekly: 0, monthly: 0 };
  tasks.forEach(t => {
    const type = t.schedule_type || 'one_time';
    if (counts[type] !== undefined) counts[type]++;
  });

  const cards = [
    { key: 'one_time', label: 'One-time', icon: Clock, color: 'bg-slate-50 border-slate-200 text-slate-700', iconColor: 'text-slate-500', count: counts.one_time },
    { key: 'daily', label: 'Daily', icon: Repeat, color: 'bg-blue-50 border-blue-200 text-blue-700', iconColor: 'text-blue-500', count: counts.daily },
    { key: 'weekly', label: 'Weekly', icon: CalendarDays, color: 'bg-violet-50 border-violet-200 text-violet-700', iconColor: 'text-violet-500', count: counts.weekly },
    { key: 'monthly', label: 'Monthly', icon: CalendarRange, color: 'bg-amber-50 border-amber-200 text-amber-700', iconColor: 'text-amber-500', count: counts.monthly },
  ];

  return (
    <div className="grid grid-cols-4 gap-3">
      {cards.map(c => {
        const Icon = c.icon;
        return (
          <div key={c.key} className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${c.color}`}>
            <div className={`p-2 rounded-lg bg-white/80 ${c.iconColor}`}>
              <Icon size={20} />
            </div>
            <div>
              <p className="text-2xl font-bold leading-none">{c.count}</p>
              <p className="text-xs mt-0.5 opacity-80">{c.label} Tasks</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ───── Grouping helpers ───── */
function groupTasksByDate(tasks) {
  // Group: month -> week -> day
  const months = {};
  tasks.forEach(task => {
    const d = dayjs(task.created_at);
    const monthKey = d.format('YYYY-MM');
    const monthLabel = d.format('MMMM YYYY');
    const weekKey = `${d.isoWeekYear()}-W${String(d.isoWeek()).padStart(2, '0')}`;
    const weekStart = d.startOf('isoWeek').format('MMM D');
    const weekEnd = d.startOf('isoWeek').add(6, 'day').format('MMM D');
    const weekLabel = `Week ${d.isoWeek()} (${weekStart} - ${weekEnd})`;
    const dayKey = d.format('YYYY-MM-DD');
    const dayLabel = d.format('ddd, MMM D');

    if (!months[monthKey]) months[monthKey] = { label: monthLabel, weeks: {}, count: 0 };
    months[monthKey].count++;
    if (!months[monthKey].weeks[weekKey]) months[monthKey].weeks[weekKey] = { label: weekLabel, days: {}, count: 0 };
    months[monthKey].weeks[weekKey].count++;
    if (!months[monthKey].weeks[weekKey].days[dayKey]) months[monthKey].weeks[weekKey].days[dayKey] = { label: dayLabel, tasks: [] };
    months[monthKey].weeks[weekKey].days[dayKey].tasks.push(task);
  });
  return months;
}

function statusSummary(tasks) {
  const counts = {};
  tasks.forEach(t => { counts[t.status] = (counts[t.status] || 0) + 1; });
  return counts;
}

function StatusDots({ tasks }) {
  const s = statusSummary(tasks);
  const colors = { pending: 'bg-yellow-400', accepted: 'bg-blue-400', in_progress: 'bg-indigo-500', done: 'bg-green-500', overdue: 'bg-red-500', rejected: 'bg-gray-400' };
  return (
    <div className="flex items-center gap-2 text-xs">
      {Object.entries(s).map(([status, count]) => (
        <span key={status} className="flex items-center gap-1">
          <span className={`w-2 h-2 rounded-full ${colors[status] || 'bg-gray-300'}`} />
          <span className="text-gray-500">{count} {status.replace('_', ' ')}</span>
        </span>
      ))}
    </div>
  );
}

/* ───── Task Row (shared between table and grouped view) ───── */
function TaskRow({ task, onView, onEdit, onDelete, onFine }) {
  return (
    <tr className={`hover:bg-gray-50 ${task.status === 'overdue' ? 'bg-red-50' : task.status === 'done' ? 'bg-green-50/50' : ''} ${task.priority === 'urgent' ? 'border-l-4 border-l-red-500' : ''}`}>
      <td className="px-4 py-2.5 font-mono text-xs">{task.task_id}</td>
      <td className="px-4 py-2.5 font-medium max-w-[200px] truncate">{task.title}</td>
      <td className="px-4 py-2.5 text-gray-600">{task.shop_name}</td>
      <td className="px-4 py-2.5 text-center"><PriorityBadge priority={task.priority} /></td>
      <td className="px-4 py-2.5 text-center"><StatusBadge status={task.status} /></td>
      <td className="px-4 py-2.5 text-xs">
        {task.deadline ? (
          <div>
            <div>{dayjs(task.deadline).format('MM/DD HH:mm')}</div>
            <div className="text-gray-400">{dayjs(task.deadline).fromNow()}</div>
          </div>
        ) : 'N/A'}
      </td>
      <td className="px-4 py-2.5 text-center">
        <div className="flex flex-wrap justify-center gap-1">
          {(task.required_report_type || 'photo').split(',').map(t => <ReportTypeBadge key={t} type={t.trim()} />)}
        </div>
      </td>
      <td className="px-4 py-2.5 text-right">{task.fine_amount_mmk || 0}</td>
      <td className="px-4 py-2.5 text-right">
        <div className="flex justify-end gap-1">
          <button onClick={() => onView(task.id)} className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded" title="View"><Eye size={16} /></button>
          <button onClick={() => onEdit(task)} className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded" title="Edit"><Pencil size={16} /></button>
          <button onClick={() => onDelete(task)} className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded" title="Delete"><Trash2 size={16} /></button>
          {task.status === 'overdue' && (
            <button onClick={() => onFine(task)} className="p-1.5 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded" title="Fine"><DollarSign size={16} /></button>
          )}
        </div>
      </td>
    </tr>
  );
}

/* ───── Expandable Grouped View ───── */
function GroupedTaskView({ tasks, onView, onEdit, onDelete, onFine }) {
  const grouped = groupTasksByDate(tasks);
  const monthKeys = Object.keys(grouped).sort().reverse();
  const [expandedMonths, setExpandedMonths] = useState(() => new Set(monthKeys.slice(0, 2)));
  const [expandedWeeks, setExpandedWeeks] = useState(() => new Set());
  const [expandedDays, setExpandedDays] = useState(() => new Set());

  // Auto-expand current month/week/day
  useEffect(() => {
    const now = dayjs();
    const curMonth = now.format('YYYY-MM');
    const curWeek = `${now.isoWeekYear()}-W${String(now.isoWeek()).padStart(2, '0')}`;
    const curDay = now.format('YYYY-MM-DD');
    setExpandedMonths(prev => new Set([...prev, curMonth]));
    setExpandedWeeks(prev => new Set([...prev, curWeek]));
    setExpandedDays(prev => new Set([...prev, curDay]));
  }, [tasks]);

  const toggle = (set, setter, key) => {
    setter(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  if (tasks.length === 0) {
    return <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400">No tasks found.</div>;
  }

  return (
    <div className="space-y-3">
      {monthKeys.map(monthKey => {
        const month = grouped[monthKey];
        const isMonthOpen = expandedMonths.has(monthKey);
        const weekKeys = Object.keys(month.weeks).sort().reverse();
        const allMonthTasks = weekKeys.flatMap(wk => Object.values(month.weeks[wk].days).flatMap(d => d.tasks));

        return (
          <div key={monthKey} className="bg-white rounded-xl shadow-sm overflow-hidden">
            {/* Month Header */}
            <button
              onClick={() => toggle(expandedMonths, setExpandedMonths, monthKey)}
              className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-gray-50 transition-colors"
            >
              {isMonthOpen ? <ChevronDown size={18} className="text-blue-500" /> : <ChevronRight size={18} className="text-gray-400" />}
              <Calendar size={18} className="text-blue-500" />
              <span className="font-semibold text-gray-900">{month.label}</span>
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">{month.count} tasks</span>
              <div className="ml-auto"><StatusDots tasks={allMonthTasks} /></div>
            </button>

            {isMonthOpen && (
              <div className="border-t">
                {weekKeys.map(weekKey => {
                  const week = month.weeks[weekKey];
                  const isWeekOpen = expandedWeeks.has(weekKey);
                  const dayKeys = Object.keys(week.days).sort().reverse();
                  const allWeekTasks = dayKeys.flatMap(dk => week.days[dk].tasks);

                  return (
                    <div key={weekKey}>
                      {/* Week Header */}
                      <button
                        onClick={() => toggle(expandedWeeks, setExpandedWeeks, weekKey)}
                        className="w-full flex items-center gap-3 px-8 py-2.5 hover:bg-blue-50/50 transition-colors border-b border-gray-100"
                      >
                        {isWeekOpen ? <ChevronDown size={16} className="text-indigo-500" /> : <ChevronRight size={16} className="text-gray-400" />}
                        <span className="font-medium text-indigo-700 text-sm">{week.label}</span>
                        <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">{week.count}</span>
                        <div className="ml-auto"><StatusDots tasks={allWeekTasks} /></div>
                      </button>

                      {isWeekOpen && (
                        <div>
                          {dayKeys.map(dayKey => {
                            const day = week.days[dayKey];
                            const isDayOpen = expandedDays.has(dayKey);
                            const isToday = dayKey === dayjs().format('YYYY-MM-DD');

                            return (
                              <div key={dayKey}>
                                {/* Day Header */}
                                <button
                                  onClick={() => toggle(expandedDays, setExpandedDays, dayKey)}
                                  className={`w-full flex items-center gap-3 px-12 py-2 hover:bg-gray-50 transition-colors border-b border-gray-50 ${isToday ? 'bg-green-50/50' : ''}`}
                                >
                                  {isDayOpen ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronRight size={14} className="text-gray-400" />}
                                  <span className={`text-sm ${isToday ? 'font-semibold text-green-700' : 'font-medium text-gray-700'}`}>
                                    {day.label} {isToday && <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full ml-1">Today</span>}
                                  </span>
                                  <span className="text-xs text-gray-400">{day.tasks.length} tasks</span>
                                  <div className="ml-auto"><StatusDots tasks={day.tasks} /></div>
                                </button>

                                {isDayOpen && (
                                  <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                      <thead className="bg-gray-50/80">
                                        <tr>
                                          <th className="px-4 py-2 text-left text-gray-500 font-medium text-xs">Task ID</th>
                                          <th className="px-4 py-2 text-left text-gray-500 font-medium text-xs">Title</th>
                                          <th className="px-4 py-2 text-left text-gray-500 font-medium text-xs">Shop</th>
                                          <th className="px-4 py-2 text-center text-gray-500 font-medium text-xs">Priority</th>
                                          <th className="px-4 py-2 text-center text-gray-500 font-medium text-xs">Status</th>
                                          <th className="px-4 py-2 text-left text-gray-500 font-medium text-xs">Deadline</th>
                                          <th className="px-4 py-2 text-center text-gray-500 font-medium text-xs">Report</th>
                                          <th className="px-4 py-2 text-right text-gray-500 font-medium text-xs">Fine</th>
                                          <th className="px-4 py-2 text-right text-gray-500 font-medium text-xs">Actions</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-gray-50">
                                        {day.tasks.map(task => (
                                          <TaskRow key={task.id} task={task} onView={onView} onEdit={onEdit} onDelete={onDelete} onFine={onFine} />
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ───── Flat Table View ───── */
function FlatTaskTable({ tasks, onView, onEdit, onDelete, onFine }) {
  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-gray-500 font-medium">Task ID</th>
              <th className="px-4 py-3 text-left text-gray-500 font-medium">Title</th>
              <th className="px-4 py-3 text-left text-gray-500 font-medium">Shop</th>
              <th className="px-4 py-3 text-center text-gray-500 font-medium">Priority</th>
              <th className="px-4 py-3 text-center text-gray-500 font-medium">Status</th>
              <th className="px-4 py-3 text-left text-gray-500 font-medium">Deadline</th>
              <th className="px-4 py-3 text-center text-gray-500 font-medium">Report Type</th>
              <th className="px-4 py-3 text-right text-gray-500 font-medium">Fine</th>
              <th className="px-4 py-3 text-right text-gray-500 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tasks.map(task => (
              <TaskRow key={task.id} task={task} onView={onView} onEdit={onEdit} onDelete={onDelete} onFine={onFine} />
            ))}
            {tasks.length === 0 && (
              <tr><td colSpan={9} className="text-center py-10 text-gray-400">No tasks found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ───── Default Deadline Helper ───── */
function getDefaultDeadline() {
  const now = dayjs();
  let deadline = now.add(3, 'hour');
  // Shop closing time: 6:30 PM
  const closing = now.hour(18).minute(30).second(0);
  if (deadline.isAfter(closing)) {
    deadline = closing;
  }
  // If already past closing, set to next day 6:30 PM
  if (now.isAfter(closing)) {
    deadline = closing.add(1, 'day');
  }
  return deadline.format('YYYY-MM-DDTHH:mm');
}

/* ───── Announcement Modal ───── */
function AnnouncementModal({ isOpen, shops, onClose }) {
  const [message, setMessage] = useState('');
  const [targetType, setTargetType] = useState('all');
  const [targetShopId, setTargetShopId] = useState('');
  const [sending, setSending] = useState(false);
  const [announcements, setAnnouncements] = useState([]);
  const [viewMode, setViewMode] = useState('create'); // 'create' or 'history'

  const loadAnnouncements = useCallback(() => {
    api.get('/announcements').then(r => setAnnouncements(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (isOpen) loadAnnouncements();
  }, [isOpen, loadAnnouncements]);

  // Auto-refresh every 10s
  useEffect(() => {
    if (!isOpen) return;
    const interval = setInterval(loadAnnouncements, 10000);
    return () => clearInterval(interval);
  }, [isOpen, loadAnnouncements]);

  if (!isOpen) return null;

  const handleSend = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    setSending(true);
    try {
      const payload = { message: message.trim(), target_type: targetType };
      if (targetType === 'single') payload.target_shop_id = Number(targetShopId);
      await api.post('/announcements', payload);
      setMessage('');
      setViewMode('history');
      loadAnnouncements();
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to send');
    } finally {
      setSending(false);
    }
  };

  const handleDelete = async (id) => {
    await api.delete(`/announcements/${id}`).catch(() => {});
    loadAnnouncements();
  };

  return (
    <ModalShell onClose={onClose} wide>
      <div className="flex items-center gap-3 mb-4">
        <Megaphone size={22} className="text-orange-500" />
        <h3 className="text-lg font-semibold">Announcements</h3>
        <div className="ml-auto flex bg-gray-100 rounded-lg p-0.5">
          <button
            onClick={() => setViewMode('create')}
            className={`px-3 py-1 rounded-md text-sm ${viewMode === 'create' ? 'bg-white shadow font-medium text-blue-600' : 'text-gray-500'}`}
          >New</button>
          <button
            onClick={() => setViewMode('history')}
            className={`px-3 py-1 rounded-md text-sm ${viewMode === 'history' ? 'bg-white shadow font-medium text-blue-600' : 'text-gray-500'}`}
          >History ({announcements.length})</button>
        </div>
      </div>

      {viewMode === 'create' ? (
        <form onSubmit={handleSend} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Message</label>
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              rows={4}
              required
              placeholder="အသိပေးချင်တဲ့ message ရေးပါ..."
              className="w-full px-3 py-2 border rounded-lg outline-none focus:ring-2 focus:ring-orange-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Send To</label>
            <div className="flex gap-3">
              <label className={`flex-1 text-center py-2.5 rounded-lg cursor-pointer text-sm border ${targetType === 'all' ? 'bg-orange-50 border-orange-400 text-orange-700 font-medium' : 'hover:bg-gray-50'}`}>
                <input type="radio" name="target" value="all" checked={targetType === 'all'} onChange={() => setTargetType('all')} className="sr-only" />
                All Shops
              </label>
              <label className={`flex-1 text-center py-2.5 rounded-lg cursor-pointer text-sm border ${targetType === 'single' ? 'bg-orange-50 border-orange-400 text-orange-700 font-medium' : 'hover:bg-gray-50'}`}>
                <input type="radio" name="target" value="single" checked={targetType === 'single'} onChange={() => setTargetType('single')} className="sr-only" />
                Single Shop
              </label>
            </div>
          </div>
          {targetType === 'single' && (
            <select
              value={targetShopId}
              onChange={e => setTargetShopId(e.target.value)}
              required
              className="w-full px-3 py-2 border rounded-lg outline-none"
            >
              <option value="">Select shop...</option>
              {shops.map(s => <option key={s.id} value={s.id}>{s.shop_name}</option>)}
            </select>
          )}
          <div className="flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200">Cancel</button>
            <button type="submit" disabled={sending} className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50">
              <Send size={16} /> {sending ? 'Sending...' : 'Send Announcement'}
            </button>
          </div>
        </form>
      ) : (
        <div className="space-y-4 max-h-[60vh] overflow-y-auto">
          {announcements.length === 0 ? (
            <p className="text-center text-gray-400 py-8">No announcements yet.</p>
          ) : announcements.map(ann => (
            <div key={ann.id} className="border rounded-xl p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-sm text-gray-800 whitespace-pre-wrap">{ann.message}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                    <span>{dayjs(ann.created_at).format('MM/DD HH:mm')}</span>
                    <span>{ann.target_type === 'all' ? 'All Shops' : ann.target_shop_name}</span>
                  </div>
                </div>
                <button onClick={() => handleDelete(ann.id)} className="p-1 text-gray-400 hover:text-red-500"><Trash2 size={14} /></button>
              </div>

              {/* Response summary bar */}
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="font-medium">{ann.agree_count}</span>
                  <span className="text-gray-400">Agree</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-blue-500" />
                  <span className="font-medium">{ann.acknowledge_count}</span>
                  <span className="text-gray-400">Ack</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-red-500" />
                  <span className="font-medium">{ann.disagree_count}</span>
                  <span className="text-gray-400">Disagree</span>
                </div>
                <div className="ml-auto text-xs text-gray-400">
                  {ann.responded_count}/{ann.total_targets} responded
                </div>
              </div>

              {/* Progress bar */}
              {ann.total_targets > 0 && (
                <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden flex">
                  {ann.agree_count > 0 && <div className="bg-green-500 h-full" style={{ width: `${(ann.agree_count / ann.total_targets) * 100}%` }} />}
                  {ann.acknowledge_count > 0 && <div className="bg-blue-500 h-full" style={{ width: `${(ann.acknowledge_count / ann.total_targets) * 100}%` }} />}
                  {ann.disagree_count > 0 && <div className="bg-red-500 h-full" style={{ width: `${(ann.disagree_count / ann.total_targets) * 100}%` }} />}
                </div>
              )}

              {/* Individual responses */}
              {ann.responses?.length > 0 && (
                <div className="grid grid-cols-2 gap-1.5">
                  {ann.responses.map(r => {
                    const color = r.response === 'agree' ? 'bg-green-50 text-green-700 border-green-200'
                      : r.response === 'acknowledge' ? 'bg-blue-50 text-blue-700 border-blue-200'
                      : 'bg-red-50 text-red-700 border-red-200';
                    const emoji = r.response === 'agree' ? '✅' : r.response === 'acknowledge' ? '👁' : '❌';
                    return (
                      <div key={r.id} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs ${color}`}>
                        <span>{emoji}</span>
                        <span className="font-medium">{r.shop_name}</span>
                        <span className="ml-auto opacity-60">{dayjs(r.responded_at).format('HH:mm')}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </ModalShell>
  );
}

/* ───── Main Tasks Page ───── */
export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [shops, setShops] = useState([]);
  const [filters, setFilters] = useState({ status: 'all', shop_id: '', priority: 'all', search: '' });
  const [viewMode, setViewMode] = useState('grouped'); // 'grouped' or 'table'
  const [formOpen, setFormOpen] = useState(false);
  const [editTask, setEditTask] = useState(null);
  const [viewTaskId, setViewTaskId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [fineTask, setFineTask] = useState(null);
  const [announcementOpen, setAnnouncementOpen] = useState(false);

  const loadTasks = useCallback(() => {
    const params = {};
    if (filters.status !== 'all') params.status = filters.status;
    if (filters.shop_id) params.shop_id = filters.shop_id;
    if (filters.priority !== 'all') params.priority = filters.priority;
    if (filters.search) params.search = filters.search;
    api.get('/tasks', { params }).then(r => setTasks(r.data)).catch(() => {});
  }, [filters]);

  useEffect(() => { loadTasks(); }, [loadTasks]);
  useEffect(() => { api.get('/shops').then(r => setShops(r.data)).catch(() => {}); }, []);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(loadTasks, 10000);
    return () => clearInterval(interval);
  }, [loadTasks]);

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    await api.delete(`/tasks/${deleteConfirm.id}`).catch(() => {});
    setDeleteConfirm(null);
    loadTasks();
  };

  const handleFine = async (amount) => {
    if (!fineTask) return;
    await api.post(`/tasks/${fineTask.id}/fine`, { amount_mmk: amount }).catch(() => {});
    setFineTask(null);
    loadTasks();
  };

  const setFilter = (k, v) => setFilters(f => ({ ...f, [k]: v }));

  const viewActions = {
    onView: (id) => setViewTaskId(id),
    onEdit: (task) => { setEditTask(task); setFormOpen(true); },
    onDelete: (task) => setDeleteConfirm(task),
    onFine: (task) => setFineTask(task),
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Tasks</h1>
        <div className="flex items-center gap-3">
          {/* View Toggle */}
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('grouped')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${viewMode === 'grouped' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
            >
              <LayoutList size={15} /> Grouped
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${viewMode === 'table' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
            >
              <List size={15} /> Table
            </button>
          </div>
          <button
            onClick={() => setAnnouncementOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600"
          >
            <Megaphone size={18} /> Announcement
          </button>
          <button
            onClick={() => { setEditTask(null); setFormOpen(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus size={18} /> Create Task
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 bg-white rounded-xl shadow-sm p-4">
        <select value={filters.status} onChange={e => setFilter('status', e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
          <option value="all">All Status</option>
          {['pending', 'accepted', 'in_progress', 'done', 'overdue'].map(s => (
            <option key={s} value={s} className="capitalize">{s.replace('_', ' ')}</option>
          ))}
        </select>
        <select value={filters.shop_id} onChange={e => setFilter('shop_id', e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
          <option value="">All Shops</option>
          {shops.map(s => <option key={s.id} value={s.id}>{s.shop_name}</option>)}
        </select>
        <select value={filters.priority} onChange={e => setFilter('priority', e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
          <option value="all">All Priority</option>
          {['low', 'medium', 'high', 'urgent'].map(p => <option key={p} value={p} className="capitalize">{p}</option>)}
        </select>
        <input
          type="text"
          value={filters.search}
          onChange={e => setFilter('search', e.target.value)}
          placeholder="Search task ID or title..."
          className="px-3 py-2 border rounded-lg text-sm flex-1 min-w-[200px]"
        />
      </div>

      {/* Schedule Summary */}
      <ScheduleSummary tasks={tasks} />

      {/* Task Views */}
      {viewMode === 'grouped' ? (
        <GroupedTaskView tasks={tasks} {...viewActions} />
      ) : (
        <FlatTaskTable tasks={tasks} {...viewActions} />
      )}

      {/* Modals */}
      <TaskFormModal
        isOpen={formOpen}
        task={editTask}
        shops={shops}
        onClose={() => setFormOpen(false)}
        onSave={() => { setFormOpen(false); loadTasks(); }}
      />

      <TaskDetailModal taskId={viewTaskId} shops={shops} onClose={() => setViewTaskId(null)} onReload={loadTasks} />

      <ConfirmDialog
        isOpen={!!deleteConfirm}
        title="Delete Task"
        message={`Delete task "${deleteConfirm?.task_id}"? This will notify the shop.`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm(null)}
      />

      {/* Announcement Modal */}
      <AnnouncementModal isOpen={announcementOpen} shops={shops} onClose={() => setAnnouncementOpen(false)} />

      {/* Fine Modal */}
      {fineTask && (
        <ModalShell onClose={() => setFineTask(null)}>
          <h3 className="text-lg font-semibold mb-4">Apply Fine</h3>
          <p className="text-sm text-gray-600 mb-4">Task: {fineTask.task_id}</p>
          <div className="flex gap-3">
            <button onClick={() => handleFine(500)} className="flex-1 py-3 bg-orange-100 text-orange-700 rounded-lg hover:bg-orange-200 font-medium">500 MMK</button>
            <button onClick={() => handleFine(1000)} className="flex-1 py-3 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 font-medium">1000 MMK</button>
          </div>
        </ModalShell>
      )}
    </div>
  );
}
