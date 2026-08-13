import {
  Home,
  Building2,
  FileText,
  ShieldCheck,
  ListTodo,
  BookOpen,
  CalendarDays,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  description?: string;
};

export const mainNav: NavItem[] = [
  {
    href: "/",
    label: "Главная",
    icon: Home,
    description: "Сводка и аналитика",
  },
  {
    href: "/organizations",
    label: "Организации",
    icon: Building2,
    description: "Заказчики и владельцы",
  },
  {
    href: "/contracts",
    label: "Договоры",
    icon: FileText,
    description: "Договоры и предметы",
  },
  {
    href: "/expertise",
    label: "Экспертизы",
    icon: ShieldCheck,
    description: "Экспертизы промышленной безопасности",
  },
  {
    href: "/tasks",
    label: "Задачи",
    icon: ListTodo,
    description: "Мои задачи и рабочие процессы",
  },
  {
    href: "/reports",
    label: "Отчёты",
    icon: FileText,
    description: "Управленческая отчётность и контроль",
  },
  {
    href: "/npd",
    label: "НПД",
    icon: BookOpen,
    description: "Нормативно-техническая документация",
  },
  {
    href: "/calendar",
    label: "Календарь",
    icon: CalendarDays,
    description: "Сроки и события",
  },
];

export const settingsNav: NavItem[] = [
  {
    href: "/settings",
    label: "Настройки",
    icon: Settings,
    description: "Параметры системы",
  },
];
