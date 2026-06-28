import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Modal } from "../components/Modal";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

type Tab = "catalog" | "circulation" | "acquisitions" | "performance";
type Book = {
  id: string; title: string; author?: string; isbn?: string; category?: string; publisher?: string;
  shelf?: string; price: string; total_copies: number; available_copies: number;
  issued_copies: number; circulation_count: number; last_issued_on?: string;
};
type Issue = {
  id: string; book: string; student: string; issue_date: string; due_date: string;
  return_date?: string; status: string; fine_amount: string; renew_count: number;
};
type Request = {
  id: string; request_no: string; book_id?: string; title: string; author?: string; isbn?: string;
  quantity: number; estimated_unit_price: string; requested_by_name?: string; request_date?: string;
  priority: string; reason?: string; status: string; decision_notes?: string;
};
type Vendor = { id: string; name: string; code: string; phone?: string; email?: string };
type POLine = {
  id: string; request_id?: string; book_id?: string; title: string; author?: string; isbn?: string;
  quantity: number; received_quantity: number; unit_price: string; line_amount: string;
};
type PO = {
  id: string; po_no: string; vendor: string; vendor_id: string; order_date?: string;
  expected_date?: string; subtotal: string; tax_amount: string; shipping_amount: string;
  total_amount: string; status: string; notes?: string; lines: POLine[];
  receipts: { id: string; grn_no: string; receipt_date: string; accepted_quantity: number; rejected_quantity: number }[];
};
type Performance = {
  summary: Record<string, number | string>;
  popular_books: { id: string; title: string; author?: string; circulations: number; availability: string }[];
  categories: { category: string; titles: number; copies: number; circulations: number }[];
  never_borrowed: { id: string; title: string; author?: string }[];
  open_loans_by_book: { book: string; due_date: string; overdue_days: number }[];
};

const blankBook = { title: "", author: "", isbn: "", category: "", publisher: "", shelf: "", price: "", copies: "1" };
const blankRequest = { book_id: "", title: "", author: "", isbn: "", quantity: "1", estimated_unit_price: "", requested_by_name: "", priority: "normal", reason: "" };

