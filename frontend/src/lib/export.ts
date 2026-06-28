// Dependency-free table export helpers (CSV, Excel, PDF) shared by all data tables.
import { openReport, reportDocument, type ReportBrand } from "./report";

export interface ExportColumn {
  key: string;
  label: string;
}

export type ExportRow = Record<string, string>;

function slug(name: string): string {
  const stamp = new Date().toISOString().slice(0, 10);
  const base = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "export";
  return `${base}-${stamp}`;
}

function triggerDownload(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function escapeHtml(value: string): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function csvField(value: string): string {
  const s = value ?? "";
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Comma-separated values, UTF-8 BOM so Excel renders accents correctly. */
export function exportCsv(name: string, columns: ExportColumn[], rows: ExportRow[]) {
  const header = columns.map((c) => csvField(c.label)).join(",");
  const body = rows.map((r) => columns.map((c) => csvField(r[c.key] ?? "")).join(",")).join("\r\n");
  triggerDownload(`${slug(name)}.csv`, "﻿" + header + "\r\n" + body, "text/csv;charset=utf-8");
}

/** A SpreadsheetML/HTML table workbook — opens natively in Excel as .xls. */
export function exportExcel(name: string, columns: ExportColumn[], rows: ExportRow[]) {
  const head = `<tr>${columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("")}</tr>`;
  const body = rows
    .map((r) => `<tr>${columns.map((c) => `<td>${escapeHtml(r[c.key] ?? "")}</td>`).join("")}</tr>`)
    .join("");
  const html =
    `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">` +
    `<head><meta charset="utf-8"><!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet>` +
    `<x:Name>${escapeHtml(name).slice(0, 31)}</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions>` +
    `</x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->` +
    `<style>th{background:#f1f5f9;text-align:left}td,th{border:1px solid #cbd5e1;padding:4px 8px;font-family:Calibri,sans-serif;font-size:11pt}</style>` +
    `</head><body><table>${head}${body}</table></body></html>`;
  triggerDownload(`${slug(name)}.xls`, html, "application/vnd.ms-excel");
}

/** Open a branded, print-ready report; the user saves as PDF via the print dialog. */
export function exportPdf(name: string, columns: ExportColumn[], rows: ExportRow[], brand: ReportBrand) {
  const head = `<tr>${columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("")}</tr>`;
  const body = rows.length
    ? rows.map((r) => `<tr>${columns.map((c) => `<td>${escapeHtml(r[c.key] ?? "")}</td>`).join("")}</tr>`).join("")
    : `<tr><td colspan="${columns.length}" style="text-align:center;color:#94a3b8">No records.</td></tr>`;
  const html = reportDocument({
    brand,
    title: name,
    meta: `${rows.length} record${rows.length === 1 ? "" : "s"} · generated ${new Date().toLocaleString()}`,
    landscape: true,
    bodyHtml: `<table><thead>${head}</thead><tbody>${body}</tbody></table>`,
  });
  openReport(html);
}
