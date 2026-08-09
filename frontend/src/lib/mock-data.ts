export type ContractStatus =
  | "Черновик"
  | "На согласовании"
  | "Подписан"
  | "В работе"
  | "Приостановлен"
  | "Завершён"
  | "Расторгнут"
  | "Архив";

export type ExpertiseStatus =
  | "Подготовка"
  | "Сбор документов"
  | "Обследование"
  | "Подготовка заключения"
  | "Внутреннее согласование"
  | "Готово к регистрации"
  | "На рассмотрении в РТН"
  | "Отказ РТН / Требует доработки"
  | "Зарегистрировано"
  | "Получено заказчиком"
  | "Завершено";

export type TaskStatus = "Новая" | "В работе" | "Выполнена" | "Отменена";
export type TaskPriority = "низкий" | "обычный" | "высокий" | "срочный";

export type ExpertiseType = "ТУ" | "ЗиС";

export type ContractKind = ContractStatus;
export type NotificationKind =
  | "task"
  | "deadline"
  | "overdue"
  | "status"
  | "mention"
  | "control";

export type SearchKind =
  | "organization"
  | "contract"
  | "expertise"
  | "task"
  | "event"
  | "npd";

export type SearchEntry = {
  id: string;
  kind: SearchKind;
  title: string;
  subtitle?: string;
  href: string;
  group: string;
  shortcut?: string;
};

export const currentUser = {
  id: "u-1",
  name: "Алексей Иванов",
  shortName: "АИ",
  role: "Эксперт",
  email: "a.ivanov@epb-expert.ru",
};

const today = new Date();
const addDays = (n: number) => {
  const d = new Date(today);
  d.setDate(d.getDate() + n);
  return d;
};
const iso = (d: Date) => d.toISOString();
const fmt = (d: Date) =>
  d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });

export const organizations = [
  {
    id: "org-1",
    name: 'АО "Нефтегаз-Сибирь"',
    short: "Нефтегаз-Сибирь",
    inn: "7701234567",
    opoCount: 4,
    devicesCount: 47,
    contractsCount: 3,
  },
  {
    id: "org-2",
    name: 'ООО "ХимПромИнжиниринг"',
    short: "ХимПромИнжиниринг",
    inn: "7702345678",
    opoCount: 2,
    devicesCount: 18,
    contractsCount: 2,
  },
  {
    id: "org-3",
    name: 'ПАО "УралМеталл"',
    short: "УралМеталл",
    inn: "6601234567",
    opoCount: 3,
    devicesCount: 31,
    contractsCount: 2,
  },
  {
    id: "org-4",
    name: 'АО "ТюменьТрансГаз"',
    short: "ТюменьТрансГаз",
    inn: "7201234567",
    opoCount: 5,
    devicesCount: 62,
    contractsCount: 4,
  },
  {
    id: "org-5",
    name: 'ООО "СибЭнергоМаш"',
    short: "СибЭнергоМаш",
    inn: "5401234567",
    opoCount: 1,
    devicesCount: 9,
    contractsCount: 1,
  },
];