export function Library() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("catalog");
  const [modal, setModal] = useState<"book" | "issue" | "request" | "po" | "vendor" | null>(null);
  const [error, setError] = useState("");
  const [bookForm, setBookForm] = useState({ ...blankBook });
  const [requestForm, setRequestForm] = useState({ ...blankRequest });
  const [bookId, setBookId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [vendorForm, setVendorForm] = useState({ name: "", contact_person: "", phone: "", email: "", gst_no: "" });
  const [poVendorId, setPoVendorId] = useState("");
  const [poExpectedDate, setPoExpectedDate] = useState("");
  const [poTax, setPoTax] = useState("");
  const [poShipping, setPoShipping] = useState("");
  const [poRequestIds, setPoRequestIds] = useState<string[]>([]);

  const { data: books = [] } = useQuery({ queryKey: ["library-catalog"], queryFn: async () => (await api.get<Book[]>("/library/catalog")).data });
  const { data: issues = [] } = useQuery({ queryKey: ["library-issues"], queryFn: async () => (await api.get<Issue[]>("/library/issues")).data });
  const { data: requests = [] } = useQuery({ queryKey: ["library-requests"], queryFn: async () => (await api.get<Request[]>("/library/acquisition-requests")).data });
  const { data: purchaseOrders = [] } = useQuery({ queryKey: ["library-pos"], queryFn: async () => (await api.get<PO[]>("/library/purchase-orders")).data });
  const { data: vendors = [] } = useQuery({ queryKey: ["library-vendors"], queryFn: async () => (await api.get<Vendor[]>("/library/vendors")).data });
  const { data: performance } = useQuery({ queryKey: ["library-performance"], queryFn: async () => (await api.get<Performance>("/library/performance")).data });
  const { data: students } = useQuery({ queryKey: ["students-pick"], queryFn: async () => (await api.get<Page<any>>("/students", { params: { page_size: 200 } })).data });

  const approvedRequests = requests.filter((r) => r.status === "approved");
  const selectedRequests = useMemo(() => approvedRequests.filter((r) => poRequestIds.includes(r.id)), [approvedRequests, poRequestIds]);
  const poSubtotal = selectedRequests.reduce((sum, r) => sum + Number(r.estimated_unit_price) * r.quantity, 0);

  function refresh() {
    for (const key of ["library-catalog", "library-issues", "library-requests", "library-pos", "library-vendors", "library-performance"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
  }
  function fail(e: unknown) { setError(apiError(e)); }
  function close() { setModal(null); setError(""); }

  const createBook = useMutation({
    mutationFn: () => api.post("/library-book", {
      title: bookForm.title, author: bookForm.author || null, isbn: bookForm.isbn || null,
      category: bookForm.category || null, publisher: bookForm.publisher || null,
      shelf: bookForm.shelf || null, price: Number(bookForm.price || 0),
      total_copies: Number(bookForm.copies), available_copies: Number(bookForm.copies),
    }),
    onSuccess: () => { setBookForm({ ...blankBook }); close(); refresh(); }, onError: fail,
  });
  const issueBook = useMutation({
    mutationFn: () => api.post("/library/issues", { book_id: bookId, student_id: studentId, days: 14 }),
    onSuccess: () => { setBookId(""); setStudentId(""); close(); refresh(); }, onError: fail,
  });
  const issueAction = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.post(action === "return" ? `/library/issues/${id}/return` : `/library/issues/${id}/${action}`, action === "renew" ? { days: 14 } : {}),
    onSuccess: refresh, onError: (e) => alert(apiError(e)),
  });
  const createRequest = useMutation({
    mutationFn: () => api.post("/library/acquisition-requests", {
      ...requestForm, book_id: requestForm.book_id || null, quantity: Number(requestForm.quantity),
      estimated_unit_price: Number(requestForm.estimated_unit_price || 0),
    }),
    onSuccess: () => { setRequestForm({ ...blankRequest }); close(); refresh(); }, onError: fail,
  });
  const requestDecision = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: string }) => api.post(`/library/acquisition-requests/${id}/decision`, { decision }),
    onSuccess: refresh, onError: (e) => alert(apiError(e)),
  });
  const createVendor = useMutation({
    mutationFn: () => api.post("/library/vendors", vendorForm),
    onSuccess: ({ data }) => { setPoVendorId(data.id); setVendorForm({ name: "", contact_person: "", phone: "", email: "", gst_no: "" }); setModal("po"); refresh(); },
    onError: fail,
  });
  const createPO = useMutation({
    mutationFn: () => api.post("/library/purchase-orders", {
      vendor_id: poVendorId, expected_date: poExpectedDate || null,
      tax_amount: Number(poTax || 0), shipping_amount: Number(poShipping || 0),
      lines: selectedRequests.map((r) => ({
        acquisition_request_id: r.id, book_id: r.book_id || null, title: r.title,
        author: r.author || null, isbn: r.isbn || null, quantity: r.quantity,
        unit_price: Number(r.estimated_unit_price),
      })),
    }),
    onSuccess: () => { setPoRequestIds([]); setPoVendorId(""); setPoExpectedDate(""); setPoTax(""); setPoShipping(""); close(); refresh(); },
    onError: fail,
  });
  const poAction = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => api.post(`/library/purchase-orders/${id}/action`, { action }),
    onSuccess: refresh, onError: (e) => alert(apiError(e)),
  });
  const receivePO = useMutation({
    mutationFn: ({ po, invoice }: { po: PO; invoice: string | null }) => api.post(`/library/purchase-orders/${po.id}/receipts`, {
      vendor_invoice_no: invoice,
      lines: po.lines.filter((line) => line.received_quantity < line.quantity).map((line) => ({
        purchase_order_line_id: line.id,
        accepted_quantity: line.quantity - line.received_quantity,
        rejected_quantity: 0,
      })),
    }),
    onSuccess: refresh, onError: (e) => alert(apiError(e)),
  });

  function requestCopies(book: Book) {
    setRequestForm({ ...blankRequest, book_id: book.id, title: book.title, author: book.author || "", isbn: book.isbn || "", estimated_unit_price: book.price });
    setModal("request");
  }

  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-semibold">Library Management</h1><p className="text-sm text-slate-400">Catalog, circulation, acquisition, purchase orders, receiving and performance.</p></div>
      <div className="flex flex-wrap gap-2">
        {tab === "catalog" && <button className="btn-primary" onClick={() => setModal("book")}>+ Add Book Title</button>}
        {tab === "circulation" && <button className="btn-primary" onClick={() => setModal("issue")}>+ Issue Book</button>}
        {tab === "acquisitions" && <>
          <button className="btn-ghost border border-slate-200" onClick={() => setModal("request")}>+ Purchase Request</button>
          <button className="btn-primary" disabled={approvedRequests.length === 0} onClick={() => setModal("po")}>Create Purchase Order</button>
        </>}
      </div>
    </div>

    <div className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1">
      {([
        ["catalog", "Book Catalog"], ["circulation", "Circulation"], ["acquisitions", "Purchasing"], ["performance", "Performance"],
      ] as [Tab, string][]).map(([key, label]) => <button key={key} onClick={() => setTab(key)} className={`rounded-lg px-4 py-2 text-sm ${tab === key ? "bg-brand-600 font-medium text-white" : "text-slate-600 hover:bg-slate-50"}`}>{label}</button>)}
    </div>

    {tab === "catalog" && <Catalog books={books} onRequest={requestCopies} />}
    {tab === "circulation" && <Circulation issues={issues} onAction={(id, action) => issueAction.mutate({ id, action })} />}
    {tab === "acquisitions" && <Acquisitions requests={requests} pos={purchaseOrders} onDecision={(id, decision) => requestDecision.mutate({ id, decision })} onPOAction={(id, action) => poAction.mutate({ id, action })} onReceive={(po) => receivePO.mutate({ po, invoice: prompt("Vendor invoice number (optional)") })} />}
    {tab === "performance" && <PerformanceView data={performance} />}

    {modal === "book" && <Modal wide title="Add Book to Catalog" onClose={close}><FormError error={error} /><div className="grid grid-cols-2 gap-3"><F label="Title *" value={bookForm.title} set={(v) => setBookForm({ ...bookForm, title: v })} /><F label="Author" value={bookForm.author} set={(v) => setBookForm({ ...bookForm, author: v })} /><F label="ISBN" value={bookForm.isbn} set={(v) => setBookForm({ ...bookForm, isbn: v })} /><F label="Category" value={bookForm.category} set={(v) => setBookForm({ ...bookForm, category: v })} /><F label="Publisher" value={bookForm.publisher} set={(v) => setBookForm({ ...bookForm, publisher: v })} /><F label="Shelf / Location" value={bookForm.shelf} set={(v) => setBookForm({ ...bookForm, shelf: v })} /><F label="Unit Price" type="number" value={bookForm.price} set={(v) => setBookForm({ ...bookForm, price: v })} /><F label="Opening Copies *" type="number" value={bookForm.copies} set={(v) => setBookForm({ ...bookForm, copies: v })} /></div><ModalActions close={close} disabled={!bookForm.title || !Number(bookForm.copies)} busy={createBook.isPending} action={() => createBook.mutate()} label="Add to Catalog" /></Modal>}

    {modal === "issue" && <Modal title="Issue a Book" onClose={close}><FormError error={error} /><label><span className="label">Available Book</span><select className="input" value={bookId} onChange={(e) => setBookId(e.target.value)}><option value="">— select —</option>{books.filter((b) => b.available_copies > 0).map((b) => <option key={b.id} value={b.id}>{b.title} ({b.available_copies} available)</option>)}</select></label><label className="mt-3 block"><span className="label">Student</span><select className="input" value={studentId} onChange={(e) => setStudentId(e.target.value)}><option value="">— select —</option>{students?.items.map((s: any) => <option key={s.id} value={s.id}>{s.first_name} {s.last_name || ""} · {s.admission_no}</option>)}</select></label><ModalActions close={close} disabled={!bookId || !studentId} busy={issueBook.isPending} action={() => issueBook.mutate()} label="Issue for 14 Days" /></Modal>}

    {modal === "request" && <Modal wide title="New Book Purchase Request" onClose={close}><FormError error={error} /><div className="grid grid-cols-2 gap-3"><label><span className="label">Existing Catalog Title</span><select className="input" value={requestForm.book_id} onChange={(e) => { const b = books.find((x) => x.id === e.target.value); setRequestForm({ ...requestForm, book_id: e.target.value, title: b?.title || "", author: b?.author || "", isbn: b?.isbn || "", estimated_unit_price: b?.price || "" }); }}><option value="">New title / select</option>{books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}</select></label><F label="Title *" value={requestForm.title} set={(v) => setRequestForm({ ...requestForm, title: v })} /><F label="Author" value={requestForm.author} set={(v) => setRequestForm({ ...requestForm, author: v })} /><F label="ISBN" value={requestForm.isbn} set={(v) => setRequestForm({ ...requestForm, isbn: v })} /><F label="Quantity *" type="number" value={requestForm.quantity} set={(v) => setRequestForm({ ...requestForm, quantity: v })} /><F label="Estimated Unit Price" type="number" value={requestForm.estimated_unit_price} set={(v) => setRequestForm({ ...requestForm, estimated_unit_price: v })} /><F label="Requested By" value={requestForm.requested_by_name} set={(v) => setRequestForm({ ...requestForm, requested_by_name: v })} /><label><span className="label">Priority</span><select className="input" value={requestForm.priority} onChange={(e) => setRequestForm({ ...requestForm, priority: e.target.value })}><option>low</option><option>normal</option><option>high</option><option>urgent</option></select></label><div className="col-span-2"><F label="Business Reason" value={requestForm.reason} set={(v) => setRequestForm({ ...requestForm, reason: v })} /></div></div><ModalActions close={close} disabled={!requestForm.title || !Number(requestForm.quantity)} busy={createRequest.isPending} action={() => createRequest.mutate()} label="Submit Request" /></Modal>}

    {modal === "po" && <Modal wide title="Create Library Purchase Order" onClose={close}><FormError error={error} /><div className="mb-4 grid grid-cols-2 gap-3"><label><span className="label">Vendor *</span><div className="flex gap-2"><select className="input" value={poVendorId} onChange={(e) => setPoVendorId(e.target.value)}><option value="">— select —</option>{vendors.map((v) => <option key={v.id} value={v.id}>{v.name} · {v.code}</option>)}</select><button className="btn-ghost whitespace-nowrap border" onClick={() => setModal("vendor")}>+ Vendor</button></div></label><F label="Expected Delivery" type="date" value={poExpectedDate} set={setPoExpectedDate} /><F label="Tax Amount" type="number" value={poTax} set={setPoTax} /><F label="Shipping Amount" type="number" value={poShipping} set={setPoShipping} /></div><div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Approved requests to include</div><div className="max-h-64 divide-y overflow-y-auto rounded-lg border">{approvedRequests.map((r) => <label key={r.id} className="flex items-center gap-3 p-3 text-sm"><input type="checkbox" checked={poRequestIds.includes(r.id)} onChange={(e) => setPoRequestIds(e.target.checked ? [...poRequestIds, r.id] : poRequestIds.filter((id) => id !== r.id))} /><div className="flex-1"><div className="font-medium">{r.title}</div><div className="text-xs text-slate-400">{r.request_no} · {r.quantity} × ₹{Number(r.estimated_unit_price).toLocaleString("en-IN")}</div></div></label>)}</div><div className="mt-3 text-right text-sm font-semibold">PO total: ₹{(poSubtotal + Number(poTax || 0) + Number(poShipping || 0)).toLocaleString("en-IN")}</div><ModalActions close={close} disabled={!poVendorId || poRequestIds.length === 0} busy={createPO.isPending} action={() => createPO.mutate()} label="Create Draft PO" /></Modal>}

    {modal === "vendor" && <Modal title="Add Book Vendor" onClose={() => setModal("po")}><FormError error={error} /><div className="space-y-3"><F label="Vendor Name *" value={vendorForm.name} set={(v) => setVendorForm({ ...vendorForm, name: v })} /><F label="Contact Person" value={vendorForm.contact_person} set={(v) => setVendorForm({ ...vendorForm, contact_person: v })} /><F label="Phone" value={vendorForm.phone} set={(v) => setVendorForm({ ...vendorForm, phone: v })} /><F label="Email" type="email" value={vendorForm.email} set={(v) => setVendorForm({ ...vendorForm, email: v })} /><F label="GST Number" value={vendorForm.gst_no} set={(v) => setVendorForm({ ...vendorForm, gst_no: v })} /></div><ModalActions close={() => setModal("po")} disabled={!vendorForm.name} busy={createVendor.isPending} action={() => createVendor.mutate()} label="Save Vendor" /></Modal>}
  </div>;
}

