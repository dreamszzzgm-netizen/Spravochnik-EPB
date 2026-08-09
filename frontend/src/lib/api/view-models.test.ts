import { describe, expect, it } from "vitest";

import { organizationName, userInitials } from "./view-models";

describe("API view-model adapters", () => {
  it("prefers an organization short name without inventing missing fields", () => {
    expect(organizationName({ short_name: "ООО Альфа", legal_name: "ООО Альфа Эксперт" })).toBe(
      "ООО Альфа",
    );
    expect(organizationName({ short_name: null, legal_name: "ООО Альфа Эксперт" })).toBe(
      "ООО Альфа Эксперт",
    );
  });

  it("derives safe initials from the backend username", () => {
    expect(userInitials("alexey.ivanov")).toBe("AI");
    expect(userInitials("admin")).toBe("AD");
  });
});
