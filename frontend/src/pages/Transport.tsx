import { Workbench } from "../components/Workbench";

export function Transport() {
  return (
    <Workbench
      title="Transport"
      description="Routes, vehicles, stops and student transport assignments with fee mapping."
      tabs={[
        { slug: "transport-route", label: "Routes", permPrefix: "transport" },
        { slug: "vehicle", label: "Vehicles", permPrefix: "transport" },
        { slug: "route-stop", label: "Stops", permPrefix: "transport" },
        { slug: "transport-assignment", label: "Student Assignments", permPrefix: "transport" },
      ]}
    />
  );
}
