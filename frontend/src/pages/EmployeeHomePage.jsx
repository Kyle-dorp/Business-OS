import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { formatClock, formatDate, formatWeekRange, shiftWeek, toIsoDate } from "../utils";

function currentMonday() {
  const today = new Date();
  const day = today.getDay();
  today.setDate(today.getDate() + (day === 0 ? -6 : 1 - day));
  return toIsoDate(today);
}

export default function EmployeeHomePage() {
  const [weekStart, setWeekStart] = useState(() => localStorage.getItem("scheduler.employee.week") || currentMonday());
  const [profile, setProfile] = useState(null);
  const [schedule, setSchedule] = useState({ schedule: null, shifts: [] });
  const [error, setError] = useState("");

  useEffect(() => {
    localStorage.setItem("scheduler.employee.week", weekStart);
    Promise.all([api("/my/profile"), api(`/my/schedule?week_start=${weekStart}`)])
      .then(([profileResult, scheduleResult]) => {
        setProfile(profileResult);
        setSchedule(scheduleResult);
      })
      .catch((err) => setError(err.message));
  }, [weekStart]);

  const grouped = useMemo(() => {
    const result = {};
    for (const shift of schedule.shifts || []) (result[shift.date] ||= []).push(shift);
    return result;
  }, [schedule]);

  return (
    <div className="page">
      <div className="employee-hero">
        <div>
          <span className="eyebrow">MY WORKSPACE</span>
          <h1>Hey, {profile?.employee?.name || profile?.user?.username || "there"}.</h1>
          <p>Your published schedule and request status live here.</p>
        </div>
        <div className="employee-week-card">
          <button onClick={() => setWeekStart(shiftWeek(weekStart, -1))}>←</button>
          <div><span>Selected week</span><strong>{formatWeekRange(weekStart)}</strong></div>
          <button onClick={() => setWeekStart(shiftWeek(weekStart, 1))}>→</button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      {!profile?.employee && (
        <section className="empty-state card">
          <h2>Account not linked yet</h2>
          <p>Your manager needs to connect this login to your employee profile.</p>
        </section>
      )}

      {profile?.employee && !schedule.schedule && (
        <section className="empty-state card">
          <div className="empty-icon">◷</div>
          <h2>No published schedule for this week</h2>
          <p>Draft schedules stay private until a manager publishes one.</p>
        </section>
      )}

      {schedule.schedule && (
        <div className="employee-schedule-grid">
          {Object.entries(grouped).map(([date, shifts]) => (
            <section className="employee-shift-day" key={date}>
              <div className="employee-shift-date"><span>{formatDate(date, { weekday: "short" })}</span><strong>{formatDate(date, { weekday: undefined })}</strong></div>
              <div className="employee-shift-list">
                {shifts.map((shift) => (
                  <article className="employee-shift-card" key={shift.id}>
                    <div><strong>{shift.position_name || shift.role}</strong><span>{shift.department || ""}</span></div>
                    <div className="employee-shift-time">{formatClock(shift.start_time)} – {formatClock(shift.end_time)}</div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
