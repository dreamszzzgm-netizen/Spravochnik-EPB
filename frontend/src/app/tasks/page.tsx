import { ListTodo } from "lucide-react";

import { PilotEmptyModule } from "@/components/pilot-empty-module";
import { PilotSectionHeader } from "@/components/pilot-section-header";
import { PILOT_UNAVAILABLE } from "@/components/pilot-unavailable-copy";

export default function TasksPage() {
  return (
    <div className="space-y-6">
      <PilotSectionHeader
        title="Задачи"
        description="Мои задачи и задачи сотрудников"
      />
      <PilotEmptyModule
        icon={ListTodo}
        title="Задачи пока не отображаются"
        description={PILOT_UNAVAILABLE.tasks}
        actionLabel="Перейти к организациям"
        actionHref="/organizations"
      />
    </div>
  );
}
