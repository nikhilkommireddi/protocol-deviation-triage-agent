import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2, UserPlus } from "lucide-react";
import { createUser, deleteUser, listSites, listUsers, updateUser } from "../../api";
import type { ManagedSite, ManagedUser, UserRole } from "../../types";
import { ROLE_INFO } from "../../lib/permissions";

const ROLE_OPTIONS = ROLE_INFO.map((r) => ({ value: r.role, label: r.title }));

interface UserFormState {
  name: string;
  role: UserRole;
  site_id: string;
}

const EMPTY_FORM: UserFormState = { name: "", role: "site_coordinator", site_id: "" };

export function UsersPanel() {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [sites, setSites] = useState<ManagedSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState<UserFormState>(EMPTY_FORM);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<UserFormState>(EMPTY_FORM);

  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [u, s] = await Promise.all([listUsers(), listSites()]);
      setUsers(u);
      setSites(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleAdd() {
    setError(null);
    try {
      await createUser({
        name: addForm.name,
        role: addForm.role,
        site_id: addForm.role === "site_coordinator" ? addForm.site_id || null : null,
      });
      setShowAddForm(false);
      setAddForm(EMPTY_FORM);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user.");
    }
  }

  function startEdit(user: ManagedUser) {
    setEditingId(user.user_id);
    setEditForm({ name: user.name, role: user.role, site_id: user.site_id ?? "" });
  }

  async function handleSaveEdit(userId: string) {
    setError(null);
    try {
      await updateUser(userId, {
        name: editForm.name,
        role: editForm.role,
        site_id: editForm.role === "site_coordinator" ? editForm.site_id || null : null,
      });
      setEditingId(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user.");
    }
  }

  async function handleDelete(userId: string) {
    setError(null);
    try {
      await deleteUser(userId);
      setConfirmingDeleteId(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete user.");
      setConfirmingDeleteId(null);
    }
  }

  function siteName(siteId: string | null): string {
    if (!siteId) return "-";
    return sites.find((s) => s.site_id === siteId)?.name ?? siteId;
  }

  if (loading) return <p className="text-slate-500">Loading users...</p>;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-slate-800">Users</h3>
        <button
          className="btn-secondary flex items-center gap-2 text-sm"
          onClick={() => setShowAddForm((v) => !v)}
        >
          <UserPlus className="w-4 h-4" />
          Add User
        </button>
      </div>

      {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

      {showAddForm && (
        <div className="border border-slate-200 rounded-md p-3 mb-4 bg-slate-50 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="block text-xs text-slate-500 mb-1">Name</span>
            <input
              className="input"
              value={addForm.name}
              onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
            />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-slate-500 mb-1">Role</span>
            <select
              className="input"
              value={addForm.role}
              onChange={(e) => setAddForm({ ...addForm, role: e.target.value as UserRole })}
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          {addForm.role === "site_coordinator" && (
            <label className="text-sm">
              <span className="block text-xs text-slate-500 mb-1">Site</span>
              <select
                className="input"
                value={addForm.site_id}
                onChange={(e) => setAddForm({ ...addForm, site_id: e.target.value })}
              >
                <option value="">Select a site...</option>
                {sites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.name} ({s.site_id})
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            className="btn-primary flex items-center gap-2 text-sm"
            disabled={!addForm.name || (addForm.role === "site_coordinator" && !addForm.site_id)}
            onClick={handleAdd}
          >
            <Plus className="w-4 h-4" />
            Create
          </button>
          <button className="btn-secondary text-sm" onClick={() => setShowAddForm(false)}>
            Cancel
          </button>
        </div>
      )}

      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-200">
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4">Role</th>
            <th className="py-2 pr-4">Site</th>
            <th className="py-2 pr-4">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.user_id} className="border-b border-slate-100">
              {editingId === u.user_id ? (
                <>
                  <td className="py-2 pr-4">
                    <input
                      className="input"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    />
                  </td>
                  <td className="py-2 pr-4">
                    <select
                      className="input"
                      value={editForm.role}
                      onChange={(e) =>
                        setEditForm({ ...editForm, role: e.target.value as UserRole })
                      }
                    >
                      {ROLE_OPTIONS.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2 pr-4">
                    {editForm.role === "site_coordinator" ? (
                      <select
                        className="input"
                        value={editForm.site_id}
                        onChange={(e) => setEditForm({ ...editForm, site_id: e.target.value })}
                      >
                        <option value="">Select a site...</option>
                        {sites.map((s) => (
                          <option key={s.site_id} value={s.site_id}>
                            {s.name} ({s.site_id})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 flex gap-2">
                    <button className="btn-primary text-xs" onClick={() => handleSaveEdit(u.user_id)}>
                      Save
                    </button>
                    <button className="btn-secondary text-xs" onClick={() => setEditingId(null)}>
                      Cancel
                    </button>
                  </td>
                </>
              ) : (
                <>
                  <td className="py-2 pr-4 text-slate-700">{u.name}</td>
                  <td className="py-2 pr-4 text-slate-600">
                    {ROLE_INFO.find((r) => r.role === u.role)?.title ?? u.role}
                  </td>
                  <td className="py-2 pr-4 text-slate-600">{siteName(u.site_id)}</td>
                  <td className="py-2 pr-4">
                    {confirmingDeleteId === u.user_id ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-red-600">Delete?</span>
                        <button
                          className="btn-danger text-xs"
                          onClick={() => handleDelete(u.user_id)}
                        >
                          Confirm
                        </button>
                        <button
                          className="btn-secondary text-xs"
                          onClick={() => setConfirmingDeleteId(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-3">
                        <button
                          className="text-slate-400 hover:text-slate-700"
                          onClick={() => startEdit(u)}
                          title="Edit"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          className="text-slate-400 hover:text-red-600"
                          onClick={() => setConfirmingDeleteId(u.user_id)}
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
