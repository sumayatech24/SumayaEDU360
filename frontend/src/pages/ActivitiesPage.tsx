import { Workbench } from "../components/Workbench";

export function ActivitiesPage() {
  return (
    <Workbench
      title="Activities & Events"
      description="Clubs, sports, competitions and capacity-aware student registrations."
      tabs={[
        { slug: "activity", label: "Activities", permPrefix: "activities_events" },
        { slug: "activity-registration", label: "Registrations", permPrefix: "activities_events" },
      ]}
    />
  );
}
