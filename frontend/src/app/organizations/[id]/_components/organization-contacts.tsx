"use client";

import { useEffect, useState } from "react";
import { Check, Plus, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  createOrganizationContact,
  deleteOrganizationContact,
  getOrganizationContacts,
} from "@/lib/api/resources";
import type { ContactType, OrganizationContactResponse } from "@/lib/api/types";
import { contactTypeLabel } from "@/lib/api/view-models";
import { useCan } from "@/lib/auth";

const CONTACT_TYPES: ContactType[] = [
  "director",
  "chief_engineer",
  "pb_specialist",
  "accountant",
  "other",
];

interface ContactFormData {
  contact_type: ContactType;
  full_name: string;
  position: string;
  phone: string;
  email: string;
  is_primary: boolean;
}

function ContactCard({
  contact,
  onDelete,
  canManage,
}: {
  contact: OrganizationContactResponse;
  onDelete: (id: string) => void;
  canManage: boolean;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{contact.full_name}</span>
          {contact.is_primary && (
            <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
              Основной
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {contactTypeLabel(contact.contact_type)}
          {contact.position ? ` · ${contact.position}` : ""}
        </p>
        {(contact.phone || contact.email) && (
          <p className="mt-1 text-xs text-muted-foreground">
            {[contact.phone, contact.email].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>
      {canManage && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
          onClick={() => onDelete(contact.id)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

export function OrganizationContacts({ organizationId }: { organizationId: string }) {
  const [contacts, setContacts] = useState<OrganizationContactResponse[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ContactFormData>({
    contact_type: "director",
    full_name: "",
    position: "",
    phone: "",
    email: "",
    is_primary: false,
  });
  const [pending, setPending] = useState(false);
  const canManage = useCan("organizations.manage_contacts");

  useEffect(() => {
    getOrganizationContacts(organizationId)
      .then(setContacts)
      .catch(() => setContacts([]));
  }, [organizationId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.full_name.trim()) return;
    setPending(true);
    try {
      const created = await createOrganizationContact(organizationId, {
        contact_type: form.contact_type,
        full_name: form.full_name.trim(),
        position: form.position.trim() || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        is_primary: form.is_primary,
      });
      setContacts((prev) => (prev ? [...prev, created] : [created]));
      setShowForm(false);
      setForm({
        contact_type: "director",
        full_name: "",
        position: "",
        phone: "",
        email: "",
        is_primary: false,
      });
    } catch {
      /* ignore */
    } finally {
      setPending(false);
    }
  };

  const handleDelete = async (contactId: string) => {
    try {
      await deleteOrganizationContact(organizationId, contactId);
      setContacts((prev) =>
        prev ? prev.filter((c) => c.id !== contactId) : prev,
      );
    } catch {
      /* ignore */
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Контакты</CardTitle>
        {canManage && (
          <Button variant="outline" size="sm" onClick={() => setShowForm(!showForm)}>
            {showForm ? (
              <X className="mr-1 h-4 w-4" />
            ) : (
              <Plus className="mr-1 h-4 w-4" />
            )}
            {showForm ? "Отмена" : "Добавить"}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {showForm && (
          <form onSubmit={handleCreate} className="space-y-3 rounded-lg border p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="contact_type">Тип контакта</Label>
                <Select
                  value={form.contact_type}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, contact_type: v as ContactType }))
                  }
                >
                  <SelectTrigger id="contact_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CONTACT_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {contactTypeLabel(t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="full_name">ФИО *</Label>
                <Input
                  id="full_name"
                  value={form.full_name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, full_name: e.target.value }))
                  }
                  required
                  maxLength={255}
                  disabled={pending}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="position">Должность</Label>
                <Input
                  id="position"
                  value={form.position}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, position: e.target.value }))
                  }
                  maxLength={255}
                  disabled={pending}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="phone">Телефон</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={form.phone}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, phone: e.target.value }))
                  }
                  maxLength={64}
                  disabled={pending}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, email: e.target.value }))
                  }
                  maxLength={320}
                  disabled={pending}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_primary}
                onChange={(e) =>
                  setForm((f) => ({ ...f, is_primary: e.target.checked }))
                }
                disabled={pending}
              />
              Основной контакт
            </label>
            <div className="flex gap-2">
              <Button
                type="submit"
                size="sm"
                disabled={pending || !form.full_name.trim()}
              >
                <Check className="mr-1 h-4 w-4" />
                Сохранить
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowForm(false)}
              >
                Отмена
              </Button>
            </div>
          </form>
        )}

        {contacts === null ? (
          <p className="text-sm text-muted-foreground">Загрузка контактов...</p>
        ) : contacts.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Нет контактов
          </p>
        ) : (
          <div className="space-y-2">
            {contacts.map((c) => (
              <ContactCard
                key={c.id}
                contact={c}
                onDelete={handleDelete}
                canManage={canManage}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
