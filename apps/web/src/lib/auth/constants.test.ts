import assert from "node:assert/strict";
import test from "node:test";

import { isProtectedPath } from "./constants.ts";

test("login and register are public", () => {
  assert.equal(isProtectedPath("/login"), false);
  assert.equal(isProtectedPath("/register"), false);
  assert.equal(isProtectedPath("/api/auth/login"), false);
});

test("dashboard surfaces are protected", () => {
  assert.equal(isProtectedPath("/"), true);
  assert.equal(isProtectedPath("/dashboard"), true);
  assert.equal(isProtectedPath("/projects/abc"), true);
  assert.equal(isProtectedPath("/datasets/x"), true);
  assert.equal(isProtectedPath("/experiments/x"), true);
  assert.equal(isProtectedPath("/runs/x/compare"), true);
  assert.equal(isProtectedPath("/traces"), true);
  assert.equal(isProtectedPath("/settings"), true);
});
