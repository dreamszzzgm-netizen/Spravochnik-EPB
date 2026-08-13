"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Search } from "lucide-react";

import { mainNav, settingsNav } from "@/components/nav-config";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

const navigationItems = [...mainNav, ...settingsNav];

export function CommandSearch() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-input bg-muted/40 px-3 text-sm text-muted-foreground transition-colors hover:bg-muted"
      >
        <Search className="h-4 w-4" />
        <span className="flex-1 text-left">Перейти к разделу…</span>
        <kbd className="pointer-events-none hidden h-5 select-none items-center gap-0.5 rounded border border-border bg-background px-1.5 font-mono text-[10px] font-medium sm:inline-flex">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Введите название раздела…" />
        <CommandList>
          <CommandEmpty>Раздел не найден</CommandEmpty>
          <CommandGroup heading="Разделы системы">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              return (
                <CommandItem
                  key={item.href}
                  value={`${item.label} ${item.description ?? ""}`}
                  onSelect={() => {
                    router.push(item.href);
                    setOpen(false);
                  }}
                  className="flex items-center gap-3"
                >
                  <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-sm">{item.label}</span>
                    {item.description && (
                      <span className="truncate text-xs text-muted-foreground">
                        {item.description}
                      </span>
                    )}
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </CommandItem>
              );
            })}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
