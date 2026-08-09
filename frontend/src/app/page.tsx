import {
  AlertTriangle,
  Clock,
  FileText,
  FileX2,
  FolderTree,
  ShieldCheck,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { DocumentStatusChart } from "@/components/dashboard/document-status-chart";
import { EmployeeLoad } from "@/components/dashboard/employee-load";
import { ExpiringSoon } from "@/components/dashboard/expiring-soon";
import { ExpertiseDonut } from "@/components/dashboard/expertise-donut";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { MyTasksList } from "@/components/dashboard/my-tasks-list";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import {
  dashboardKpis,
  formatMoneyShort,
  contracts,
  expertiseList,
} from "@/lib/mock-data";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <DashboardHeader />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Активные договоры"
          value={dashboardKpis.contractsActive}
          icon={FileText}
          tone="default"
          href="/contracts"
          footerLabel="Открыть"
          hint={
            <>
              Сумма:{" "}
              <span className="font-medium text-foreground">
                {formatMoneyShort(dashboardKpis.contractsActiveSum)}
              </span>
            </>
          }
          delta={{ value: "+2 за месяц", trend: "up" }}
        />
        <KpiCard
          label="Экспертизы в работе"
          value={dashboardKpis.expertiseInProgress}
          icon={ShieldCheck}
          tone="default"
          href="/expertise"
          footerLabel="Открыть"
          hint={
            <>
              <span className="text-deadline-overdue">
                {dashboardKpis.expertiseRejected} отказ РТН
              </span>
              {" · "}
              <span className="text-priority-high">
                {dashboardKpis.expertiseAtRtn} на рассмотрении
              </span>
            </>
          }
        />
        <KpiCard
          label="Мои задачи на сегодня"
          value={dashboardKpis.myTasksToday}
          icon={Clock}
          tone={dashboardKpis.myTasksOverdue > 0 ? "danger" : "warning"}
          href="/tasks"
          footerLabel="Открыть"
          hint={
            <>
              <span className="text-deadline-overdue">
                {dashboardKpis.myTasksOverdue} просрочено
              </span>
              {" · срок: сегодня"}
            </>
          }
        />
        <KpiCard
          label="Документы с истекшим сроком"
          value={dashboardKpis.documentsExpired}
          icon={FileX2}
          tone={dashboardKpis.documentsExpired > 0 ? "danger" : "default"}
          href="/expertise"
          footerLabel="Открыть"
          hint={
            <>
              Заключения ЭПБ, у которых истёк срок следующего контроля — требуется повторная экспертиза
            </>
          }
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-entity-contract-muted text-entity-contract">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-base">Экспертизы по статусам</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {expertiseList.length} экспертиз всего
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <ExpertiseDonut />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-entity-expertise-muted text-entity-expertise">
                <FolderTree className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-base">Документы по сроку действия</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Заключения, акты, программы и протоколы
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <DocumentStatusChart />
          </CardContent>
        </Card>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MyTasksList />
        <ExpiringSoon />
        <RecentActivity />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-entity-task-muted text-entity-task">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-base">Загрузка сотрудников</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Открытые и завершённые задачи за период
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <EmployeeLoad />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Сводка по системе</CardTitle>
            <p className="text-xs text-muted-foreground">Ключевые показатели</p>
          </CardHeader>
          <CardContent className="space-y-3">
            <SummaryRow
              label="Договоров всего"
              value={contracts.length}
              sub={`${dashboardKpis.contractsCompletedCount} завершено`}
            />
            <SummaryRow
              label="Экспертиз"
              value={dashboardKpis.expertiseTotalCount}
              sub={`${dashboardKpis.expertiseRegisteredCount} зарегистр.`}
            />
            <SummaryRow
              label="Задач в работе"
              value={dashboardKpis.tasksTotal}
              sub={`${dashboardKpis.tasksDone} выполнено`}
            />
            <SummaryRow
              label="Заказчиков"
              value={dashboardKpis.organizationsCount}
              sub={`${dashboardKpis.opoCount} ОПО`}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  sub,
}: {
  label: string;
  value: number | string;
  sub?: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-dashed border-border/60 pb-2 last:border-b-0 last:pb-0">
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
      <p className="text-lg font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}
