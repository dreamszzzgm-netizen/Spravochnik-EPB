"use client";

import {
  ListTodo,
  ClipboardList,
  Search,
  ShieldCheck,
  Calculator,
  BookOpen,
  FileText,
  Stethoscope,
  MessageSquare,
  History,
  Users,
  Paperclip,
} from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { PriorityBadge } from "@/components/dashboard/priority-badge";
import { DeadlineChip } from "@/components/dashboard/deadline-chip";
import { expertiseDetail, myTasks } from "@/lib/mock-data";

export function ExpertiseTabs() {
  return (
    <Tabs defaultValue="main" className="w-full">
      <div className="overflow-x-auto">
        <TabsList className="inline-flex h-auto w-auto min-w-full justify-start gap-1 bg-muted/50 p-1">
          <TabsTrigger value="main" className="gap-1.5">
            <ClipboardList className="h-3.5 w-3.5" />
            Основное
          </TabsTrigger>
          <TabsTrigger value="subject" className="gap-1.5">
            <Stethoscope className="h-3.5 w-3.5" />
            Предмет экспертизы
          </TabsTrigger>
          <TabsTrigger value="experts" className="gap-1.5">
            <Users className="h-3.5 w-3.5" />
            Эксперты
          </TabsTrigger>
          <TabsTrigger value="tasks" className="gap-1.5">
            <ListTodo className="h-3.5 w-3.5" />
            Задачи
            <Badge variant="secondary" className="ml-1 h-4 px-1 text-[10px]">
              3
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="survey" className="gap-1.5">
            <Search className="h-3.5 w-3.5" />
            Обследование
          </TabsTrigger>
          <TabsTrigger value="calc" className="gap-1.5">
            <Calculator className="h-3.5 w-3.5" />
            Расчёты
          </TabsTrigger>
          <TabsTrigger value="npd" className="gap-1.5">
            <BookOpen className="h-3.5 w-3.5" />
            НПД
          </TabsTrigger>
          <TabsTrigger value="conclusion" className="gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            Заключение
          </TabsTrigger>
          <TabsTrigger value="docs" className="gap-1.5">
            <Paperclip className="h-3.5 w-3.5" />
            Документы
          </TabsTrigger>
          <TabsTrigger value="rtn" className="gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5" />
            Регистрация в РТН
          </TabsTrigger>
          <TabsTrigger value="comments" className="gap-1.5">
            <MessageSquare className="h-3.5 w-3.5" />
            Комментарии
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-1.5">
            <History className="h-3.5 w-3.5" />
            История
          </TabsTrigger>
        </TabsList>
      </div>

      <div className="mt-6">
        <TabsContent value="main" className="m-0">
          <MainTab />
        </TabsContent>
        <TabsContent value="subject" className="m-0">
          <SubjectTab />
        </TabsContent>
        <TabsContent value="experts" className="m-0">
          <ExpertsTab />
        </TabsContent>
        <TabsContent value="tasks" className="m-0">
          <TasksTab />
        </TabsContent>
        <TabsContent value="survey" className="m-0">
          <SurveyTab />
        </TabsContent>
        <TabsContent value="calc" className="m-0">
          <CalculationsTab />
        </TabsContent>
        <TabsContent value="npd" className="m-0">
          <NpdTab />
        </TabsContent>
        <TabsContent value="conclusion" className="m-0">
          <ConclusionTab />
        </TabsContent>
        <TabsContent value="docs" className="m-0">
          <DocsTab />
        </TabsContent>
        <TabsContent value="rtn" className="m-0">
          <RtnTab />
        </TabsContent>
        <TabsContent value="comments" className="m-0">
          <CommentsTab />
        </TabsContent>
        <TabsContent value="history" className="m-0">
          <HistoryTab />
        </TabsContent>
      </div>
    </Tabs>
  );
}