export const contracts = [
  {
    id: "c-2026-018",
    number: "ЭПБ-018/2026",
    organizationId: "org-1",
    organizationName: 'АО "Нефтегаз-Сибирь"',
    status: "В работе" as ContractStatus,
    amount: 4_850_000,
    startDate: fmt(addDays(-42)),
    endDate: fmt(addDays(34)),
    subjectsCount: 8,
    expertiseCount: 6,
    responsible: "Иванов А.П.",
  },
  {
    id: "c-2026-024",
    number: "ЭПБ-024/2026",
    organizationId: "org-2",
    organizationName: 'ООО "ХимПромИнжиниринг"',
    status: "Подписан" as ContractStatus,
    amount: 2_280_000,
    startDate: fmt(addDays(-10)),
    endDate: fmt(addDays(80)),
    subjectsCount: 5,
    expertiseCount: 3,
    responsible: "Петрова Е.С.",
  },
  {
    id: "c-2026-031",
    number: "ЭПБ-031/2026",
    organizationId: "org-3",
    organizationName: 'ПАО "УралМеталл"',
    status: "На согласовании" as ContractStatus,
    amount: 1_650_000,
    startDate: fmt(addDays(7)),
    endDate: fmt(addDays(95)),
    subjectsCount: 4,
    expertiseCount: 0,
    responsible: "Соколов Д.А.",
  },
  {
    id: "c-2026-012",
    number: "ЭПБ-012/2026",
    organizationId: "org-4",
    organizationName: 'АО "ТюменьТрансГаз"',
    status: "В работе" as ContractStatus,
    amount: 7_120_000,
    startDate: fmt(addDays(-95)),
    endDate: fmt(addDays(12)),
    subjectsCount: 12,
    expertiseCount: 9,
    responsible: "Иванов А.П.",
  },
  {
    id: "c-2026-009",
    number: "ЭПБ-009/2026",
    organizationId: "org-1",
    organizationName: 'АО "Нефтегаз-Сибирь"',
    status: "Приостановлен" as ContractStatus,
    amount: 980_000,
    startDate: fmt(addDays(-60)),
    endDate: fmt(addDays(20)),
    subjectsCount: 3,
    expertiseCount: 1,
    responsible: "Кузнецова М.В.",
  },
  {
    id: "c-2025-188",
    number: "ЭПБ-188/2025",
    organizationId: "org-5",
    organizationName: 'ООО "СибЭнергоМаш"',
    status: "Завершён" as ContractStatus,
    amount: 3_420_000,
    startDate: fmt(addDays(-220)),
    endDate: fmt(addDays(-30)),
    subjectsCount: 6,
    expertiseCount: 6,
    responsible: "Иванов А.П.",
  },
];

export const expertiseList = [
  {
    id: "exp-2401",
    number: "ЭПБ-2026/2401",
    contractId: "c-2026-018",
    contractNumber: "ЭПБ-018/2026",
    organizationName: 'АО "Нефтегаз-Сибирь"',
    subjectType: "ТУ" as ExpertiseType,
    subjectName: "Сосуд В-101/2",
    status: "На рассмотрении в РТН" as ExpertiseStatus,
    responsible: "Иванов А.П.",
    nextControl: fmt(addDays(2)),
  },
  {
    id: "exp-2402",
    number: "ЭПБ-2026/2402",
    contractId: "c-2026-018",
    contractNumber: "ЭПБ-018/2026",
    organizationName: 'АО "Нефтегаз-Сибирь"',
    subjectType: "ЗиС" as ExpertiseType,
    subjectName: "Резервуар РВС-5000",
    status: "Обследование" as ExpertiseStatus,
    responsible: "Иванов А.П.",
    nextControl: fmt(addDays(8)),
  },
  {
    id: "exp-2403",
    number: "ЭПБ-2026/2403",
    contractId: "c-2026-024",
    contractNumber: "ЭПБ-024/2026",
    organizationName: 'ООО "ХимПромИнжиниринг"',
    subjectType: "ТУ" as ExpertiseType,
    subjectName: "Котёл ДКВр-10/13",
    status: "Подготовка заключения" as ExpertiseStatus,
    responsible: "Петрова Е.С.",
    nextControl: fmt(addDays(5)),
  },
  {
    id: "exp-2404",
    number: "ЭПБ-2026/2404",
    contractId: "c-2026-012",
    contractNumber: "ЭПБ-012/2026",
    organizationName: 'АО "ТюменьТрансГаз"',
    subjectType: "ТУ" as ExpertiseType,
    subjectName: "Газопровод Г-12",
    status: "Отказ РТН / Требует доработки" as ExpertiseStatus,
    responsible: "Иванов А.П.",
    nextControl: fmt(addDays(-3)),
  },
  {
    id: "exp-2405",
    number: "ЭПБ-2026/2405",
    contractId: "c-2026-012",
    contractNumber: "ЭПБ-012/2026",
    organizationName: 'АО "ТюменьТрансГаз"',
    subjectType: "ТУ" as ExpertiseType,
    subjectName: "Трубопровод Т-204",
    status: "Зарегистрировано" as ExpertiseStatus,
    responsible: "Соколов Д.А.",
    nextControl: fmt(addDays(18)),
  },
  {
    id: "exp-2406",
    number: "ЭПБ-2026/2406",
    contractId: "c-2026-018",
    contractNumber: "ЭПБ-018/2026",
    organizationName: 'АО "Нефтегаз-Сибирь"',
    subjectType: "ТУ" as ExpertiseType,
    subjectName: "Резервуар РВС-2000",
    status: "Готово к регистрации" as ExpertiseStatus,
    responsible: "Иванов А.П.",
    nextControl: fmt(addDays(1)),
  },
  {
    id: "exp-2407",
    number: "ЭПБ-2026/2407",
    contractId: "c-2026-024",
    contractNumber: "ЭПБ-024/2026",
    organizationName: 'ООО "ХимПромИнжиниринг"',
    subjectType: "ЗиС" as ExpertiseType,
    subjectName: "Эстакада слива №3",
    status: "Сбор документов" as ExpertiseStatus,
    responsible: "Петрова Е.С.",
    nextControl: fmt(addDays(14)),
  },
  {
    id: "exp-2408",
    number: "ЭПБ-2026/2408",
    contractId: "c-2026-012",
    contractNumber: "ЭПБ-012/2026",
    organizationName: 'АО "ТюменьТрансГаз"',
    subjectType: "ТУ" as ExpertiseType,
    subjectName: "Компрессор К-501",
    status: "Внутреннее согласование" as ExpertiseStatus,
    responsible: "Соколов Д.А.",
    nextControl: fmt(addDays(10)),
  },
];

