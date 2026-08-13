"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Files } from "lucide-react";

import { OrganizationDocuments } from "../_components/organization-documents";
import { Button } from "@/components/ui/button";

export default function OrganizationDocumentsPage() {
  const id = useParams().id as string;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/organizations/${id}`} aria-label="Назад к карточке организации">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Files className="h-5 w-5" aria-hidden="true" />
            Документы организации
          </h1>
          <p className="text-sm text-muted-foreground">
            Локальные файлы, сроки действия и комплектность карточки организации.
          </p>
        </div>
      </div>

      <OrganizationDocuments organizationId={id} />
    </div>
  );
}
