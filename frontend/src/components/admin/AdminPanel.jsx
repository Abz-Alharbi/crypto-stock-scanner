import React, { useEffect, useState } from 'react';
import { Settings, Users, BarChart3, RefreshCw, Shield, Database, AlertCircle } from 'lucide-react';
import { adminAPI } from '../../services/api';
import useAuthStore from '../../store/useAuthStore';
import LoadingSpinner from '../common/LoadingSpinner';

export default function AdminPanel() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [scans, setScans] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [loadErrors, setLoadErrors] = useState({ stats: null, users: null, scans: null });

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    setLoadErrors({ stats: null, users: null, scans: null });

    const loadSection = async (section, request, applyData, clearData) => {
      try {
        const response = await request();
        applyData(response.data);
        return null;
      } catch (err) {
        console.error(`Admin ${section} load failed:`, err);
        clearData();
        return err.response?.data?.error || err.message || `Failed to load ${section}`;
      }
    };

    const [statsError, usersError, scansError] = await Promise.all([
      loadSection('overview stats', adminAPI.getStats, (data) => setStats(data), () => setStats(null)),
      loadSection('users', adminAPI.getUsers, (data) => setUsers(data.users || []), () => setUsers([])),
      loadSection('scan history', adminAPI.getScans, (data) => setScans(data.scans || []), () => setScans([])),
    ]);

    setLoadErrors({ stats: statsError, users: usersError, scans: scansError });
    setLoading(false);
  };

  const updateUser = async (id, updates) => {
    try {
      await adminAPI.updateUser(id, updates);
      loadData();
    } catch (err) {
      console.error('Update failed:', err);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="bg-scanner-card border border-scanner-border rounded-2xl p-12 text-center">
        <Shield size={48} className="mx-auto text-scanner-danger/30 mb-4" />
        <h3 className="font-display text-xl font-bold">Admin Access Required</h3>
        <p className="text-sm text-scanner-text-dim mt-2">You need admin privileges to view this panel.</p>
      </div>
    );
  }

  if (loading) return <LoadingSpinner text="Loading admin data..." />;

  const tabs = [
    { key: 'overview', label: 'Overview', icon: BarChart3 },
    { key: 'users', label: 'Users', icon: Users },
    { key: 'scans', label: 'Scan History', icon: Database },
  ];

  const SectionError = ({ message }) => message ? (
    <div className="bg-scanner-danger/10 border border-scanner-danger/30 rounded-xl p-4 text-sm text-scanner-danger flex items-center gap-2">
      <AlertCircle size={16} />
      <span>{message}</span>
    </div>
  ) : null;

  return (
    <div className="space-y-4">
      {/* Tab nav */}
      <div className="flex gap-1 bg-scanner-card border border-scanner-border rounded-xl p-1">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === key ? 'bg-scanner-accent text-scanner-bg' : 'text-scanner-text-dim hover:text-scanner-text hover:bg-scanner-bg'
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
        <button onClick={loadData} className="ml-auto p-2 rounded-lg hover:bg-scanner-bg text-scanner-text-dim hover:text-scanner-accent transition-colors">
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Overview */}
      {activeTab === 'overview' && <SectionError message={loadErrors.stats} />}
      {activeTab === 'overview' && stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Users', value: stats.total_users, icon: Users, color: 'text-blue-400' },
            { label: 'Active Users', value: stats.active_users, icon: Users, color: 'text-scanner-accent' },
            { label: 'Total Scans', value: stats.total_scans, icon: BarChart3, color: 'text-purple-400' },
            { label: 'Cache Entries', value: stats.cache_entries, icon: Database, color: 'text-amber-400' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-scanner-card border border-scanner-border rounded-xl p-5">
              <Icon size={20} className={`${color} mb-2`} />
              <p className="font-mono text-2xl font-bold">{value}</p>
              <p className="text-[10px] text-scanner-text-dim uppercase tracking-wider mt-1">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Users table */}
      {activeTab === 'users' && (
        loadErrors.users ? <SectionError message={loadErrors.users} /> : <div className="bg-scanner-card border border-scanner-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest text-scanner-text-dim border-b border-scanner-border">
                <th className="text-left px-5 py-3">User</th>
                <th className="text-left px-3 py-3">Email</th>
                <th className="text-center px-3 py-3">Role</th>
                <th className="text-center px-3 py-3">Plan</th>
                <th className="text-center px-3 py-3">Status</th>
                <th className="text-right px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-scanner-border/50 hover:bg-scanner-bg/30">
                  <td className="px-5 py-3 font-medium">{u.username}</td>
                  <td className="px-3 py-3 text-scanner-text-dim">{u.email}</td>
                  <td className="px-3 py-3 text-center">
                    <select
                      value={u.role}
                      onChange={(e) => updateUser(u.id, { role: e.target.value })}
                      className="bg-scanner-bg border border-scanner-border rounded px-2 py-1 text-xs"
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <select
                      value={u.plan}
                      onChange={(e) => updateUser(u.id, { plan: e.target.value })}
                      className="bg-scanner-bg border border-scanner-border rounded px-2 py-1 text-xs"
                    >
                      <option value="free">Free</option>
                      <option value="premium">Premium</option>
                    </select>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button
                      onClick={() => updateUser(u.id, { is_active: !u.is_active })}
                      className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${u.is_active ? 'bg-scanner-accent/10 text-scanner-accent' : 'bg-scanner-danger/10 text-scanner-danger'}`}
                    >
                      {u.is_active ? 'Active' : 'Disabled'}
                    </button>
                  </td>
                  <td className="px-5 py-3 text-right text-xs text-scanner-text-dim">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Scan history */}
      {activeTab === 'scans' && (
        loadErrors.scans ? <SectionError message={loadErrors.scans} /> : <div className="bg-scanner-card border border-scanner-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest text-scanner-text-dim border-b border-scanner-border">
                <th className="text-left px-5 py-3">Date</th>
                <th className="text-center px-3 py-3">Market</th>
                <th className="text-center px-3 py-3">Scanned</th>
                <th className="text-center px-3 py-3">Matched</th>
                <th className="text-right px-5 py-3">Duration</th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s) => (
                <tr key={s.id} className="border-b border-scanner-border/50">
                  <td className="px-5 py-3 text-scanner-text-dim">{new Date(s.date).toLocaleString()}</td>
                  <td className="px-3 py-3 text-center uppercase text-xs">{s.market}</td>
                  <td className="px-3 py-3 text-center font-mono">{s.total_scanned}</td>
                  <td className="px-3 py-3 text-center font-mono text-scanner-accent">{s.total_matched}</td>
                  <td className="px-5 py-3 text-right font-mono text-scanner-text-dim">{s.duration}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