export const myTasks = [
  {
    id: "t-901",
    title: "Подготовить заключение по сосуд В-101/2",
    priority: "срочный" as TaskPriority,
    status: "В работе" as TaskStatus,
    dueDate: fmt(addDays(1)),
    expertiseId: "exp-2401",
    expertiseNumber: "ЭПБ-2026/2401",
    overdue: false,
  },
  {
    id: "t-902",
    title: "Согласовать программу обследования с заказчиком",
    priority: "высокий" as TaskPriority,
    status: "Новая" as TaskStatus,
    dueDate: fmt(addDays(0)),
    expertiseId: "exp-2402",
    expertiseNumber: "ЭПБ-2026/2402",
    overdue: false,
  },
  {
    id: "t-903",
    title: "Запросить недостающие документы у ХимПромИнжиниринг",
    priority: "обычный" as TaskPriority,
    status: "В работе" as TaskStatus,
    dueDate: fmt(addDays(2)),
    expertiseId: "exp-2403",
    expertiseNumber: "ЭПБ-2026/2403",
    overdue: false,
  },
  {
    id: "t-904",
    title: "Доработать заключение по газопровод Г-12 (отказ РТН)",
    priority: "срочный" as TaskPriority,
    status: "В работе" as TaskStatus,
    dueDate: fmt(addDays(-1)),
    expertiseId: "exp-2404",
    expertiseNumber: "ЭПБ-2026/2404",
    overdue: true,
  },
  {
    id: "t-905",
    title: "Подготовить пакет документов в РТН (РВС-2000)",
    priority: "высокий" as TaskPriority,
    status: "Новая" as TaskStatus,
    dueDate: fmt(addDays(3)),
    expertiseId: "exp-2406",
    expertiseNumber: "ЭПБ-2026/2406",
    overdue: false,
  },
  {
    id: "t-906",
    title: "Подготовить акт готовности по компрессор К-501",
    priority: "обычный" as TaskPriority,
    status: "Новая" as TaskStatus,
    dueDate: fmt(addDays(5)),
    expertiseId: "exp-2408",
    expertiseNumber: "ЭПБ-2026/2408",
    overdue: false,
  },
  {
    id: "t-907",
    title: "Проверить расчёт на прочность по эстакаде №3",
    priority: "обычный" as TaskPriority,
    status: "Новая" as TaskStatus,
    dueDate: fmt(addDays(7)),
    expertiseId: "exp-2407",
    expertiseNumber: "ЭПБ-2026/2407",
    overdue: false,
  },
];