function Catalog({ books, onRequest }: { books: Book[]; onRequest: (book: Book) => void }) {
  return <div className="card overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><Th>Title / ISBN</Th><Th>Category</Th><Th>Shelf</Th><Th>Copies</Th><Th>Circulation</Th><Th>Value</Th><Th /></tr></thead><tbody className="divide-y">{books.map((b) => <tr key={b.id}><Td><div className="font-medium">{b.title}</div><div className="text-xs text-slate-400">{b.author || "Unknown author"} · {b.isbn || "No ISBN"}</div></Td><Td>{b.category || "—"}</Td><Td>{b.shelf || "—"}</Td><Td><div className="font-medium">{b.available_copies}/{b.total_copies} available</div><div className="text-xs text-slate-400">{b.issued_copies} on loan</div></Td><Td>{b.circulation_count}</Td><Td>₹{(Number(b.price) * b.total_copies).toLocaleString("en-IN")}</Td><Td><button className="btn-ghost px-2 py-1 text-xs" onClick={() => onRequest(b)}>Request Copies</button></Td></tr>)}{books.length === 0 && <Empty colSpan={7}>No catalog titles. Add the first book.</Empty>}</tbody></table></div>;
}

function Circulation({ issues, onAction }: { issues: Issue[]; onAction: (id: string, action: string) => void }) {
  return <div className="card overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><Th>Book</Th><Th>Borrower</Th><Th>Issued</Th><Th>Due</Th><Th>Status</Th><Th>Fine / Charge</Th><Th /></tr></thead><tbody className="divide-y">{issues.map((i) => <tr key={i.id}><Td><div className="font-medium">{i.book}</div><div className="text-xs text-slate-400">{i.renew_count} renewal(s)</div></Td><Td>{i.student}</Td><Td>{i.issue_date}</Td><Td>{i.due_date}</Td><Td><Pill value={i.status} /></Td><Td>₹{Number(i.fine_amount).toLocaleString("en-IN")}</Td><Td><div className="flex justify-end gap-1">{i.status === "issued" && <button className="btn-ghost px-2 py-1 text-xs" onClick={() => onAction(i.id, "renew")}>Renew</button>}{["issued", "overdue"].includes(i.status) && <><button className="btn-primary px-2 py-1 text-xs" onClick={() => onAction(i.id, "return")}>Return</button><button className="btn-danger px-2 py-1 text-xs" onClick={() => onAction(i.id, "lost")}>Lost</button></>}</div></Td></tr>)}{issues.length === 0 && <Empty colSpan={7}>No circulation transactions.</Empty>}</tbody></table></div>;
}

