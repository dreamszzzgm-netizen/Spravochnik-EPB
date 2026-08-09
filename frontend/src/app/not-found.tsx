import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-foreground mb-4">404</h1>
        <p className="text-xl text-muted-foreground mb-4">Страница не найдена</p>
        <Link
          href="/"
          className="text-primary hover:text-primary/80 underline"
        >
          Вернуться на главную
        </Link>
      </div>
    </div>
  );
}
