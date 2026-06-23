export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const DAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export function toIsoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function fromIsoDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function mondayOf(date = new Date()) {
  const result = new Date(date);
  const day = result.getDay();
  const difference = day === 0 ? -6 : 1 - day;
  result.setDate(result.getDate() + difference);
  result.setHours(0, 0, 0, 0);
  return result;
}

export function shiftWeek(weekStart, amount) {
  const date = fromIsoDate(weekStart);
  date.setDate(date.getDate() + amount * 7);
  return toIsoDate(date);
}

export function weekDates(weekStart) {
  const first = fromIsoDate(weekStart);
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(first);
    date.setDate(first.getDate() + index);
    return toIsoDate(date);
  });
}

export function formatWeekRange(weekStart) {
  const dates = weekDates(weekStart);
  const start = fromIsoDate(dates[0]);
  const end = fromIsoDate(dates[6]);
  const sameMonth = start.getMonth() === end.getMonth();
  const startText = start.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(start.getFullYear() !== end.getFullYear() ? { year: "numeric" } : {}),
  });
  const endText = end.toLocaleDateString(undefined, {
    month: sameMonth ? undefined : "short",
    day: "numeric",
    year: "numeric",
  });
  return `${startText} – ${endText}`;
}

export function formatDate(value, options = {}) {
  if (!value) return "";
  return fromIsoDate(value).toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
    ...options,
  });
}

export function formatRole(role) {
  if (role === "shift_lead") return "Shift Lead";
  if (role === "gm") return "GM";
  return "Employee";
}

export function formatClock(value) {
  if (!value) return "Any time";
  const [hourValue, minute] = value.split(":").map(Number);
  const suffix = hourValue >= 12 ? "PM" : "AM";
  const hour = hourValue % 12 || 12;
  return `${hour}:${String(minute).padStart(2, "0")} ${suffix}`;
}

export function formatRange(start, end) {
  if (!start && !end) return "Full day";
  return `${formatClock(start)} – ${formatClock(end)}`;
}

export function statusLabel(status) {
  if (status === "needs_review") return "Needs Review";
  if (status === "published") return "Published";
  return "Draft";
}

export function confirmOncePerSession(key, message) {
  const storageKey = `scheduler.confirmed.${key}`;
  if (sessionStorage.getItem(storageKey) === "1") return true;
  const approved = window.confirm(message);
  if (approved) sessionStorage.setItem(storageKey, "1");
  return approved;
}
