"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { OrganizationFormFields } from "@/components/organization-form-fields";
import { OrganizationSmartImport } from "@/components/organization-smart-import";
import { useOrganizationForm } from "@/components/use-organization-form";
import { useOrganizationSave } from "@/components/use-organization-save";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HardenedNewOrganizationPage() {
  const form = useOrganizationForm();
  const save = useOrganizationSave();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/organizations" aria-label="Назад к организациям"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Новая организация</h1>
      </div>
      <OrganizationSmartImport disabled={save.pending} onApply={form.applyImport} />
      <form onSubmit={(event) => { event.preventDefault(); void save.save(form.values); }}>
        <Card>
          <CardHeader><CardTitle>Основные сведения</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <OrganizationFormFields values={form.values} disabled={save.pending} setText={form.setText} setType={form.setType} setIdentifier={form.setIdentifier} />
            {save.error && <p className="text-sm text-destructive" role="alert">{save.error}</p>}
            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={save.pending}>{save.pending ? "Создание…" : "Создать организацию"}</Button>
              <Button type="button" variant="outline" asChild><Link href="/organizations">Отмена</Link></Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
