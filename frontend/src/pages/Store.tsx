import { Workbench } from "../components/Workbench";
import { api } from "../lib/api";

export function Store() {
  return (
    <Workbench
      title="Store & Inventory"
      description="Stock items, reorder levels and stock movements (in/out) that adjust quantity-on-hand."
      tabs={[
        {
          slug: "inventory-item",
          label: "Items",
          permPrefix: "finance_accounting",
          rowActions: [
            {
              label: "Stock In",
              tone: "primary",
              run: async (_r, id) => {
                const qty = prompt("Quantity received:");
                if (!qty) return;
                await api.post("/inventory/stock-movements", {
                  item_id: id,
                  movement_type: "in",
                  quantity: Number(qty),
                });
              },
            },
            {
              label: "Stock Out",
              tone: "ghost",
              run: async (_r, id) => {
                const qty = prompt("Quantity issued:");
                if (!qty) return;
                await api.post("/inventory/stock-movements", {
                  item_id: id,
                  movement_type: "out",
                  quantity: Number(qty),
                });
              },
            },
          ],
        },
        { slug: "stock-movement", label: "Movements", permPrefix: "finance_accounting", hideCreate: true },
      ]}
    />
  );
}
