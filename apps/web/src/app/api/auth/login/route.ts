import { NextResponse } from "next/server";
import { AuthRequestError, requestAuthToken } from "@/lib/auth/api";
import { AUTH_COOKIE_MAX_AGE_SECONDS, AUTH_COOKIE_NAME } from "@/lib/auth/constants";

function setSessionCookie(response: NextResponse, token: string) {
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: AUTH_COOKIE_MAX_AGE_SECONDS,
  });
}

export async function POST(request: Request) {
  let body: { email?: string; password?: string };
  try {
    body = (await request.json()) as { email?: string; password?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const email = body.email?.trim() ?? "";
  const password = body.password ?? "";
  if (!email || !password) {
    return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
  }

  try {
    const tokenResponse = await requestAuthToken("/auth/login", { email, password });
    const response = NextResponse.json({
      ok: true,
      user_id: tokenResponse.user_id,
      email: tokenResponse.email,
    });
    setSessionCookie(response, tokenResponse.access_token);
    return response;
  } catch (error) {
    if (error instanceof AuthRequestError) {
      return NextResponse.json({ error: error.message }, { status: error.status || 401 });
    }
    return NextResponse.json({ error: "Login failed" }, { status: 500 });
  }
}
