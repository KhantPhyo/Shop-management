import { useState, useEffect } from 'react';
import { ClipboardList, Clock, Loader, CheckCircle, AlertTriangle, Banknote } from 'lucide-react';
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import StatsCard from '../components/StatsCard';
import api from '../api';

const PIE_COLORS = ['#9ca3af', '#3b82f6', '#f97316', '#22c55e', '#ef4444'];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [kpi, setKpi] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [shopPerf, setShopPerf] = useState([]);
  const [timelineDays, setTimelineDays] = useState(7);
  const [perfPeriod, setPerfPeriod] = useState('month');

  useEffect(() => {
    api.get('/dashboard/stats').then(r => setStats(r.data)).catch(() => {});
    api.get('/dashboard/kpi').then(r => setKpi(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    api.get(`/dashboard/task-timeline?days=${timelineDays}`).then(r => setTimeline(r.data)).catch(() => {});
  }, [timelineDays]);

  useEffect(() => {
    api.get(`/dashboard/shop-performance?period=${perfPeriod}`).then(r => setShopPerf(r.data)).catch(() => {});
  }, [perfPeriod]);

  if (!stats) return <div className="flex items-center justify-center h-64 text-gray-500">Loading...</div>;

  const pieData = [
    { name: 'Pending', value: stats.pending_count },
    { name: 'Accepted', value: stats.accepted_count },
    { name: 'In Progress', value: stats.in_progress_count },
    { name: 'Done', value: stats.done_count },
    { name: 'Overdue', value: stats.overdue_count },
  ].filter(d => d.value > 0);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatsCard icon={ClipboardList} label="Total Today" value={stats.total_tasks_today} color="blue" />
        <StatsCard icon={Clock} label="Pending" value={stats.pending_count} color="amber" />
        <StatsCard icon={Loader} label="In Progress" value={stats.in_progress_count} color="orange" />
        <StatsCard icon={CheckCircle} label="Completed" value={stats.done_count} color="green" />
        <StatsCard icon={AlertTriangle} label="Overdue" value={stats.overdue_count} color="red" />
        <StatsCard icon={Banknote} label="Fines (MMK)" value={stats.total_fines_mmk?.toLocaleString()} color="purple" />
      </div>

      {/* KPI Cards */}
      {kpi && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[
            { label: 'Fastest Shop', value: `${kpi.fastest_shop.shop_name} (${kpi.fastest_shop.avg_hours}h)` },
            { label: 'Slowest Shop', value: `${kpi.slowest_shop.shop_name} (${kpi.slowest_shop.avg_hours}h)` },
            { label: 'Most Tasks', value: `${kpi.most_tasks_shop.shop_name} (${kpi.most_tasks_shop.count})` },
            { label: 'Best Completion', value: `${kpi.highest_completion_rate.shop_name} (${kpi.highest_completion_rate.rate}%)` },
            { label: 'Overdue Rate', value: `${kpi.overdue_rate_percent}%` },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-sm font-semibold text-gray-900 mt-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Timeline Chart */}
        <div className="bg-white rounded-xl shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Task Timeline</h2>
            <select
              value={timelineDays}
              onChange={e => setTimelineDays(Number(e.target.value))}
              className="text-sm border rounded-lg px-2 py-1"
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
            </select>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Area type="monotone" dataKey="created" stroke="#3b82f6" fill="#93c5fd" name="Created" />
              <Area type="monotone" dataKey="completed" stroke="#22c55e" fill="#86efac" name="Completed" />
              <Area type="monotone" dataKey="overdue" stroke="#ef4444" fill="#fca5a5" name="Overdue" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Status Pie */}
        <div className="bg-white rounded-xl shadow-sm p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Today's Status</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[250px] text-gray-400">No tasks today</div>
          )}
        </div>
      </div>

      {/* Shop Performance */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Shop Performance</h2>
          <select
            value={perfPeriod}
            onChange={e => setPerfPeriod(e.target.value)}
            className="text-sm border rounded-lg px-2 py-1"
          >
            <option value="today">Today</option>
            <option value="week">Week</option>
            <option value="month">Month</option>
            <option value="all">All</option>
          </select>
        </div>
        {shopPerf.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={shopPerf}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="shop_name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar dataKey="completed" fill="#22c55e" name="Completed" />
              <Bar dataKey="pending" fill="#f59e0b" name="Pending" />
              <Bar dataKey="overdue" fill="#ef4444" name="Overdue" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center text-gray-400 py-10">No data available</div>
        )}
      </div>

      {/* Shop Ranking Table */}
      {shopPerf.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="p-5 border-b">
            <h2 className="font-semibold text-gray-900">Shop Ranking</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-gray-500 font-medium">Rank</th>
                  <th className="px-4 py-3 text-left text-gray-500 font-medium">Shop</th>
                  <th className="px-4 py-3 text-right text-gray-500 font-medium">Total</th>
                  <th className="px-4 py-3 text-right text-gray-500 font-medium">Completed</th>
                  <th className="px-4 py-3 text-right text-gray-500 font-medium">Avg Hours</th>
                  <th className="px-4 py-3 text-right text-gray-500 font-medium">Rate %</th>
                  <th className="px-4 py-3 text-right text-gray-500 font-medium">Fines MMK</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {shopPerf.map((s, i) => (
                  <tr key={s.shop_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{i + 1}</td>
                    <td className="px-4 py-3">{s.shop_name}</td>
                    <td className="px-4 py-3 text-right">{s.total_tasks}</td>
                    <td className="px-4 py-3 text-right text-green-600">{s.completed}</td>
                    <td className="px-4 py-3 text-right">{s.avg_completion_hours}</td>
                    <td className="px-4 py-3 text-right">{s.completion_rate_percent}%</td>
                    <td className="px-4 py-3 text-right text-red-600">{s.fines_total_mmk?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
