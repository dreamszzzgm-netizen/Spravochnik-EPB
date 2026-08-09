import { describe, expect, it } from "vitest";

import { ApiError } from "./errors";
import { backendStatusLabel, organizationStateMessage, userMenuModel } from "./state-models";

describe("integration state models", () => {
  it.each([
    ["checking", "Проверка сервера"],
    ["online", "Сервер в сети"],
    ["offline", "Сервер недоступен"],
  ] as const)("maps health state %s truthfully", (state, label) => {
    expect(backendStatusLabel(state)).toBe(label);
  });

  it("uses only fields provided by the current-user backend DTO", () => {
    expect(userMenuModel(null, false)).toEqual({ username: "Не выполнен вход", secondary: "Требуется авторизация" });
    expect(userMenuModel({ username: "admin", is_superuser: true }, false)).toEqual({ username: "admin", secondary: "Суперпользователь" });
  });

  it.each([
    [null, null, 0, "Загрузка организаций…"],
    [new ApiError(401, "Unauthorized"), [], 0, "Войдите в систему, чтобы увидеть организации."],
    [new ApiError(403, "Forbidden"), [], 0, "У вашей учётной записи нет права organizations.view."],
    [new Error("offline"), [], 0, "Не удалось получить организации от backend."],
    [null, [], 0, "Организации не найдены."],
    [null, [{}], 1, null],
  ])("describes organization loading and error states", (error, organizations, count, message) => {
    expect(organizationStateMessage(error, organizations, count)).toBe(message);
  });
});
