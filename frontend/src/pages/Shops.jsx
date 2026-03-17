import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, Send, CheckCircle, Loader2, AlertCircle } from 'lucide-react';
import ConfirmDialog from '../components/ConfirmDialog';
import api from '../api';

function ShopModal({ isOpen, shop, onClose, onSave }) {
  const [form, setForm] = useState({ shop_name: '', leader_name: '', phone_number: '', telegram_bot_token: '', telegram_chat_id: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Telegram verification states
  const [fetchingChatId, setFetchingChatId] = useState(false);
  const [chatIdResult, setChatIdResult] = useState(null); // { chat_ids: [], bot_name, message }
  const [activating, setActivating] = useState(false);
  const [activateResult, setActivateResult] = useState(null); // { success, message/error }

  useEffect(() => {
    if (shop) setForm({ shop_name: shop.shop_name, leader_name: shop.leader_name, phone_number: shop.phone_number, telegram_bot_token: shop.telegram_bot_token, telegram_chat_id: shop.telegram_chat_id });
    else setForm({ shop_name: '', leader_name: '', phone_number: '', telegram_bot_token: '', telegram_chat_id: '' });
    setChatIdResult(null);
    setActivateResult(null);
    setError('');
  }, [shop, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      if (shop) {
        await api.put(`/shops/${shop.id}`, form);
      } else {
        await api.post('/shops', form);
      }
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleGetChatId = async () => {
    if (!form.telegram_bot_token.trim()) {
      setError('Please enter the Telegram Bot Token first');
      return;
    }
    setFetchingChatId(true);
    setChatIdResult(null);
    setError('');
    try {
      const res = await api.post('/shops/get-chat-id', { telegram_bot_token: form.telegram_bot_token });
      setChatIdResult(res.data);
      // Auto-fill if exactly one chat found
      if (res.data.chat_ids?.length === 1) {
        setForm(f => ({ ...f, telegram_chat_id: res.data.chat_ids[0].chat_id }));
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch chat ID');
    } finally {
      setFetchingChatId(false);
    }
  };

  const handleSelectChatId = (chatId) => {
    setForm(f => ({ ...f, telegram_chat_id: chatId }));
    setActivateResult(null);
  };

  const handleActivate = async () => {
    if (!form.telegram_bot_token.trim() || !form.telegram_chat_id.trim()) {
      setError('Both Bot Token and Chat ID are required to activate');
      return;
    }
    setActivating(true);
    setActivateResult(null);
    setError('');
    try {
      const res = await api.post('/shops/test-bot', {
        telegram_bot_token: form.telegram_bot_token,
        telegram_chat_id: form.telegram_chat_id
      });
      setActivateResult({ success: true, message: res.data.message });
    } catch (err) {
      setActivateResult({ success: false, message: err.response?.data?.error || 'Activation failed' });
    } finally {
      setActivating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 max-w-lg w-full mx-4 shadow-xl max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold mb-4">{shop ? 'Edit Shop' : 'Add New Shop'}</h3>
        {error && <div className="bg-red-50 text-red-600 px-4 py-2 rounded-lg text-sm mb-4">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Shop Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Shop Name</label>
            <input type="text" value={form.shop_name} onChange={e => setForm({ ...form, shop_name: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required />
          </div>

          {/* Leader Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Leader Name</label>
            <input type="text" value={form.leader_name} onChange={e => setForm({ ...form, leader_name: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required />
          </div>

          {/* Phone Number */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
            <input type="text" value={form.phone_number} onChange={e => setForm({ ...form, phone_number: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required />
          </div>

          {/* Telegram Bot Token + Send Chat ID button */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Telegram Bot Token</label>
            <div className="flex gap-2">
              <input type="text" value={form.telegram_bot_token}
                onChange={e => { setForm({ ...form, telegram_bot_token: e.target.value }); setChatIdResult(null); setActivateResult(null); }}
                className="flex-1 px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                placeholder="Paste token from @BotFather" required />
              <button type="button" onClick={handleGetChatId} disabled={fetchingChatId || !form.telegram_bot_token.trim()}
                className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 whitespace-nowrap"
                title="Fetch Chat IDs from bot updates">
                {fetchingChatId ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                Send Chat ID
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1">Get token from @BotFather on Telegram</p>
          </div>

          {/* Chat ID search results */}
          {chatIdResult && (
            <div className="bg-gray-50 rounded-lg p-3 text-sm">
              <p className="text-gray-600 mb-2">{chatIdResult.message}</p>
              {chatIdResult.chat_ids?.length > 0 && (
                <div className="space-y-1.5">
                  {chatIdResult.chat_ids.map(c => (
                    <button key={c.chat_id} type="button"
                      onClick={() => handleSelectChatId(c.chat_id)}
                      className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
                        form.telegram_chat_id === c.chat_id
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/50'
                      }`}>
                      <span className="font-mono font-medium">{c.chat_id}</span>
                      {c.name && <span className="text-gray-500 ml-2">— {c.name}</span>}
                      {c.username && <span className="text-gray-400 ml-1">@{c.username}</span>}
                    </button>
                  ))}
                </div>
              )}
              {chatIdResult.chat_ids?.length === 0 && (
                <p className="text-amber-600 text-xs mt-1">
                  Tip: Open Telegram, find @{chatIdResult.bot_name}, send <code className="bg-amber-100 px-1 rounded">/start</code>, then click "Send Chat ID" again.
                </p>
              )}
            </div>
          )}

          {/* Telegram Chat ID + Activate button */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Telegram Chat ID</label>
            <div className="flex gap-2">
              <input type="text" value={form.telegram_chat_id}
                onChange={e => { setForm({ ...form, telegram_chat_id: e.target.value }); setActivateResult(null); }}
                className="flex-1 px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                placeholder="Chat ID from above or paste manually" required />
              <button type="button" onClick={handleActivate}
                disabled={activating || !form.telegram_bot_token.trim() || !form.telegram_chat_id.trim()}
                className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50 whitespace-nowrap"
                title="Send a test message to verify the connection">
                {activating ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                Activate
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1">Leader's Telegram Chat ID</p>
          </div>

          {/* Activate result */}
          {activateResult && (
            <div className={`flex items-start gap-2 px-4 py-3 rounded-lg text-sm ${
              activateResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
            }`}>
              {activateResult.success
                ? <CheckCircle size={16} className="mt-0.5 flex-shrink-0" />
                : <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />}
              <span>{activateResult.message}</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200">Cancel</button>
            <button type="submit" disabled={saving} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Shops() {
  const [shops, setShops] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editShop, setEditShop] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const loadShops = () => api.get('/shops').then(r => setShops(r.data)).catch(() => {});

  useEffect(() => { loadShops(); }, []);

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      await api.delete(`/shops/${deleteConfirm.id}`);
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to delete shop');
    }
    setDeleteConfirm(null);
    loadShops();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Shops</h1>
        <button
          onClick={() => { setEditShop(null); setModalOpen(true); }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus size={18} /> Add Shop
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-gray-500 font-medium">ID</th>
                <th className="px-4 py-3 text-left text-gray-500 font-medium">Shop Name</th>
                <th className="px-4 py-3 text-left text-gray-500 font-medium">Leader</th>
                <th className="px-4 py-3 text-left text-gray-500 font-medium">Phone</th>
                <th className="px-4 py-3 text-center text-gray-500 font-medium">Status</th>
                <th className="px-4 py-3 text-center text-gray-500 font-medium">Active Tasks</th>
                <th className="px-4 py-3 text-right text-gray-500 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {shops.map(shop => (
                <tr key={shop.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">{shop.id}</td>
                  <td className="px-4 py-3 font-medium">{shop.shop_name}</td>
                  <td className="px-4 py-3">{shop.leader_name}</td>
                  <td className="px-4 py-3">{shop.phone_number}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`inline-block w-3 h-3 rounded-full ${shop.is_active ? 'bg-green-500' : 'bg-red-500'}`} />
                  </td>
                  <td className="px-4 py-3 text-center">{shop.active_tasks || 0}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => { setEditShop(shop); setModalOpen(true); }}
                        className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(shop)}
                        className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {shops.length === 0 && (
                <tr><td colSpan={7} className="text-center py-10 text-gray-400">No shops yet. Add one to get started.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ShopModal
        isOpen={modalOpen}
        shop={editShop}
        onClose={() => setModalOpen(false)}
        onSave={() => { setModalOpen(false); loadShops(); }}
      />

      <ConfirmDialog
        isOpen={!!deleteConfirm}
        title="Delete Shop"
        message={`Are you sure you want to deactivate "${deleteConfirm?.shop_name}"?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm(null)}
      />
    </div>
  );
}
