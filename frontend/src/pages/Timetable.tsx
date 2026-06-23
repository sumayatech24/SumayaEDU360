import { Workbench } from "../components/Workbench";

export function Timetable() {
  return (
    <Workbench
      title="Timetable & Scheduling"
      description="Class periods by grade, section, day and slot."
      tabs={[{ slug: "timetable-period", label: "Periods", permPrefix: "timetable_scheduling" }]}
    />
  );
}