function Acquisitions({ requests, pos, onDecision, onPOAction, onReceive }: { requests: Request[]; pos: PO[]; onDecision: (id: string, decision: string) => void; onPOAction: (id: string, action: string) => void; onReceive: (po: PO) => void }) {
  return <div className="space-y-5"><section className="card overflow-x-auto"><div className="border-b px-4 py-3 font-semibold">Acquisition Requests</div><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><Th>Request</Th><Th>Book</Th><Th>Qty</Th><Th>Estimate</Th><Th>Priority</Th><Th>Status</Th><Th /></tr></thead><tbody className="divide-y">{requests.map((r) => <tr key={r.id}><Td><div className="font-medium">{r.request_no}</div><div className="text-xs text-slate-400">{r.requested_by_name || "Library"}</div></Td><Td><div>{r.title}</div><div className="text-xs text-slate-400">{r.author || r.isbn || "—"}</div></Td><Td>{r.quantity}</Td><Td>₹{(Number(r.estimated_unit_price) * r.quantity).toLocaleString("en-IN")}</Td><Td><Pill value={r.priority} /></Td><Td><Pill value={r.status} /></Td><Td>{r.status === "pending" && <div className="flex justify-end gap-1"><button className="btn-ghost px-2 py-1 text-xs text-emerald-700" onClick={() => onDecision(r.id, "approved")}>Approve</button><button className="btn-danger px-2 py-1 text-xs" onClick={() => onDecision(r.id, "rejected")}>Reject</button></div>}</Td></tr>)}{requests.length === 0 && <Empty colSpan={7}>No purchase requests.</Empty>}</tbody></table></section><section className="space-y-3"><h2 className="font-semibold">Purchase Orders</h2>{pos.map((po) => <div key={po.id} className="card p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-xs text-slate-400">{po.po_no}</div><div className="font-semibold">{po.vendor}</div><div className="text-xs text-slate-400">Ordered {po.order_date || "—"} · Expected {po.expected_date || "—"}</div></div><div className="flex items-center gap-2"><Pill value={po.status} /><span className="font-semibold">₹{Number(po.total_amount).toLocaleString("en-IN")}</span></div></div><div className="mt-3 divide-y rounded-lg border">{po.lines.map((line) => <div key={line.id} className="flex justify-between p-3 text-sm"><div>{line.title}<div className="text-xs text-slate-400">{line.received_quantity}/{line.quantity} received</div></div><div>₹{Number(line.line_amount).toLocaleString("en-IN")}</div></div>)}</div><div className="mt-3 flex flex-wrap justify-between gap-2"><div className="text-xs text-slate-400">{po.receipts.map((r) => `${r.grn_no}: ${r.accepted_quantity} accepted`).join(" · ")}</div><div className="flex gap-2">{po.status === "draft" && <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => onPOAction(po.id, "approve")}>Approve PO</button>}{po.status === "approved" && <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => onPOAction(po.id, "order")}>Send to Vendor</button>}{["ordered", "partially_received"].includes(po.status) && <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => onReceive(po)}>Receive Books</button>}{!["received", "cancelled"].includes(po.status) && <button className="btn-danger px-3 py-1.5 text-xs" onClick={() => onPOAction(po.id, "cancel")}>Cancel</button>}</div></div></div>)}{pos.length === 0 && <div className="card p-8 text-center text-sm text-slate-400">No library purchase orders.</div>}</section></div>;
}

