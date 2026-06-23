import { Workbench } from "../components/Workbench";
import { api } from "../lib/api";

export function Communication() {
  return (
    <Workbench
      title="Communication"
      description="Announcements and notices across in-app, email, SMS and WhatsApp channels."
      tabs={[
        {
          slug: "announcement",
          label: "Announcements",
          permPrefix: "ptm_communication",
          rowActions: [
            {
              label: "Publish",
              tone: "primary",
              show: (r) => r.announcement_status !== "published",
              run: async (_r, id) => {
                await api.post(`/announcements/${id}/publish`);
              },
            },
          ],
        },
      ]}
    />
  );
}
