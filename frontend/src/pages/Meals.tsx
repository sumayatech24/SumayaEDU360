import { Workbench } from "../components/Workbench";

export function Meals() {
  return (
    <Workbench
      title="Meal & Cafeteria"
      description="Meal plans and weekly menus with nutrition info."
      tabs={[
        { slug: "meal-plan", label: "Meal Plans", permPrefix: "meal_cafeteria" },
        { slug: "meal-menu", label: "Weekly Menu", permPrefix: "meal_cafeteria" },
      ]}
    />
  );
}
