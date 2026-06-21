import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { Modal } from "../components/Modal";
import type { Page } from "../lib/types";

interface Alloc {
  id: string;
  student: string;
  room: string;
  block: string;
  allocation_date: string;
  status: string;
}

export function Hostel() {
  const qc = useQueryClient();
  const [allocating, setAllocating] = useState(false);
  const [roomId, setRoomId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: rooms } = useQuery({
    queryKey: ["hostel-rooms"],
    queryFn: async () => (await api.get<Page<any>>("/hostel-room", { params: { page_size: 200 } })).data,
  });
  const { data: students } = useQuery({
    queryKey: ["students-pick"],
    queryFn: async () => (await api.get<Page<any>>("/students", { params: { page_size: 200 } })).data,
  });
  const { data: allocs = [] } = useQuery({
    queryKey: ["hostel-allocs"],
    queryFn: async () => (await api.get<Alloc[]>("/hostel/allocations")).data,
  });

  const allocate = useMutation({
    mutationFn: async () => api.post("/hostel/allocations", { room_id: roomId, student_id: studentId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hostel-allocs"] });
      qc.invalidateQueries({ queryKey: ["hostel-rooms"] });
      setAllocating(false);
      setRoomId("");
      setStudentId("");
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });
  const vacate = useMutation({
    mutationFn: async (id: string) => api.post(`/hostel/allocations/${id}/vacate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hostel-allocs"] });
      qc.invalidateQueries({ queryKey: ["hostel-rooms"] });
    },
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Hostel</h1>
          <p className="text-sm text-slate-400">Room occupancy and student allocation.</p>
        </div>
        <button className="btn-primary" onClick={() => setAllocating(true)}>
          + Allocate Room
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {rooms?.items?.map((r: any) => {
          const full = r.occupied >= r.capacity;
          return (
            <div key={r.id} className="card p-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold">Room {r.room_no}</span>
                <span className={`badge ${full ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-600"}`}>
                  {r.occupied}/{r.capacity}
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-400">{r.room_type ?? "room"}</div>
            </div>
          );
        })}
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-600">
          Allocations
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Student</th>
              <th className="px-4 py-3">Block</th>
              <th className="px-4 py-3">Room</th>
              <th className="px-4 py-3">Since</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {allocs.map((a) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{a.student}</td>
                <td className="px-4 py-3">{a.block}</td>
                <td className="px-4 py-3">{a.room}</td>
                <td className="px-4 py-3">{a.allocation_date}</td>
                <td className="px-4 py-3">
                  <span
                    className={`badge ${
                      a.status === "allocated" ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {a.status === "allocated" && (
                    <button className="btn-danger px-2.5 py-1 text-xs" onClick={() => vacate.mutate(a.id)}>
                      Vacate
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {allocs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                  No allocations yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {allocating && (
        <Modal title="Allocate Room" onClose={() => setAllocating(false)}>
          <div className="space-y-4">
            <div>
              <label className="label">Student</label>
              <select className="input" value={studentId} onChange={(e) => setStudentId(e.target.value)}>
                <option value="">— select —</option>
                {students?.items?.map((s: any) => (
                  <option key={s.id} value={s.id}>
                    {s.first_name} {s.last_name} · {s.admission_no}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Room</label>
              <select className="input" value={roomId} onChange={(e) => setRoomId(e.target.value)}>
                <option value="">— select —</option>
                {rooms?.items
                  ?.filter((r: any) => r.occupied < r.capacity)
                  .map((r: any) => (
                    <option key={r.id} value={r.id}>
                      Room {r.room_no} ({r.occupied}/{r.capacity})
                    </option>
                  ))}
              </select>
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setAllocating(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!roomId || !studentId || allocate.isPending}
                onClick={() => allocate.mutate()}
              >
                Allocate
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
