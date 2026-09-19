import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { AUTH_COOKIE_NAME, isProtectedPath } from "@/lib/auth/constants";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (!isProtectedPath(pathname)) {
    return NextResponse.next();
  }

  const cookieToken = request.cookies.get(AUTH_COOKIE_NAME)?.value?.trim();
  const envToken = process.env.EVALSURE_ACCESS_TOKEN?.trim();
  if (cookieToken || envToken) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/",
    "/dashboard/:path*",
    "/projects/:path*",
    "/datasets/:path*",
    "/experiments/:path*",
    "/runs/:path*",
    "/traces/:path*",
    "/settings/:path*",
  ],
};
