import { AlertTriangle, Building2, FileText, ListTodo, ShieldCheck } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const AVAILABLE_SECTIONS = [
  {
    title: "Организации",
    description: "Общее количество организаций и дальнейшая детализация по выбранному периоду.",
    icon: Building2,
  },
  {
    title: "Договоры",
    description: "Активные, завершённые и расторгнутые договоры без дублирования бизнес-данных.",
    icon: FileText,
  },
  {
    title: "Задачи",
    description: "Новые, в работе, выполненные, отменённые и просроченные задачи.",
    icon: ListTodo,
  },
];

export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Управленческий отчёт</h1>
        <p className="text-sm text-muted-foreground">
          Сводка формируется из рабочих данных системы. Демо-значения не используются.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {AVAILABLE_SECTIONS.map(({ title, description, icon: Icon }) => (
          <Card key={title}>
            <CardHeader className="flex flex-row items-center gap-3 space-y-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <CardTitle className="text-base">{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              Контроль документов
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="font-medium">Источник документов ещё не подключён</p>
            <p className="text-sm text-muted-foreground">
              После подключения домена документов здесь появятся просроченные, истекающие,
              отсутствующие документы и документы без указанного срока действия.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              Экспертизы
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="font-medium">Источник экспертиз ещё не подключён</p>
            <p className="text-sm text-muted-foreground">
              Раздел начнёт показывать реальные показатели после появления backend-домена
              экспертиз в интеграционной базе.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
