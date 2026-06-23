import { Workbench } from "../components/Workbench";
import { api } from "../lib/api";

export function HomeworkPage() {
  return (
    <Workbench
      title="Homework & Assignments"
      description="Assign homework, collect submissions and grade them."
      tabs={[
        { slug: "homework", label: "Homework", permPrefix: "homework_assignments" },
        {
          slug: "homework-submission",
          label: "Submissions",
          permPrefix: "homework_assignments",
          rowActions: [
            {
              label: "Grade",
              tone: "primary",
              show: (r) => r.submission_status !== "graded",
              run: async (_r, id) => {
                const marks = prompt("Marks awarded:");
                if (marks === null) return;
                await api.post(`/homework/submissions/${id}/grade`, {
                  marks_awarded: Number(marks),
                });
              },
            },
          ],
        },
      ]}
    />
  );
}