function MainTab() {
  const e = expertiseDetail;
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Сводная информация</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <InfoRow label="Номер экспертизы" value={e.number} mono />
            <InfoRow label="Тип экспертизы" value={e.type} />
            <InfoRow label="Предмет экспертизы" value={e.subject.name} />
            <InfoRow label="Тип предмета" value={e.subject.type === "ТУ" ? "Техническое устройство" : "Здание / сооружение"} />
            <InfoRow label="Заказчик" value={e.organization.name} />
            <InfoRow label="ИНН заказчика" value={e.organization.inn} mono />
            <InfoRow label="ОПО" value={e.organization.opoName} />
            <InfoRow label="Рег. № ОПО" value={e.organization.opoRegNumber} mono />
            <InfoRow label="Договор" value={e.contractNumber} mono />
            <InfoRow label="Класс опасности ОПО" value={e.organization.opoClass} />
            <InfoRow label="Дата создания" value={e.createdAt} />
            <InfoRow label="Статус" value={<StatusBadge status={e.status} kind="expertise" />} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Связанные сущности</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <LinkRow label="Организация" value={e.organization.name} href={`/organizations/${e.organization.id}`} />
          <LinkRow label="Договор" value={e.contractNumber} href={`/contracts/${e.contractId}`} mono />
          <LinkRow label="Предмет экспертизы" value={e.subject.name} href="#" mono />
          <LinkRow label="Ответственный эксперт" value={e.responsibleExpert.name} />
        </CardContent>
      </Card>
    </div>
  );
}

function SubjectTab() {
  const s = expertiseDetail.subject;
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Предмет экспертизы — технические характеристики</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <InfoRow label="Наименование" value={s.name} />
          <InfoRow label="Марка / модель" value={s.model} mono />
          <InfoRow label="Заводской №" value={s.serial} mono />
          <InfoRow label="Изготовитель" value={s.manufacturer} />
          <InfoRow label="Год изготовления" value={String(s.year)} />
          <InfoRow label="Рабочее давление" value={s.pressure} />
          <InfoRow label="Температура" value={s.temperature} />
          <InfoRow label="Объём" value={s.volume} />
          <InfoRow label="Среда" value={s.medium} />
        </dl>
      </CardContent>
    </Card>
  );
}