export const contractStatusDistribution: { status: ContractStatus; count: number }[] = [
  { status: "В работе", count: 2 },
  { status: "Подписан", count: 1 },
  { status: "На согласовании", count: 1 },
  { status: "Приостановлен", count: 1 },
  { status: "Завершён", count: 1 },
];

export type ExpertiseStage =
  | "Планируется выезд"
  | "В работе"
  | "На регистрации в РТН"
  | "Зарегистрирована";

export const expertiseStatusDistribution: { status: ExpertiseStage; count: number }[] = [
  { status: "Планируется выезд", count: 3 },
  { status: "В работе", count: 5 },
  { status: "На регистрации в РТН", count: 2 },
  { status: "Зарегистрирована", count: 4 },
];

export const expertiseStageDistribution: { status: ExpertiseStatus; count: number }[] = [
  { status: "Сбор документов", count: 1 },
  { status: "Обследование", count: 1 },
  { status: "Подготовка заключения", count: 1 },
  { status: "Внутреннее согласование", count: 1 },
  { status: "Готово к регистрации", count: 1 },
  { status: "На рассмотрении в РТН", count: 1 },
  { status: "Отказ РТН / Требует доработки", count: 1 },
  { status: "Зарегистрировано", count: 1 },
];

export type DocumentValidity =
  | "Действителен"
  | "Срок истекает через 40 дней"
  | "Срок истекает через 14 дней"
  | "Срок истек";

export type DocumentKind =
  | "Заключение ЭПБ"
  | "Акт готовности"
  | "Программа ЭПБ"
  | "Протокол обследования";

export type Document = {
  id: string;
  name: string;
  kind: DocumentKind;
  expertiseId?: string;
  expertiseNumber?: string;
  contractNumber?: string;
  validUntil: string;
};

