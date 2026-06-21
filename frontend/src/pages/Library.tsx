import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { Modal } from "../components/Modal";
import type { Page } from "../lib/types";

interface Issue {
  id: string;
  book: string;
  student: string;
  issue_date: string;
  due_date: string;
  return_date?: string | null;
  status: string;
  fine_amount: string;
}

export function Library() {
  const qc = useQueryClient();
  const [issuing, setIssuing] = useState(false);
  const [bookId, setBookId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: issues = [] } = useQuery({
    queryKey: ["library-issues"],
    queryFn: async () => (await api.get<Issue[]>("/library/issues")).data,
  });
  const { data: books } = useQuery({
    queryKey: ["library-books-pick"],
    queryFn: async () => (await api.get<Page<any>>("/library-book", { params: { page_size: 200 } })).data,
  });
  const { data: students } = useQuery({
    queryKey: ["students-pick"],
    queryFn: async () => (await api.get<Page<any>>("/students", { params: { page_size: 200 } })).data,
  });

  const issue = useMutation({
    mutationFn: async () =>
      api.post("/library/issues", { book_id: bookId, student_id: studentId, days: 14 }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library-issues"] });
      setIssuing(false);
      setBookId("");
      setStudentId("");
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  const returnBook = useMutation({
    mutationFn: async (id: string) => api.post(`/library/issues/${id}/return`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library-issues"] }),
    onError: (e) => alert(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Library Circulation</h1>
          <p className="text-sm text-slate-400">Issue &amp; return books — overdue fines calculated automatically.</p>
        </div>
        <button className="btn-primary" onClick={() => setIssuing(true)}>
          + Issue Book
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Book</th>
              <th className="px-4 py-3">Student</th>
              <th className="px-4 py-3">Issued</th>
              <th className="px-4 py-3">Due</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Fine</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {issues.map((i) => (
              <tr key={i.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{i.book}</td>
                <td className="px-4 py-3">{i.student}</td>
                <td className="px-4 py-3">{i.issue_date}</td>
                <td className="px-4 py-3">{i.due_date}</td>
                <td className="px-4 py-3">
                  <span
                    className={`badge ${
                      i.status === "returned"
                        ? "bg-emerald-50 text-emerald-600"
                        : "bg-amber-50 text-amber-600"
                    }`}
                  >
                    {i.status}
                  </span>
                </td>
                <td className="px-4 py-3">₹{i.fine_amount}</td>
                <td className="px-4 py-3 text-right">
                  {i.status !== "returned" && (
                    <button
                      className="btn-primary px-2.5 py-1 text-xs"
                      onClick={() => returnBook.mutate(i.id)}
                    >
                      Return
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {issues.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  No books issued yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {issuing && (
        <Modal title="Issue a Book" onClose={() => setIssuing(false)}>
          <div className="space-y-4">
            <div>
              <label className="label">Book</label>
              <select className="input" value={bookId} onChange={(e) => setBookId(e.target.value)}>
                <option value="">— select —</option>
                {books?.items
                  ?.filter((b: any) => b.available_copies > 0)
                  .map((b: any) => (
                    <option key={b.id} value={b.id}>
                      {b.title} ({b.available_copies} avail)
                    </option>
                  ))}
              </select>
            </div>
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
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setIssuing(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!bookId || !studentId || issue.isPending}
                onClick={() => issue.mutate()}
              >
                Issue (14 days)
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
