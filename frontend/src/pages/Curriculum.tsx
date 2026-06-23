import { Workbench } from "../components/Workbench";
import { api } from "../lib/api";

export function Curriculum() {
  return (
    <Workbench
      title="Curriculum & Lesson Planning"
      description="Lesson plans with objectives, resources and completion tracking."
      tabs={[
        {
          slug: "lesson-plan",
          label: "Lesson Plans",
          permPrefix: "curriculum_lesson_planning",
          rowActions: [
            {
              label: "Start",
              tone: "ghost",
              show: (r) => r.plan_status === "planned" || !r.plan_status,
              run: async (_r, id) => {
                await api.put(`/lesson-plan/${id}`, { plan_status: "in_progress" });
              },
            },
            {
              label: "Complete",
              tone: "primary",
              show: (r) => r.plan_status !== "completed",
              run: async (_r, id) => {
                await api.put(`/lesson-plan/${id}`, { plan_status: "completed", completion_percent: 100 });
              },
            },
          ],
        },
      ]}
    />
  );
}
