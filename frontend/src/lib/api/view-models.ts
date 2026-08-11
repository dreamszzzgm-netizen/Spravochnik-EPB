export function organizationName(organization: {
  short_name: string | null;
  legal_name: string;
}): string {
  return organization.short_name || organization.legal_name;
}

export function organizationTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    legal_entity: "Юридическое лицо",
    individual_entrepreneur: "Индивидуальный предприниматель",
    branch: "Филиал",
  };
  return labels[type] ?? type;
}

export function contactTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    director: "Директор",
    chief_engineer: "Главный инженер",
    pb_specialist: "Специалист ПБ",
    accountant: "Бухгалтер",
    other: "Прочее",
  };
  return labels[type] ?? type;
}

export function userInitials(username: string): string {
  const parts = username.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  if (parts.length > 1) return parts.slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return username.slice(0, 2).toUpperCase();
}

export function hazardClassLabel(hazardClass: string): string {
  const labels: Record<string, string> = {
    hazard_class_1: "I класс опасности",
    hazard_class_2: "II класс опасности",
    hazard_class_3: "III класс опасности",
    hazard_class_4: "IV класс опасности",
  };
  return labels[hazardClass] ?? hazardClass;
}

export function technicalDeviceTypeLabel(deviceType: string): string {
  const labels: Record<string, string> = {
    pressure_vessel: "Сосуд под давлением",
    pipeline: "Трубопровод",
    lifting_mechanism: "Подъёмное сооружение",
    other: "Другое",
  };
  return labels[deviceType] ?? deviceType;
}

export function buildingTypeLabel(buildingType: string): string {
  const labels: Record<string, string> = {
    industrial: "Производственное",
    warehouse: "Складское",
    administrative: "Административное",
    other: "Другое",
  };
  return labels[buildingType] ?? buildingType;
}
