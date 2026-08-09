import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="relative">
        <svg
          width="28"
          height="32"
          viewBox="0 0 28 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
          className="text-primary"
        >
          <path
            d="M14 1.5L26 5.5V14C26 22.5 20.5 28.5 14 30.5C7.5 28.5 2 22.5 2 14V5.5L14 1.5Z"
            fill="currentColor"
            className="opacity-15"
          />
          <path
            d="M14 1.5L26 5.5V14C26 22.5 20.5 28.5 14 30.5C7.5 28.5 2 22.5 2 14V5.5L14 1.5Z"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
          <path
            d="M8.5 10.5L11.2 21.5L14 14.5L16.8 21.5L19.5 10.5"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <div className="flex flex-col leading-none">
        <span className="text-sm font-semibold tracking-tight text-foreground">
          Справочник ЭПБ
        </span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Экспертная организация
        </span>
      </div>
    </div>
  );
}
