# ADR-UI-001 Tailwind + shadcn/ui

**Status:** Accepted · **Date:** 2026-11-12

## Context
Several portal documents say not to assume a framework and offer static HTML/CSS; the Requirements spec names CSS Modules. The owner explicitly chose React + TypeScript + Vite + Tailwind + shadcn/ui, which satisfies their "ask before assuming" instruction.

## Decision
One React/TypeScript/Vite app with role-protected portal routes; Tailwind for styling; shadcn/ui (Radix-based) components copied into the repo. Per-portal themes via CSS variables.

## Consequences
- Tailwind build step; shadcn components are owned source, not a runtime dependency.
- Source honesty rules still apply: no fake functionality, mock data labelled.

## References
DDR-03; #2 §1.6, §13; #5 §2.4–5; #8 §2.7; #11 Gate A.