function PerformanceView({ data }: { data?: Performance }) {
  if (!data) return <div className="text-sm text-slate-400">Loading performance…</div>;
  const metrics = [["titles", "Titles"], ["total_copies", "Total Copies"], ["on_loan", "On Loan"], ["overdue", "Overdue"], ["total_circulations", "Total Circulations"], ["catalog_value", "Catalog Value"]];
  return <div className="space-y-5"><div className="grid grid-cols-2 gap-3 md:grid-cols-6">{metrics.map(([key, label]) => <div key={key} className="card p-4"><div className="text-2xl font-semibold">{key === "catalog_value" ? `₹${Number(data.summary[key]).toLocaleString("en-IN")}` : data.summary[key]}</div><div className="text-xs text-slate-400">{label}</div></div>)}</div><div className="grid gap-5 lg:grid-cols-2"><section className="card overflow-hidden"><div className="border-b px-4 py-3 font-semibold">Most Circulated Books</div><div className="divide-y">{data.popular_books.map((b) => <div key={b.id} className="flex justify-between p-4 text-sm"><div><div className="font-medium">{b.title}</div><div className="text-xs text-slate-400">{b.author || "Unknown author"} · {b.availability} available</div></div><div className="text-lg font-semibold">{b.circulations}</div></div>)}</div></section><section className="card overflow-hidden"><div className="border-b px-4 py-3 font-semibold">Category Performance</div><div className="divide-y">{data.categories.map((c) => <div key={c.category} className="grid grid-cols-4 p-4 text-sm"><div className="font-medium">{c.category}</div><div>{c.titles} titles</div><div>{c.copies} copies</div><div>{c.circulations} issues</div></div>)}</div></section></div></div>;
}

