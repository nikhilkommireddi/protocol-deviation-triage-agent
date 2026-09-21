import { useEffect, useState } from "react";
import { MapPinPlus, Pencil, Plus, Trash2 } from "lucide-react";
import { createSite, deleteSite, listSites, updateSite } from "../../api";
import type { ManagedSite, SiteStatus } from "../../types";

interface SiteFormState {
  site_id: string;
  name: string;
  protocol_id: string;
  status: SiteStatus;
}

const EMPTY_FORM: SiteFormState = { site_id: "", name: "", protocol_id: "", status: "active" };

export function SitesPanel() {
  const [sites, setSites] = useState<ManagedSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState<SiteFormState>(EMPTY_FORM);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<SiteFormState>(EMPTY_FORM);

  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setSites(await listSites());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sites.");
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
      await createSite({
        site_id: addForm.site_id,
        name: addForm.name,
        protocol_id: addForm.protocol_id || null,
        status: addForm.status,
      });
      setShowAddForm(false);
      setAddForm(EMPTY_FORM);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create site.");
    }
  }

  function startEdit(site: ManagedSite) {
    setEditingId(site.site_id);
    setEditForm({
      site_id: site.site_id,
      name: site.name,
      protocol_id: site.protocol_id ?? "",
      status: site.status,
    });
  }

  async function handleSaveEdit(siteId: string) {
    setError(null);
    try {
      await updateSite(siteId, {
        name: editForm.name,
        protocol_id: editForm.protocol_id || null,
        status: editForm.status,
      });
      setEditingId(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update site.");
    }
  }

  async function handleDelete(siteId: string) {
    setError(null);
    try {
      await deleteSite(siteId);
      setConfirmingDeleteId(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete site.");
      setConfirmingDeleteId(null);
    }
  }

  if (loading) return <p className="text-slate-500">Loading sites...</p>;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-slate-800">Sites</h3>
        <button
          className="btn-secondary flex items-center gap-2 text-sm"
          onClick={() => setShowAddForm((v) => !v)}
        >
          <MapPinPlus className="w-4 h-4" />
          Add Site
        </button>
      </div>

      {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

      {showAddForm && (
        <div className="border border-slate-200 rounded-md p-3 mb-4 bg-slate-50 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="block text-xs text-slate-500 mb-1">Site ID</span>
            <input
              className="input"
              placeholder="e.g. 042"
              value={addForm.site_id}
              onChange={(e) => setAddForm({ ...addForm, site_id: e.target.value })}
            />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-slate-500 mb-1">Name</span>
            <input
              className="input"
              value={addForm.name}
              onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
            />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-slate-500 mb-1">Protocol ID (optional)</span>
            <input
              className="input"
              value={addForm.protocol_id}
              onChange={(e) => setAddForm({ ...addForm, protocol_id: e.target.value })}
            />
          </label>
          <button
            className="btn-primary flex items-center gap-2 text-sm"
            disabled={!addForm.site_id || !addForm.name}
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
            <th className="py-2 pr-4">Site ID</th>
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4">Protocol</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sites.map((s) => (
            <tr key={s.site_id} className="border-b border-slate-100">
              <td className="py-2 pr-4 font-mono text-xs text-slate-500">{s.site_id}</td>
              {editingId === s.site_id ? (
                <>
                  <td className="py-2 pr-4">
                    <input
                      className="input"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    />
                  </td>
                  <td className="py-2 pr-4">
                    <input
                      className="input"
                      value={editForm.protocol_id}
                      onChange={(e) => setEditForm({ ...editForm, protocol_id: e.target.value })}
                    />
                  </td>
                  <td className="py-2 pr-4">
                    <select
                      className="input"
                      value={editForm.status}
                      onChange={(e) =>
                        setEditForm({ ...editForm, status: e.target.value as SiteStatus })
                      }
                    >
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </td>
                  <td className="py-2 pr-4 flex gap-2">
                    <button className="btn-primary text-xs" onClick={() => handleSaveEdit(s.site_id)}>
                      Save
                    </button>
                    <button className="btn-secondary text-xs" onClick={() => setEditingId(null)}>
                      Cancel
                    </button>
                  </td>
                </>
              ) : (
                <>
                  <td className="py-2 pr-4 text-slate-700">{s.name}</td>
                  <td className="py-2 pr-4 text-slate-600">{s.protocol_id ?? "-"}</td>
                  <td className="py-2 pr-4">
                    <span className={s.status === "active" ? "badge badge-green" : "badge badge-slate"}>
                      {s.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    {confirmingDeleteId === s.site_id ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-red-600">Delete?</span>
                        <button
                          className="btn-danger text-xs"
                          onClick={() => handleDelete(s.site_id)}
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
                          onClick={() => startEdit(s)}
                          title="Edit"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          className="text-slate-400 hover:text-red-600"
                          onClick={() => setConfirmingDeleteId(s.site_id)}
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
