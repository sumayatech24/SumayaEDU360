interface Mark {
  exam: string;
  subject: string;
  marks: string;
  max: string;
  grade?: string | null;
}

interface StudentInfo {
  name: string;
  admission_no?: string;
  roll_no?: string;
  grade?: string;
  section?: string;
}

function overallGrade(pct: number): string {
  if (pct >= 90) return "A+";
  if (pct >= 80) return "A";
  if (pct >= 70) return "B+";
  if (pct >= 60) return "B";
  if (pct >= 50) return "C";
  if (pct >= 40) return "D";
  return "E";
}

/** Open a printable marksheet (results grouped by exam) in a new window. */
export function printMarksheet(school: string, student: StudentInfo, marks: Mark[]) {
  const w = window.open("", "_blank", "width=760,height=900");
  if (!w) return;

  const byExam = new Map<string, Mark[]>();
  marks.forEach((m) => byExam.set(m.exam, [...(byExam.get(m.exam) ?? []), m]));

  const examBlocks = [...byExam.entries()]
    .map(([exam, rows]) => {
      const totalObt = rows.reduce((s, r) => s + Number(r.marks || 0), 0);
      const totalMax = rows.reduce((s, r) => s + Number(r.max || 0), 0) || 1;
      const pct = Math.round((totalObt / totalMax) * 1000) / 10;
      const body = rows
        .map(
          (r) => `<tr><td>${r.subject}</td><td class="c">${r.marks}</td><td class="c">${r.max}</td><td class="c">${r.grade ?? "—"}</td></tr>`
        )
        .join("");
      return `
        <h3>${exam}</h3>
        <table>
          <thead><tr><th>Subject</th><th class="c">Marks</th><th class="c">Max</th><th class="c">Grade</th></tr></thead>
          <tbody>${body}
            <tr class="tot"><td>Total</td><td class="c">${totalObt}</td><td class="c">${totalMax}</td><td class="c">${pct}% · ${overallGrade(pct)}</td></tr>
          </tbody>
        </table>`;
    })
    .join("");

  w.document.write(`
    <html><head><title>Marksheet — ${student.name}</title>
    <style>
      body{font-family:system-ui,-apple-system,sans-serif;padding:36px;color:#1e293b}
      h1{font-size:20px;margin:0}.muted{color:#64748b;font-size:12px}
      .hdr{border-bottom:2px solid #2563eb;padding-bottom:12px;margin-bottom:16px}
      .grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;font-size:13px;margin:14px 0}
      .grid div span{color:#64748b}
      h3{font-size:14px;margin:20px 0 6px}
      table{width:100%;border-collapse:collapse;font-size:13px}
      th,td{padding:7px 10px;border-bottom:1px solid #e2e8f0;text-align:left}
      th{background:#f8fafc;font-size:11px;text-transform:uppercase;color:#64748b}
      .c{text-align:center}.tot{font-weight:700;background:#f8fafc}
      .sign{margin-top:48px;display:flex;justify-content:space-between;font-size:12px;color:#64748b}
    </style></head>
    <body>
      <div class="hdr"><h1>${school}</h1><div class="muted">Statement of Marks</div></div>
      <div class="grid">
        <div><span>Student:</span> <b>${student.name}</b></div>
        <div><span>Admission No:</span> ${student.admission_no ?? "—"}</div>
        <div><span>Roll No:</span> ${student.roll_no ?? "—"}</div>
        <div><span>Class:</span> ${student.grade ?? "—"} · ${student.section ?? "—"}</div>
      </div>
      ${examBlocks || '<p class="muted">No published results yet.</p>'}
      <div class="sign"><span>Class Teacher</span><span>Principal</span></div>
      <script>window.print()</script>
    </body></html>`);
  w.document.close();
}