export const documents: Document[] = [
  {
    id: "doc-001",
    name: 'Заключение ЭПБ №ЭПБ-2023/0912',
    kind: "Заключение ЭПБ",
    expertiseId: "exp-2401",
    expertiseNumber: "ЭПБ-2026/2401",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(-22)),
  },
  {
    id: "doc-002",
    name: "Акт готовности по газопроводу Г-12",
    kind: "Акт готовности",
    expertiseId: "exp-2404",
    expertiseNumber: "ЭПБ-2026/2404",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(-9)),
  },
  {
    id: "doc-003",
    name: "Протокол обследования Т-204",
    kind: "Протокол обследования",
    expertiseId: "exp-2405",
    expertiseNumber: "ЭПБ-2026/2405",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(-4)),
  },
  {
    id: "doc-004",
    name: "Программа ЭПБ по эстакаде №3",
    kind: "Программа ЭПБ",
    expertiseId: "exp-2407",
    expertiseNumber: "ЭПБ-2026/2407",
    contractNumber: "ЭПБ-024/2026",
    validUntil: fmt(addDays(-1)),
  },
  {
    id: "doc-005",
    name: "Заключение ЭПБ по РВС-2000",
    kind: "Заключение ЭПБ",
    expertiseId: "exp-2406",
    expertiseNumber: "ЭПБ-2026/2406",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(3)),
  },
  {
    id: "doc-006",
    name: "Акт готовности по компрессору К-501",
    kind: "Акт готовности",
    expertiseId: "exp-2408",
    expertiseNumber: "ЭПБ-2026/2408",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(8)),
  },
  {
    id: "doc-007",
    name: "Протокол обследования сосуда В-101/2",
    kind: "Протокол обследования",
    expertiseId: "exp-2401",
    expertiseNumber: "ЭПБ-2026/2401",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(12)),
  },
  {
    id: "doc-008",
    name: "Заключение ЭПБ по котлу ДКВр-10/13",
    kind: "Заключение ЭПБ",
    expertiseId: "exp-2403",
    expertiseNumber: "ЭПБ-2026/2403",
    contractNumber: "ЭПБ-024/2026",
    validUntil: fmt(addDays(22)),
  },
  {
    id: "doc-009",
    name: "Программа ЭПБ по трубопроводу Т-204",
    kind: "Программа ЭПБ",
    expertiseId: "exp-2405",
    expertiseNumber: "ЭПБ-2026/2405",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(28)),
  },
  {
    id: "doc-010",
    name: "Акт готовности по РВС-5000",
    kind: "Акт готовности",
    expertiseId: "exp-2402",
    expertiseNumber: "ЭПБ-2026/2402",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(35)),
  },
  {
    id: "doc-011",
    name: "Протокол обследования эстакады №3",
    kind: "Протокол обследования",
    expertiseId: "exp-2407",
    expertiseNumber: "ЭПБ-2026/2407",
    contractNumber: "ЭПБ-024/2026",
    validUntil: fmt(addDays(38)),
  },
  {
    id: "doc-012",
    name: "Заключение ЭПБ по компрессору К-501",
    kind: "Заключение ЭПБ",
    expertiseId: "exp-2408",
    expertiseNumber: "ЭПБ-2026/2408",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(55)),
  },
  {
    id: "doc-013",
    name: "Акт готовности по газопроводу Г-12 (повторный)",
    kind: "Акт готовности",
    expertiseId: "exp-2404",
    expertiseNumber: "ЭПБ-2026/2404",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(72)),
  },
  {
    id: "doc-014",
    name: "Заключение ЭПБ по трубопроводу Т-204",
    kind: "Заключение ЭПБ",
    expertiseId: "exp-2405",
    expertiseNumber: "ЭПБ-2026/2405",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(95)),
  },
  {
    id: "doc-015",
    name: "Протокол обследования РВС-2000",
    kind: "Протокол обследования",
    expertiseId: "exp-2406",
    expertiseNumber: "ЭПБ-2026/2406",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(120)),
  },
  {
    id: "doc-016",
    name: "Заключение ЭПБ по эстакаде №3",
    kind: "Заключение ЭПБ",
    expertiseId: "exp-2407",
    expertiseNumber: "ЭПБ-2026/2407",
    contractNumber: "ЭПБ-024/2026",
    validUntil: fmt(addDays(150)),
  },
  {
    id: "doc-017",
    name: "Программа ЭПБ по сосуду В-101/2",
    kind: "Программа ЭПБ",
    expertiseId: "exp-2401",
    expertiseNumber: "ЭПБ-2026/2401",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(180)),
  },
  {
    id: "doc-018",
    name: "Акт готовности по РВС-2000 (повторный)",
    kind: "Акт готовности",
    expertiseId: "exp-2406",
    expertiseNumber: "ЭПБ-2026/2406",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(210)),
  },
  {
    id: "doc-019",
    name: "Заключение ЭПБ №ЭПБ-2024/1102",
    kind: "Заключение ЭПБ",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(260)),
  },
  {
    id: "doc-020",
    name: "Протокол обследования котла ДКВр-10/13",
    kind: "Протокол обследования",
    expertiseId: "exp-2403",
    expertiseNumber: "ЭПБ-2026/2403",
    contractNumber: "ЭПБ-024/2026",
    validUntil: fmt(addDays(310)),
  },
  {
    id: "doc-021",
    name: "Заключение ЭПБ №ЭПБ-2024/1144",
    kind: "Заключение ЭПБ",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(340)),
  },
  {
    id: "doc-022",
    name: "Программа ЭПБ по компрессору К-501",
    kind: "Программа ЭПБ",
    expertiseId: "exp-2408",
    expertiseNumber: "ЭПБ-2026/2408",
    contractNumber: "ЭПБ-012/2026",
    validUntil: fmt(addDays(380)),
  },
  {
    id: "doc-023",
    name: "Акт готовности №АГ-2024/118",
    kind: "Акт готовности",
    contractNumber: "ЭПБ-024/2026",
    validUntil: fmt(addDays(420)),
  },
  {
    id: "doc-024",
    name: "Заключение ЭПБ №ЭПБ-2025/1904",
    kind: "Заключение ЭПБ",
    contractNumber: "ЭПБ-018/2026",
    validUntil: fmt(addDays(480)),
  },
];

const VALIDITY_ORDER: DocumentValidity[] = [
  "Действителен",
  "Срок истекает через 40 дней",
  "Срок истекает через 14 дней",
  "Срок истек",
];

export const documentValidityDistribution: { status: DocumentValidity; count: number }[] =
  VALIDITY_ORDER.map((status) => ({ status, count: 0 }));

