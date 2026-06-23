import { Workbench } from "../components/Workbench";
import { api } from "../lib/api";

export function CMS() {
  return (
    <Workbench
      title="Public Website & CMS"
      description="Pages, news, events and homepage banners. Publish to make content live."
      tabs={[
        {
          slug: "cms-page",
          label: "Pages & News",
          permPrefix: "public_website_cms",
          rowActions: [
            {
              label: "Publish",
              tone: "primary",
              show: (r) => !r.is_published,
              run: async (_r, id) => {
                await api.put(`/cms-page/${id}`, { is_published: true, publish_date: new Date().toISOString().slice(0, 10) });
              },
            },
            {
              label: "Unpublish",
              tone: "ghost",
              show: (r) => r.is_published,
              run: async (_r, id) => {
                await api.put(`/cms-page/${id}`, { is_published: false });
              },
            },
          ],
        },
        { slug: "banner", label: "Banners", permPrefix: "public_website_cms" },
      ]}
    />
  );
}
