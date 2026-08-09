import { ApiError } from "./errors";

export type BackendState = "checking" | "online" | "offline";

export function backendStatusLabel(state: BackendState): string {
  return state === "online" ? "Сервер в сети" : state === "offline" ? "Сервер недоступен" : "Проверка сервера";
}

export function userMenuModel(
  user: { username: string; is_superuser: boolean } | null,
  unavailable: boolean,
): { username: string; secondary: string } {
  const username = user?.username || (unavailable ? "Сервер недоступен" : "Не выполнен вход");
  const secondary = user?.is_superuser ? "Суперпользователь" : user ? "Профиль backend" : "Требуется авторизация";
  return { username, secondary };
}

export function organizationStateMessage(
  error: unknown,
  organizations: unknown[] | null,
  filteredCount: number,
): string | null {
  if (error instanceof ApiError && error.status === 401) return "Войдите в систему, чтобы увидеть организации.";
  if (error instanceof ApiError && error.status === 403) return "У вашей учётной записи нет права organizations.view.";
  if (error) return "Не удалось получить организации от backend.";
  if (organizations === null) return "Загрузка организаций…";
  if (filteredCount === 0) return "Организации не найдены.";
  return null;
}
