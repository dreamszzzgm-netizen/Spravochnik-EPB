import { cn } from "@/lib/utils";

import type { TaskPriority } from "@/lib/mock-data";

const map: Record<TaskPriority, { className: string; label: string }> = {
  низкий: { className: "bg-priority-low text-priority-low", label: "Низкий" },
  обычный: { className: "bg-priority-normal text-priority-normal", label: "Обычный" },
  высокий: { className: "bg-priority-high text-priority-high", label: "Высокий" },
  срочный: { className: "bg-priority-urgent text-priority-urgent", label: "Срочный" },
};

export function PriorityBadge({ priority, className }: { priority: TaskPriority; className?: string }) {
  const { className: colorClass, label } = map[priority];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
        colorClass,
        className
      )}
    >
      <span className="h-1 w-1 rounded-full bg-current" />
      {label}
    </span>
  );
}
