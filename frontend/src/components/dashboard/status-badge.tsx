import { cn } from "@/lib/utils";

import type { ContractStatus, ExpertiseStatus, TaskStatus } from "@/lib/mock-data";

type StatusKind = "contract" | "expertise" | "task";

const contractClass: Record<ContractStatus, string> = {
  Черновик: "bg-status-draft text-status-draft",
  "На согласовании": "bg-status-review text-status-review",
  Подписан: "bg-status-signed text-status-signed",
  "В работе": "bg-status-active text-status-active",
  Приостановлен: "bg-status-paused text-status-paused",
  Завершён: "bg-status-done text-status-done",
  Расторгнут: "bg-status-terminated text-status-terminated",
  Архив: "bg-status-draft text-status-draft",
};

const expertiseClass: Record<ExpertiseStatus, string> = {
  Подготовка: "bg-status-draft text-status-draft",
  "Сбор документов": "bg-status-expertise text-status-expertise",
  Обследование: "bg-status-expertise text-status-expertise",
  "Подготовка заключения": "bg-status-review text-status-review",
  "Внутреннее согласование": "bg-status-review text-status-review",
  "Готово к регистрации": "bg-status-rtn text-status-rtn",
  "На рассмотрении в РТН": "bg-status-rtn text-status-rtn",
  "Отказ РТН / Требует доработки": "bg-status-rejected text-status-rejected",
  Зарегистрировано: "bg-status-registered text-status-registered",
  "Получено заказчиком": "bg-status-registered text-status-registered",
  Завершено: "bg-status-done text-status-done",
};

const taskClass: Record<TaskStatus, string> = {
  Новая: "bg-status-expertise text-status-expertise",
  "В работе": "bg-status-review text-status-review",
  Выполнена: "bg-status-registered text-status-registered",
  Отменена: "bg-status-draft text-status-draft",
};

export function StatusBadge({
  status,
  kind,
  className,
}: {
  status: string;
  kind: StatusKind;
  className?: string;
}) {
  const colorClass =
    kind === "contract"
      ? contractClass[status as ContractStatus] ?? "bg-status-draft text-status-draft"
      : kind === "expertise"
        ? expertiseClass[status as ExpertiseStatus] ?? "bg-status-draft text-status-draft"
        : taskClass[status as TaskStatus] ?? "bg-status-draft text-status-draft";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        colorClass,
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {status}
    </span>
  );
}
