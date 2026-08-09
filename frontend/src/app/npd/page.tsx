import { BookOpen, Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

const sample = [
  {
    id: "npd-536",
    short: "ФНП-536",
    title:
      "Правила промышленной безопасности при использовании оборудования, работающего под избыточным давлением",
    organ: "Ростехнадзор",
    date: "15.12.2020",
    status: "Действует",
  },
  {
    id: "npd-533",
    short: "ФНП-533",
    title: "Правила промышленной безопасности складов нефти и нефтепродуктов",
    organ: "Ростехнадзор",
    date: "15.12.2020",
    status: "Действует",
  },
  {
    id: "gost-34347",
    short: "ГОСТ 34347-2017",
    title: "Сосуды и аппараты стальные сварные. Общие технические условия",
    organ: "Росстандарт",
    date: "01.07.2018",
    status: "Действует",
  },
];

export default function NpdPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">НПД</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Нормативно-техническая документация: ФНП, ГОСТ, СП, РД и др.
          </p>
        </div>
        <Button size="sm">
          <Plus className="mr-1.5 h-4 w-4" />
          Добавить документ
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Поиск по номеру или названию…" className="pl-9" />
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <ul className="divide-y divide-border">
            {sample.map((n) => (
              <li key={n.id} className="px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <BookOpen className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium text-foreground">
                        {n.short}
                      </span>
                      <Badge variant="secondary">{n.status}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-foreground">{n.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {n.organ} · от {n.date}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <EmptyState
        icon={BookOpen}
        title="Полная база НПД появится в ближайших релизах"
        description="Импорт из XML-выгрузок Ростехнадзора, контроль актуальности и привязка к типам ТУ/ЗиС/экспертиз."
      />
    </div>
  );
}
