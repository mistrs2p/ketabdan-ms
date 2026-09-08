# 00 — Project Context

**Project name:** Ketabdaneh
**Document status:** Living document — update as discovery continues.
**Last reviewed:** 2026-09-08

---

## 1. Purpose

Ketabdaneh is a **branch operations management system** for a single Ketabdaneh branch.

The system exists to keep branch operations running in an **organized and predictable way** when the branch manager is physically absent, and to reduce (ideally eliminate) the need for the manager to manually chase people for status.

## 2. Business Problem

The branch manager today must:

- Continuously follow up with people **manually** to know what is happening.
- Stay personally involved in every operational detail to keep things moving.

The consequence: operations stall or become unpredictable when the manager is not physically present.

The system should provide:

- **Visibility** into events, assignments, tasks, and completion status.
- **Visibility into important exceptions** (things that did not go as planned).

## 3. Users / Roles (known from discovery)

People in the branch have **primary roles**:

| Role | Notes |
|---|---|
| Learner / Student | — |
| Supporter | Can have availability / time slots |
| Coach | — |
| Teacher | — |
| Referrer | — |
| Manager | The primary user the system is built around |

> Confirmed: these are *primary roles* a person can have.
> Not yet confirmed: whether a person can hold **multiple** roles at the same time — see Assumptions & TBD.

## 4. Core Concepts (known from discovery)

### 4.1 Event

- An activity that is **scheduled in advance**, usually based on a **weekly schedule**.
- Known event types (examples, not an exhaustive list):
  - Introduction session
  - Film analysis
  - Book analysis
  - Gathering
  - Group games
  - Classes
  - …and similar activities

### 4.2 Event Assignment

- An event may require **assigning one or more people to responsibilities**.
- Event responsibilities are **different from permanent organizational roles** (e.g., someone whose primary role is "learner" may still be assigned a responsibility for a specific event).
- The manager wants to **approve assignments** (see §5).

### 4.3 Task

- Tasks may be **daily, weekly, monthly, or event-based**.
- A task has:
  - An **assignee**.
  - A **completion state**.

### 4.4 Availability

- **Supporters** can have availability / time slots.
- Availability relates to when a supporter is able to participate (exact semantics not yet fully defined — see Assumptions & TBD).

### 4.5 Event Report

- **After an event**, a result / report may be recorded.
- The manager wants to **see these results** without having attended the event.

## 5. The Manager's Main Need

> Run the branch in an organized and predictable way **without continuous manual follow-up**, and **without being involved in every operational detail** — while still:
>
> - **Approving** assignments.
> - **Staying informed** about events, tasks, completion status, and results.
> - Being alerted to **important exceptions**.

## 6. MVP Direction

The **first important workflow** (the MVP anchor):

> **Create Event → Assign Person → Show Event in Calendar → Complete Event → Record Result → Manager sees result.**

### Technology stack (already selected)

| Layer | Choice |
|---|---|
| Frontend | Next.js + TypeScript |
| Backend | FastAPI + Python |
| Database | PostgreSQL |
| Architecture | Modular Monolith |

### Explicitly OUT of MVP scope

- Telegram integration.
- Bale integration.

These are **future possibilities**, not current requirements. They must not influence MVP design decisions beyond avoiding hard blockers.

## 7. Confirmed vs. Assumptions / TBD

### ✅ Confirmed (from discovery)

1. The project is a branch operations management system for a single Ketabdaneh branch.
2. The core problem is manager absence causing manual follow-up and unpredictability.
3. Primary roles: learner/student, supporter, coach, teacher, referrer, manager.
4. Supporters can have availability / time slots.
5. Events are scheduled in advance, usually on a weekly schedule.
6. Known event examples: introduction session, film analysis, book analysis, gathering, group games, classes, similar.
7. Events may require assigning one or more people to responsibilities.
8. Event responsibilities differ from permanent organizational roles.
9. Tasks are daily, weekly, monthly, or event-based; tasks have an assignee and a completion state.
10. After an event, a result/report may be recorded.
11. The manager wants to approve assignments and stay informed without operational involvement.
12. First workflow: Create Event → Assign Person → Calendar → Complete → Record Result → Manager sees result.
13. Stack: Next.js + TypeScript, FastAPI + Python, PostgreSQL, Modular Monolith.
14. Telegram/Bale integrations are future, not MVP.

### ⚠️ Assumptions / TBD (not confirmed — must be resolved before building on them)

| # | Open Question | Current Working Assumption |
|---|---|---|
| A1 | Can one person hold multiple primary roles simultaneously? | Assumed possible; needs confirmation. |
| A2 | Full, closed list of event types? | The listed types are examples only; no fixed taxonomy yet. |
| A3 | What is the exact semantics of supporter availability? (Hours of day? Days of week? Per-event?) | Unknown — needs discovery. |
| A4 | How is availability used? (Suggesting assignees? Conflict detection? Just informational?) | Unknown — needs discovery. |
| A5 | What are the possible event responsibilities? (Named roles per event type? Free text?) | Unknown — needs discovery. |
| A6 | What does "approve assignments" mean precisely? Does every assignment require approval, or only certain kinds? | Unknown — needs discovery. |
| A7 | What counts as an "important exception"? What are the notification/escalation rules? | Unknown — needs discovery. |
| A8 | What is "completing an event" exactly? Who marks it complete? | Unknown — needs discovery. |
| A9 | What content/structure does an event report have? (Free text? Structured form? Attendance?) | Unknown — needs discovery. |
| A10 | Task completion — who marks it done? Are there deadlines or reminders? | Unknown — needs discovery. |
| A11 | Who, besides the manager, uses the system and with what permissions? | Unknown — needs discovery. |
| A12 | Calendar — which view(s) (weekly/monthly), and is it only for events or also tasks? | Unknown — needs discovery. |
| A13 | Authentication method for users | TBD. |
| A14 | Language(s) of the UI (Persian? Bilingual?) | TBD. |

> **Rule of thumb for this project:** no business rule should be implemented based on the TBD items above. Each TBD must be resolved with the branch manager/domain experts before the corresponding feature is designed or built.

---

## 8. Out of Scope for This Document

- Database models / schemas.
- API design.
- Module boundaries of the modular monolith.
- Any code.

These belong to later documents once the TBD items above are resolved.
