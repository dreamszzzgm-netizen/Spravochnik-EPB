import { BookOpen, Building2, CalendarDays, FileText, ListTodo, ShieldCheck } from "lucide-react";

import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { PilotModuleStatusCard } from "@/components/pilot-module-status-card";
import { PilotReadinessNote } from "@/components/pilot-readiness-note";

const modules = [
  {
    title: "Организации",
    description: "Рабочий раздел подключён к серверным данным.",
    href: "/organizations",
    actionLabel: "Открыть организации",
    icon: Building2,
  },
  {
    title: "Договоры",
    description: "Серверный модуль существует; реестр Next.js будет подключён отдельным этапом.",
    href: "/contracts",
    actionLabel: "Открыть состояние раздела",
    icon: FileText,
  },
  {
    title: "Задачи",
    description: "Серверный модуль существует; реестр Next.js будет подключён отдельным этапом.",
    href: "/tasks",
    actionLabel: "Открыть состояние раздела",
    icon: ListTodo,
  },
  {
    title: "Экспертизы",
    description: "Полноценный модуль экспертиз запланирован на Stage 6.",
    href: "/expertise",
    actionLabel: "Открыть состояние раздела",
    icon: ShieldCheck,
  },
  {
    title: "НПД",
    description: "Нормативная база будет отображаться после подключения серверного модуля НПД.",
    href: "/npd",
    actionLabel: "Открыть состояние раздела",
    icon: BookOpen,
  },
  {
    title: "Календарь",
    description: "Календарные события будут агрегироваться после подключения соответствующих модулей.",
    href: "/calendar",
    actionLabel: "Открыть календарь",
    icon: CalendarDays,
  },
] as const;

export default function HomePage() {
  return (
    <div className="space-y-6">
      <DashboardHeader />

      <PilotReadinessNote>
        Главная страница Pilot показывает только фактическую готовность модулей. Фиктивные KPI, сроки, события и рабочие записи не используются.
      </PilotReadinessNote>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Готовность модулей Pilot">
        {modules.map((module) => (
          <PilotModuleStatusCard key={module.title} {...module} />
        ))}
      </section>
    </div>
  );
}