export const employeeLoad: { name: string; open: number; done: number }[] = [
  { name: "Иванов А.П.", open: 7, done: 12 },
  { name: "Петрова Е.С.", open: 4, done: 9 },
  { name: "Соколов Д.А.", open: 3, done: 8 },
  { name: "Кузнецова М.В.", open: 2, done: 5 },
  { name: "Морозов И.К.", open: 1, done: 4 },
];

export const expiringSoon = [
  {
    id: "exp-2401",
    kind: "expertise" as const,
    title: "Сосуд В-101/2 — подача в РТН",
    date: addDays(2),
    severity: "urgent" as const,
    contractNumber: "ЭПБ-018/2026",
  },
  {
    id: "exp-2406",
    kind: "expertise" as const,
    title: "РВС-2000 — пакет в РТН",
    date: addDays(1),
    severity: "urgent" as const,
    contractNumber: "ЭПБ-018/2026",
  },
  {
    id: "c-2026-012",
    kind: "contract" as const,
    title: "Окончание договора ТюменьТрансГаз",
    date: addDays(12),
    severity: "warning" as const,
    contractNumber: "ЭПБ-012/2026",
  },
  {
    id: "c-2026-009",
    kind: "contract" as const,
    title: "Окончание договора Нефтегаз-Сибирь (приостановлен)",
    date: addDays(20),
    severity: "warning" as const,
    contractNumber: "ЭПБ-009/2026",
  },
  {
    id: "dev-501",
    kind: "device" as const,
    title: 'Контрольная дата ТУ "Котёл ДКВр-10/13"',
    date: addDays(14),
    severity: "info" as const,
    contractNumber: "ЭПБ-024/2026",
  },
];

export const recentActivity = [
  {
    id: "a-1",
    type: "status",
    text: "Экспертиза ЭПБ-2026/2405 «Трубопровод Т-204» зарегистрирована в РТН",
    at: iso(addDays(0)),
  },
  {
    id: "a-2",
    type: "create",
    text: "Создана экспертиза ЭПБ-2026/2407 «Эстакада слива №3»",
    at: iso(addDays(0)),
  },
  {
    id: "a-3",
    type: "reject",
    text: "Получен отказ РТН по экспертизе ЭПБ-2026/2404 «Газопровод Г-12»",
    at: iso(addDays(-1)),
  },
  {
    id: "a-4",
    type: "doc",
    text: 'Сформирован акт готовности по договору ЭПБ-018/2026',
    at: iso(addDays(-1)),
  },
  {
    id: "a-5",
    type: "comment",
    text: "@Петрова прокомментировала экспертизу ЭПБ-2026/2403 «Котёл ДКВр-10/13»",
    at: iso(addDays(-2)),
  },
  {
    id: "a-6",
    type: "task",
    text: "Завершена задача «Проверка комплектности документации»",
    at: iso(addDays(-2)),
  },
];

export const notifications: {
  id: string;
  kind: NotificationKind;
  title: string;
  description?: string;
  at: string;
  read: boolean;
}[] = [
  {
    id: "n-1",
    kind: "task",
    title: 'Назначена задача «Согласовать программу обследования»',
    description: "ЭПБ-2026/2402 • Срок: сегодня",
    at: iso(addDays(0)),
    read: false,
  },
  {
    id: "n-2",
    kind: "overdue",
    title: 'Просрочена задача «Доработать заключение по Г-12»',
    description: "ЭПБ-2026/2404 • Просрочка: 1 день",
    at: iso(addDays(0)),
    read: false,
  },
  {
    id: "n-3",
    kind: "deadline",
    title: 'Через 5 дней: подача пакета в РТН (РВС-2000)',
    description: "ЭПБ-2026/2406 • ЭПБ-018/2026",
    at: iso(addDays(-1)),
    read: false,
  },
  {
    id: "n-4",
    kind: "mention",
    title: "@Иванов — упомянули в комментарии",
    description: 'ЭПБ-2026/2403 «Котёл ДКВр-10/13»',
    at: iso(addDays(-1)),
    read: true,
  },
  {
    id: "n-5",
    kind: "control",
    title: 'Контрольная дата ТУ «Котёл ДКВр-10/13» через 14 дней',
    description: "ЭПБ-024/2026",
    at: iso(addDays(-2)),
    read: true,
  },
  {
    id: "n-6",
    kind: "status",
    title: "Статус экспертизы изменён: «Зарегистрировано в РТН»",
    description: "ЭПБ-2026/2405 • Трубопровод Т-204",
    at: iso(addDays(-2)),
    read: true,
  },
];

