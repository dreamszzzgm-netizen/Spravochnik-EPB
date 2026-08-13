"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";

import { OrganizationFormFields } from "@/components/organization-form-fields";
import { OrganizationSmartImport } from "@/components/organization-smart-import";
import { useOrganizationForm } from "@/components/use-organization-form";
import { useOrganizationLoad } from "@/components/use-organization-load";
import { useOrganizationSave } from "@/components/use-organization-save";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HardenedEditOrganizationPage() {
  const id = useParams().id as string;
  const form = useOrganizationForm();
  const load = useOrganizationLoad(id, form.setValues);
  const save = useOrganizationSave(id);

  if (load.loading) {
    return <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-label="Загрузка" /></div>;
  }
  if (load.loadError) {
    return <div className="py-20 text-center"><p className="text-sm text-destructive">{load.loadError}</p><Button variant="outline" className="mt-4" asChild><Link href="/organizations">Вернуться к списку</Link></Button></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild><Link href={`/organizations/${id}`} aria-label="Назад к карточке"><ArrowLeft className="h-4 w-4" /></Link></Button>
        <h1 className="text-2xl font-semibold tracking-tight">Редактирование организации</h1>
      </div>
      <OrganizationSmartImport disabled={save.pending} onApply={form.applyImport} />
      <form onSubmit={(event) => { event.preventDefault(); void save.save(form.values); }}>
        <Card>
          <CardHeader><CardTitle>Основные сведения</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <OrganizationFormFields values={form.values} disabled={save.pending} setText={form.setText} setType={form.setType} setIdentifier={form.setIdentifier} />
            {save.error && <p className="text-sm text-destructive" role="alert">{save.error}</p>}
            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={save.pending}>{save.pending ? "Сохранение…" : "Сохранить изменения"}</Button>
              <Button type="button" variant="outline" asChild><Link href={`/organizations/${id}`}>Отмена</Link></Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
