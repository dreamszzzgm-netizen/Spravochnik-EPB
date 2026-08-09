import Link from "next/link";
import {
  Building,
  Users,
  Database,
  GitBranch,
  FileText,
  Hash,
  Sparkles,
  FolderArchive,
  HardDrive,
  ShieldCheck,
  ChevronRight,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

const sections = [
  {
    href: "/settings/organization",
    icon: Building,
    title: "Моя экспертная организация",
    description: "Реквизиты, реквизиты для документов",
  },
  {
    href: "/settings/staff",
    icon: Users,
    title: "Сотрудники и пользователи",
    description: "Сотрудники, эксперты, учётки и права",
  },
  {
    href: "/settings/dictionaries",
    icon: Database,
    title: "Справочники",
    description: "Типы ТУ, ЗиС, методы НК, области аттестации",
  },
  {
    href: "/settings/workflows",
    icon: GitBranch,
    title: "Рабочие процессы",
    description: "Шаблоны задач и переходов статусов",
  },
  {
    href: "/settings/templates",
    icon: FileText,
    title: "Шаблоны документов",
    description: "DOCX-шаблоны и движок формирования",
  },
  {
    href: "/settings/numbering",
    icon: Hash,
    title: "Нумерация",
    description: "Форматы внутренних номеров документов",
  },
  {
    href: "/settings/ai",
    icon: Sparkles,
    title: "ИИ",
    description: "Локальные и внешние модели, обезличивание",
  },
  {
    href: "/settings/storage",
    icon: FolderArchive,
    title: "Файловое хранилище",
    description: "Расположение и лимиты хранилища",
  },
  {
    href: "/settings/backup",
    icon: HardDrive,
    title: "Резервное копирование",
    description: "Автоматическое и ручное копирование",
  },
  {
    href: "/settings/system",
    icon: ShieldCheck,
    title: "Система",
    description: "Состояние БД, версия, диагностика",
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Настройки</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Параметры системы и администрирование
        </p>
      </div>

      <Card>
        <CardContent className="p-0">
          <ul className="divide-y divide-border">
            {sections.map((s) => {
              const Icon = s.icon;
              return (
                <li key={s.href}>
                  <Link
                    href={s.href}
                    className="flex items-center gap-4 px-4 py-4 transition-colors hover:bg-muted/40"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground">{s.title}</p>
                      <p className="text-xs text-muted-foreground">{s.description}</p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
