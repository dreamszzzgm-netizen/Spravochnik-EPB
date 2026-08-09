"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Building2,
  FileText,
  ShieldCheck,
  ListTodo,
  Search,
  Calendar,
  BookOpen,
  ArrowRight,
} from "lucide-react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { searchIndex, type SearchEntry } from "@/lib/mock-data";

const iconByKind: Record<SearchEntry["kind"], React.ComponentType<{ className?: string }>> = {
  organization: Building2,
  contract: FileText,
  expertise: ShieldCheck,
  task: ListTodo,
  event: Calendar,
  npd: BookOpen,
};

export function CommandSearch() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const grouped = React.useMemo(() => {
    const groups: Record<string, SearchEntry[]> = {};
    for (const item of searchIndex) {
      const key = item.group;
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    }
    return groups;
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-input bg-muted/40 px-3 text-sm text-muted-foreground transition-colors hover:bg-muted"
      >
        <Search className="h-4 w-4" />
        <span className="flex-1 text-left">Поиск по системе…</span>
        <kbd className="pointer-events-none hidden h-5 select-none items-center gap-0.5 rounded border border-border bg-background px-1.5 font-mono text-[10px] font-medium sm:inline-flex">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Введите название организации, договора, экспертизы…" />
        <CommandList>
          <CommandEmpty>Ничего не найдено</CommandEmpty>
          {Object.entries(grouped).map(([group, items]) => (
            <CommandGroup key={group} heading={group}>
              {items.map((item) => {
                const Icon = iconByKind[item.kind];
                return (
                  <CommandItem
                    key={item.id}
                    value={`${item.title} ${item.subtitle ?? ""}`}
                    onSelect={() => {
                      router.push(item.href);
                      setOpen(false);
                    }}
                    className="flex items-center gap-3"
                  >
                    <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="flex flex-1 flex-col overflow-hidden">
                      <span className="truncate text-sm">{item.title}</span>
                      {item.subtitle && (
                        <span className="truncate text-xs text-muted-foreground">
                          {item.subtitle}
                        </span>
                      )}
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                    {item.shortcut && <CommandShortcut>{item.shortcut}</CommandShortcut>}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          ))}
        </CommandList>
      </CommandDialog>
    </>
  );
}
