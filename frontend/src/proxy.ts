import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  if (pathname === "/organizations/new") {
    return NextResponse.rewrite(new URL("/organizations/new-hardened", request.url));
  }

  if (/^\/organizations\/[^/]+\/edit$/.test(pathname)) {
    const id = pathname.split("/")[2];
    return NextResponse.rewrite(new URL(`/organizations/${id}/edit-hardened`, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/organizations/new", "/organizations/:id/edit"],
};
