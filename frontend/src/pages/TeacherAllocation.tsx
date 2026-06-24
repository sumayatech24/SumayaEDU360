import { Workbench } from "../components/Workbench";

/** Map teachers to class + section + subject (and class-teacher via Sections). */
export function TeacherAllocation() {
  return (
    <Workbench
      title="Teacher Allocation"
      description="Map teachers to a class, section and subject. These mappings drive teacher schedules, marks entry and each student's teacher list."
      tabs={[
        { slug: "teacher-assignment", label: "Subject Allocation", permPrefix: "teacher_management" },
        { slug: "section", label: "Class Teachers", permPrefix: "academic_configuration" },
      ]}
    />
  );
}
