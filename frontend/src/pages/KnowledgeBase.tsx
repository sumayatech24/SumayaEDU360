import { Workbench } from "../components/Workbench";
import { api } from "../lib/api";

export function KnowledgeBase() {
  return (
    <Workbench
      title="Knowledge Base & Digital Library"
      description="Policies, handbooks and FAQs, plus the digital learning repository."
      tabs={[
        {
          slug: "knowledge-article",
          label: "Articles",
          permPrefix: "knowledge_base",
          rowActions: [
            {
              label: "Publish",
              tone: "primary",
              show: (r) => !r.is_published,
              run: async (_r, id) => {
                await api.put(`/knowledge-article/${id}`, { is_published: true });
              },
            },
          ],
        },
        { slug: "learning-resource", label: "Learning Resources", permPrefix: "digital_learning_repository" },
      ]}
    />
  );
}