export const searchIndex: SearchEntry[] = [
  ...organizations.map((o) => ({
    id: o.id,
    kind: "organization" as const,
    title: o.name,
    subtitle: `ИНН ${o.inn} • ОПО: ${o.opoCount}, ТУ: ${o.devicesCount}`,
    href: `/organizations/${o.id}`,
    group: "Организации",
  })),
  ...contracts.map((c) => ({
    id: c.id,
    kind: "contract" as const,
    title: c.number,
    subtitle: `${c.organizationName} • ${c.status}`,
    href: `/contracts/${c.id}`,
    group: "Договоры",
  })),
  ...expertiseList.map((e) => ({
    id: e.id,
    kind: "expertise" as const,
    title: e.number,
    subtitle: `${e.subjectName} • ${e.status}`,
    href: `/expertise/${e.id}`,
    group: "Экспертизы",
  })),
  ...myTasks.slice(0, 3).map((t) => ({
    id: t.id,
    kind: "task" as const,
    title: t.title,
    subtitle: `${t.expertiseNumber} • ${t.dueDate}`,
    href: `/tasks/${t.id}`,
    group: "Задачи",
  })),
  {
    id: "ev-1",
    kind: "event",
    title: "Срок подачи в РТН: Сосуд В-101/2",
    subtitle: "через 2 дня • ЭПБ-2026/2401",
    href: "/calendar",
    group: "Календарь",
  },
  {
    id: "npd-1",
    kind: "npd",
    title: "ФНП «Правила промышленной безопасности при использовании оборудования, работающего под избыточным давлением»",
    subtitle: "Приказ Ростехнадзора № 536 • Действует",
    href: "/npd/npd-1",
    group: "НПД",
  },
];

/** Расширенные данные для карточки экспертизы. */
export const expertiseDetail = {
  id: "exp-2401",
  number: "ЭПБ-2026/2401",
  contractId: "c-2026-018",
  contractNumber: "ЭПБ-018/2026",
  organization: {
    id: "org-1",
    name: 'АО "Нефтегаз-Сибирь"',
    inn: "7701234567",
    opoName: 'ОПО «Установка подготовки нефти "Московская"»',
    opoRegNumber: "А-44-0247-2021",
    opoClass: "I класс",
  },
  subject: {
    type: "ТУ" as const,
    name: "Сосуд В-101/2",
    manufacturer: 'АО "Уралхиммаш"',
    serial: "В-101/2-2020-1488",
    model: "В-101/2",
    year: 2020,
    pressure: "1.6 МПа",
    temperature: "+200 °C",
    medium: "Нефть, попутный газ",
    volume: "50 м³",
  },
  status: "На рассмотрении в РТН" as ExpertiseStatus,
  type: "Экспертиза промышленной безопасности технического устройства",
  createdAt: "12.02.2026",
  submittedToRtnAt: "01.03.2026",
  responsibleExpert: {
    name: "Иванов Алексей Петрович",
    role: "Ответственный эксперт",
    certificate: "ЭПБ-44-2024-118",
    area: "Оборудование, работающее под избыточным давлением",
  },
  experts: [
    {
      name: "Иванов Алексей Петрович",
      role: "Ответственный эксперт",
      certificate: "ЭПБ-44-2024-118",
    },
    {
      name: "Морозов Иван Константинович",
      role: "Эксперт",
      certificate: "ЭПБ-44-2023-089",
    },
  ],
  specialists: [
    { name: "Лазарев В.А.", role: "Специалист по ВИК" },
    { name: "Орлов С.И.", role: "Специалист по УЗК" },
  ],
  rtnAttempts: [
    {
      n: 1,
      preparedAt: "25.02.2026",
      sentAt: "01.03.2026",
      state: "На рассмотрении" as const,
      result: null,
      registeredAt: null,
      registryNumber: null,
    },
  ],
  consideredDocs: [
    { id: "d-1", name: "Паспорт сосуда В-101/2", status: "Финальный" },
    { id: "d-2", name: "Акт монтажа от 15.04.2020", status: "Финальный" },
    { id: "d-3", name: 'Заключение ЭПБ №ЭПБ-2023/0912', status: "Архивный" },
    { id: "d-4", name: "Технологический регламент", status: "Рабочий" },
  ],
  npd: [
    { id: "npd-536", short: "ФНП-536", title: "Правила промышленной безопасности при использовании оборудования, работающего под избыточным давлением" },
    { id: "npd-533", short: "ФНП-533", title: "Правила промышленной безопасности складов нефти и нефтепродуктов" },
    { id: "gost-34347", short: "ГОСТ 34347-2017", title: "Сосуды и аппараты стальные сварные. Общие технические условия" },
  ],
  tasks: myTasks.filter((t) => t.expertiseId === "exp-2401" || t.expertiseId === "exp-2406"),
  timeline: [
    { date: "12.02.2026", event: "Экспертиза создана" },
    { date: "18.02.2026", event: "Назначены эксперты и специалисты" },
    { date: "22.02.2026", event: "Программа ЭПБ согласована" },
    { date: "26.02.2026", event: "Проведено обследование, выполнены ВИК и УЗК" },
    { date: "27.02.2026", event: "Подготовлен проект заключения" },
    { date: "28.02.2026", event: "Внутреннее согласование пройдено" },
    { date: "01.03.2026", event: "Заключение направлено в РТН (попытка №1)" },
  ],
};

