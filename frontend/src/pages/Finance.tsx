import { Workbench } from "../components/Workbench";
import { api } from "../lib/api";

export function Finance() {
  return (
    <Workbench
      title="Finance & Accounting"
      description="Ledger, vendors, expenses with approval, and purchase orders."
      tabs={[
        {
          slug: "expense",
          label: "Expenses",
          permPrefix: "finance_accounting",
          rowActions: [
            {
              label: "Approve",
              tone: "primary",
              show: (r) => r.approval_status === "pending" || !r.approval_status,
              run: async (_r, id) => {
                await api.post(`/finance/expenses/${id}/decide`, { decision: "approved" });
              },
            },
            {
              label: "Reject",
              tone: "danger",
              show: (r) => r.approval_status === "pending" || !r.approval_status,
              run: async (_r, id) => {
                await api.post(`/finance/expenses/${id}/decide`, { decision: "rejected" });
              },
            },
            {
              label: "Mark Paid",
              tone: "ghost",
              show: (r) => r.approval_status === "approved",
              run: async (_r, id) => {
                await api.post(`/finance/expenses/${id}/decide`, { decision: "paid" });
              },
            },
          ],
        },
        { slug: "vendor", label: "Vendors", permPrefix: "finance_accounting" },
        { slug: "ledger-account", label: "Ledger Accounts", permPrefix: "finance_accounting" },
        { slug: "purchase-order", label: "Purchase Orders", permPrefix: "finance_accounting" },
      ]}
    />
  );
}
