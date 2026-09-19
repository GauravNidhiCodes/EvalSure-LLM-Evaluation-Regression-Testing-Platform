export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function shortId(id: string, size = 8): string {
  return id.length <= size ? id : `${id.slice(0, size)}…`;
}

export function formatScore(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(4);
  }
  if (typeof value === "string") {
    const n = Number(value);
    if (Number.isFinite(n)) return n.toFixed(4);
  }
  return "—";
}

export function previewJson(value: unknown, max = 80): string {
  try {
    const text = JSON.stringify(value);
    if (!text) return "—";
    return text.length > max ? `${text.slice(0, max)}…` : text;
  } catch {
    return String(value);
  }
}
