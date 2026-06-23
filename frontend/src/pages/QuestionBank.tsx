import { Workbench } from "../components/Workbench";

export function QuestionBank() {
  return (
    <Workbench
      title="Question Paper Management"
      description="Subject-wise question bank by type, difficulty and marks."
      tabs={[{ slug: "question-bank-item", label: "Question Bank", permPrefix: "question_paper_management" }]}
    />
  );
}
