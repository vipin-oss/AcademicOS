import { NextResponse, type NextRequest } from "next/server";

/** Route guard (final release): protected routes require the session
 * cookie (set whenever tokens are stored); auth pages redirect away when
 * a session already exists. The cookie is a presence flag — real
 * verification happens client-side via /auth/me + the refresh interceptor. */

const PROTECTED_PREFIXES = [
  "/assistant",
  "/committees",
  "/documents",
  "/events",
  "/faculty",
  "/finance",
  "/intake",
  "/objects",
  "/productivity",
  "/publications",
  "/reports",
  "/research",
  "/search",
  "/settings",
  "/students",
  "/teaching",
];

const AUTH_PAGES = ["/login", "/register", "/forgot-password", "/reset-password"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.get("academicos.session")?.value === "1";

  if (pathname === "/") {
    return hasSession
      ? NextResponse.next()
      : NextResponse.redirect(new URL("/login", request.url));
  }

  if (PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    if (!hasSession) {
      const url = new URL("/login", request.url);
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  if (AUTH_PAGES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    if (hasSession) return NextResponse.redirect(new URL("/", request.url));
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/",
    "/assistant/:path*",
    "/committees/:path*",
    "/documents/:path*",
    "/events/:path*",
    "/faculty/:path*",
    "/finance/:path*",
    "/intake/:path*",
    "/objects/:path*",
    "/productivity/:path*",
    "/publications/:path*",
    "/reports/:path*",
    "/research/:path*",
    "/search/:path*",
    "/settings/:path*",
    "/students/:path*",
    "/teaching/:path*",
    "/login",
    "/register",
    "/forgot-password",
    "/reset-password",
  ],
};
