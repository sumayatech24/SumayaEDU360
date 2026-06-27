import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";

interface Doc {
  id: string;
  name: string;
  category?: string | null;
  url?: string | null;
  mime_type?: string | null;
}

/** Upload / list / view / delete documents attached to a student or employee. */
export function DocumentUpload({ ownerType, ownerId }: { ownerType: string; ownerId: string }) {
  const qc = useQueryClient();
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);
  const key = ["documents", ownerType, ownerId];

  const { data: docs = [] } = useQuery({
    queryKey: key,
    queryFn: async () =>
      (await api.get<Doc[]>("/documents", { params: { owner_type: ownerType, owner_id: ownerId } })).data,
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const dataUrl: string = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(String(r.result));
        r.onerror = rej;
        r.readAsDataURL(file);
      });
      return api.post("/documents", {
        owner_type: ownerType,
        owner_id: ownerId,
        name: file.name,
        category: category || "General",
        url: dataUrl,
        mime_type: file.type,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: key });
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  const remove = useMutation({
    mutationFn: async (id: string) => api.delete(`/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  function onFile(file?: File) {
    if (!file) return;
    if (file.size > 1_500_000) {
      setError("File must be under 1.5 MB.");
      return;
    }
    upload.mutate(file);
  }

  function view(d: Doc) {
    if (!d.url) return;
    const w = window.open();
    if (w) w.document.write(`<iframe src="${d.url}" style="border:0;width:100%;height:100%"></iframe>`);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="label">Category</label>
          <select className="input w-44" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">General</option>
            <option>Birth Certificate</option>
            <option>Transfer Certificate</option>
            <option>Photo</option>
            <option>ID Proof</option>
            <option>Report Card</option>
            <option>Resume / CV</option>
            <option>Qualification</option>
          </select>
        </div>
        <label className="btn-primary cursor-pointer text-sm">
          {upload.isPending ? "Uploading…" : "+ Upload"}
          <input
            type="file"
            className="hidden"
            accept="image/*,application/pdf"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
        </label>
      </div>
      {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

      <div className="divide-y divide-slate-100">
        {docs.map((d) => (
          <div key={d.id} className="flex items-center justify-between py-2 text-sm">
            <div>
              <span className="font-medium">{d.name}</span>
              <span className="ml-2 text-[11px] text-slate-400">{d.category}</span>
            </div>
            <div className="flex gap-1">
              <button className="btn-ghost px-2 py-1 text-xs text-brand-600" onClick={() => view(d)}>
                View
              </button>
              <button className="btn-danger px-2 py-1 text-xs" onClick={() => remove.mutate(d.id)}>
                Delete
              </button>
            </div>
          </div>
        ))}
        {docs.length === 0 && <p className="py-2 text-sm text-slate-400">No documents uploaded.</p>}
      </div>
    </div>
  );
}