function parseRuDate(s: string): Date {
  const [d, m, y] = s.split(".");
  return new Date(Number(y), Number(m) - 1, Number(d));
}

const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
const expiredExpertise = expertiseList.filter(
  (e) => e.nextControl && parseRuDate(e.nextControl).getTime() < todayMidnight.getTime(),
);

(function computeDocumentValidity() {
  const buckets = new Map<DocumentValidity, number>(
    VALIDITY_ORDER.map((s) => [s, 0]),
  );
  for (const d of documents) {
    const diffDays = Math.floor(
      (parseRuDate(d.validUntil).getTime() - todayMidnight.getTime()) / 86_400_000,
    );
    let bucket: DocumentValidity;
    if (diffDays < 0) bucket = "Срок истек";
    else if (diffDays <= 14) bucket = "Срок истекает через 14 дней";
    else if (diffDays <= 40) bucket = "Срок истекает через 40 дней";
    else bucket = "Действителен";
    buckets.set(bucket, (buckets.get(bucket) ?? 0) + 1);
  }
  for (const row of documentValidityDistribution) {
    row.count = buckets.get(row.status) ?? 0;
  }
})();

export const dashboardKpis = {
  contractsActive: 4,
  contractsActiveSum: 15_900_000,
  contractsEndingSoon: 2,
  expertiseInProgress: 6,
  expertiseAtRtn: 1,
  expertiseRejected: 1,
  myTasksToday: 3,
  myTasksOverdue: 1,
  documentsExpired: expiredExpertise.length,
  organizationsCount: organizations.length,
  opoCount: organizations.reduce((s, o) => s + o.opoCount, 0),
  devicesCount: organizations.reduce((s, o) => s + o.devicesCount, 0),
  contractsTotalCount: contracts.length,
  contractsCompletedCount: contracts.filter((c) => c.status === "Завершён").length,
  expertiseTotalCount: expertiseList.length,
  expertiseRegisteredCount: expertiseList.filter((e) => e.status === "Зарегистрировано").length,
  expertiseCompletedCount: expertiseList.filter((e) => e.status === "Завершено").length,
  tasksTotal: 38,
  tasksDone: 27,
};

export function formatMoney(value: number): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatMoneyShort(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1).replace(".0", "")} млн ₽`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(0)} тыс ₽`;
  }
  return `${value} ₽`;
}