function F({ label, value, set, type = "text" }: { label: string; value: string; set: (v: string) => void; type?: string }) { return <label><span className="label">{label}</span><input className="input" type={type} value={value} onChange={(e) => set(e.target.value)} /></label>; }
function FormError({ error }: { error: string }) { return error ? <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div> : null; }
function ModalActions({ close, disabled, busy, action, label }: { close: () => void; disabled: boolean; busy: boolean; action: () => void; label: string }) { return <div className="mt-5 flex justify-end gap-2"><button className="btn-ghost" onClick={close}>Cancel</button><button className="btn-primary" disabled={disabled || busy} onClick={action}>{busy ? "Saving…" : label}</button></div>; }
function Th({ children }: { children?: React.ReactNode }) { return <th className="px-4 py-3">{children}</th>; }
function Td({ children }: { children?: React.ReactNode }) { return <td className="px-4 py-3">{children}</td>; }
function Empty({ colSpan, children }: { colSpan: number; children: React.ReactNode }) { return <tr><td colSpan={colSpan} className="px-4 py-8 text-center text-slate-400">{children}</td></tr>; }
function Pill({ value }: { value: string }) { const green = ["approved", "ordered", "received", "returned", "fulfilled", "normal"].includes(value); const red = ["rejected", "cancelled", "lost", "urgent", "overdue"].includes(value); return <span className={`badge capitalize ${green ? "bg-emerald-50 text-emerald-700" : red ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>{value.replace(/_/g, " ")}</span>; }