function ExpertsTab() {
  const e = expertiseDetail;
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Эксперты</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ul className="divide-y divide-border">
            {e.experts.map((x) => (
              <li key={x.name} className="flex items-center gap-3 px-4 py-3">
                <AvatarCircle name={x.name} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{x.name}</p>
                  <p className="text-xs text-muted-foreground">{x.role}</p>
                </div>
                <Badge variant="outline" className="font-mono text-[11px]">
                  {x.certificate}
                </Badge>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Специалисты</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ul className="divide-y divide-border">
            {e.specialists.map((x) => (
              <li key={x.name} className="flex items-center gap-3 px-4 py-3">
                <AvatarCircle name={x.name} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{x.name}</p>
                  <p className="text-xs text-muted-foreground">{x.role}</p>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function TasksTab() {
  const list = myTasks.filter((t) => t.expertiseId === "exp-2401" || t.expertiseId === "exp-2406");
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="text-base">Задачи по экспертизе</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {list.map((t) => (
            <li
              key={t.id}
              className={
                t.overdue
                  ? "border-l-2 border-l-deadline-overdue"
                  : "border-l-2 border-l-transparent"
              }
            >
              <div className="flex items-start gap-4 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{t.title}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                    <DeadlineChip date={parseDate(t.dueDate)} showIcon={false} />
                    <PriorityBadge priority={t.priority} />
                  </div>
                </div>
                <StatusBadge status={t.status} kind="task" />
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function SurveyTab() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Диагностика и НК</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            <NkRow method="ВИК" scope="Сварные швы корпуса, 100%" result="Без критичных дефектов" />
            <NkRow method="УЗК" scope="Сварные швы, 25%" result="Без дефектов" />
            <NkRow method="Измерение твёрдости" scope="3 точки" result="HB 145–152" />
            <NkRow method="Металлография" scope="1 образец" result="Структура соответствует" />
          </ul>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Выявленные дефекты</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-3 rounded-md border border-border/70 px-3 py-2">
              <Badge className="bg-amber-500/15 text-amber-700 hover:bg-amber-500/15 dark:text-amber-300">
                Замечание
              </Badge>
              <div className="min-w-0 flex-1">
                <p className="text-foreground">
                  Локальная коррозия опорной обечайки, глубина до 0.6 мм
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Допустимо по ФНП-536 · рекомендуется мониторинг
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3 rounded-md border border-border/70 px-3 py-2">
              <Badge className="bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-300">
                Норма
              </Badge>
              <div className="min-w-0 flex-1">
                <p className="text-foreground">Толщина стенки в контрольных точках — без утонения</p>
              </div>
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function CalculationsTab() {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="text-base">Расчёты</CardTitle>
        <Badge variant="secondary">1 расчёт</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border border-border/70 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">
                Расчёт на прочность корпуса сосуда
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Методика: ГОСТ 34347-2017, п. 8.4 · Выполнен: 25.02.2026
              </p>
            </div>
            <Badge className="bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-300">
              Соответствует
            </Badge>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            <InfoRow label="Допускаемое давление" value="1.92 МПа" />
            <InfoRow label="Рабочее давление" value="1.6 МПа" />
            <InfoRow label="Коэффициент запаса" value="1.20" />
            <InfoRow label="Результат" value="Соответствует" />
          </dl>
        </div>
      </CardContent>
    </Card>
  );
}

function NpdTab() {
  const e = expertiseDetail;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="text-base">Применимые НПД</CardTitle>
        <Badge variant="secondary">{e.npd.length} документа</Badge>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {e.npd.map((n) => (
            <li key={n.id} className="flex items-start gap-3 px-4 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <BookOpen className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-medium text-foreground">{n.short}</span>
                  <Badge variant="secondary">Действует</Badge>
                </div>
                <p className="mt-1 text-sm text-foreground">{n.title}</p>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function ConclusionTab() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
          <CardTitle className="text-base">Проект заключения ЭПБ</CardTitle>
          <Badge variant="secondary">Черновик</Badge>
        </CardHeader>
        <CardContent className="space-y-4 text-sm leading-relaxed">
          <Section title="1. Общие сведения">
            Экспертиза промышленной безопасности технического устройства — сосуд
            В-101/2 — выполнена на основании договора {expertiseDetail.contractNumber} от
            {" "}
            {expertiseDetail.createdAt}.
          </Section>
          <Section title="2. Объект экспертизы">
            Сосуд В-101/2, зав. № {expertiseDetail.subject.serial}, изготовитель —
            {" "}
            {expertiseDetail.subject.manufacturer}, год изготовления — {expertiseDetail.subject.year}.
          </Section>
          <Section title="3. Результаты обследования">
            По результатам ВИК, УЗК и измерения твёрдости критичных дефектов не выявлено.
            Локальная коррозия опорной обечайки в пределах допустимого по ФНП-536.
          </Section>
          <Section title="4. Заключение">
            Сосуд В-101/2 соответствует требованиям промышленной безопасности и может
            эксплуатироваться в установленном режиме до следующей экспертизы.
          </Section>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Подготовка заключения</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <ChecklistRow done label="Сводные данные по экспертизе" />
          <ChecklistRow done label="Рассмотренные документы" />
          <ChecklistRow done label="Результаты обследования" />
          <ChecklistRow done label="Расчёты" />
          <ChecklistRow done label="НПД" />
          <ChecklistRow label="Внутреннее согласование" />
          <ChecklistRow label="Финализация" />
          <Separator />
          <p className="text-xs text-muted-foreground">
            ИИ может подготовить черновик раздела или рекомендации — финальное решение принимает эксперт.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function DocsTab() {
  const e = expertiseDetail;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="text-base">Документы</CardTitle>
        <Badge variant="secondary">{e.consideredDocs.length} файла</Badge>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {e.consideredDocs.map((d) => (
            <li key={d.id} className="flex items-center gap-3 px-4 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{d.name}</p>
                <p className="text-xs text-muted-foreground">PDF · 1.2 МБ</p>
              </div>
              <StatusBadge status={d.status} kind="contract" />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function RtnTab() {
  const e = expertiseDetail;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="text-base">Попытки регистрации в РТН</CardTitle>
        <Badge variant="secondary">попытка №{e.rtnAttempts.length}</Badge>
      </CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2 font-medium">№</th>
              <th className="px-4 py-2 font-medium">Подготовлен</th>
              <th className="px-4 py-2 font-medium">Направлен</th>
              <th className="px-4 py-2 font-medium">Состояние</th>
              <th className="px-4 py-2 font-medium">Рег. номер</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {e.rtnAttempts.map((a) => (
              <tr key={a.n}>
                <td className="px-4 py-3 font-mono text-foreground">{a.n}</td>
                <td className="px-4 py-3 text-muted-foreground">{a.preparedAt}</td>
                <td className="px-4 py-3 text-muted-foreground">{a.sentAt}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={a.state} kind="expertise" />
                </td>
                <td className="px-4 py-3 text-muted-foreground">{a.registryNumber ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function CommentsTab() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Комментарии</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <CommentItem
          author="Петрова Е.С."
          when="2 ч назад"
          text="Запросила у заказчика уточнение по среде — они прислали обновлённый паспорт."
        />
        <CommentItem
          author="Иванов А.П."
          when="вчера"
          text="@Морозов, посмотри пожалуйста расчёт на прочность по разделу 4. Хочу согласовать до подачи в РТН."
          mention
        />
        <Separator />
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Написать комментарий… (@ чтобы упомянуть)"
            className="flex h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <button
            type="button"
            className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Отправить
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

function HistoryTab() {
  const e = expertiseDetail;
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Хронология</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-4 border-l border-border pl-6">
          {e.timeline.map((t, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[27px] top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 border-background bg-primary" />
              <p className="text-sm font-medium text-foreground">{t.event}</p>
              <p className="text-xs text-muted-foreground">{t.date}</p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function InfoRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        className={`mt-1 truncate text-sm text-foreground ${mono ? "font-mono" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}

function LinkRow({
  label,
  value,
  href,
  mono,
}: {
  label: string;
  value: string;
  href?: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">{label}</span>
      {href ? (
        <a href={href} className={`truncate text-sm text-primary hover:underline ${mono ? "font-mono" : ""}`}>
          {value}
        </a>
      ) : (
        <span className={`truncate text-sm text-foreground ${mono ? "font-mono" : ""}`}>{value}</span>
      )}
    </div>
  );
}

function NkRow({
  method,
  scope,
  result,
}: {
  method: string;
  scope: string;
  result: string;
}) {
  return (
    <li className="flex items-start gap-3 rounded-md border border-border/70 px-3 py-2">
      <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide">
        {method}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-foreground">{scope}</p>
        <p className="text-xs text-muted-foreground">{result}</p>
      </div>
    </li>
  );
}

function AvatarCircle({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("");
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
      {initials}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <p className="mt-1 text-foreground">{children}</p>
    </div>
  );
}

function ChecklistRow({ label, done }: { label: string; done?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={
          done
            ? "flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
            : "flex h-4 w-4 items-center justify-center rounded-full border border-dashed border-muted-foreground/40"
        }
      >
        {done && (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-3 w-3"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </span>
      <span className={done ? "text-foreground" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}

function CommentItem({
  author,
  when,
  text,
  mention,
}: {
  author: string;
  when: string;
  text: string;
  mention?: boolean;
}) {
  return (
    <div className="flex gap-3">
      <AvatarCircle name={author} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium text-foreground">{author}</span>
          <span className="text-xs text-muted-foreground">{when}</span>
        </div>
        <p className="mt-1 text-sm text-foreground">
          {mention ? (
            <>
              <span className="font-medium text-primary">@Морозов</span>, посмотри пожалуйста
              расчёт на прочность по разделу 4. Хочу согласовать до подачи в РТН.
            </>
          ) : (
            text
          )}
        </p>
      </div>
    </div>
  );
}

function parseDate(s: string): Date {
  const [d, m, y] = s.split(".");
  return new Date(Number(y), Number(m) - 1, Number(d));
}
