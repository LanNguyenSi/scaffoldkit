# Task 001: Graceful Blueprint Resolution And Planforge Import

## Summary

Improve `scaffoldkit` so blueprint lookup and `from-planforge` imports degrade gracefully when the preferred blueprint or optional import details are not available locally.

## Problem

The current integration path is better than before, but it still assumes the recommended blueprint exists exactly as exported.
That is fragile when:

- a local ScaffoldKit checkout has fewer blueprints than expected
- blueprint names change over time
- `agent-planforge` exports multiple candidates but the first one is unavailable
- suggested variables contain fields that do not exist on the selected blueprint
- optional parts of the import payload are missing

Hard failures are correct for invalid blueprint definitions and missing required template files.
They are less helpful for recoverable mismatches where ScaffoldKit could still produce a useful result with an explicit fallback.

## Recommendation

Add graceful resolution at the integration boundary, while keeping hard failures for invalid or unsafe states.

### Recover Gracefully

- If `blueprint` is missing locally, try `blueprintCandidates` in order.
- If no candidate matches, show locally available blueprints plus the imported recommendation and reason.
- Ignore unknown `suggestedVariables` keys with a visible warning instead of treating them as fatal.
- Accept partial planforge exports when enough information exists to scaffold a project.
- Treat missing optional sections such as `features`, `constraints`, or `architecture` as warnings, not hard failures.

### Fail Hard

- Missing blueprint after all fallback attempts
- Invalid blueprint definition
- Missing required template or static file
- Invalid required variable after normalization
- Malformed import payload that does not identify a project or blueprint

## Proposed Changes

1. Extend `from-planforge` to try `blueprintCandidates` when the primary blueprint is unavailable.
2. Add a small warning/reporting layer for ignored variable hints and fallback blueprint selection.
3. Make the planforge import parser distinguish between required and optional payload sections.
4. Add CLI output that makes fallback behavior explicit, not silent.
5. Add tests for:
   - primary blueprint missing but fallback candidate available
   - unknown suggested variable names
   - partial import payload with optional fields omitted
   - total failure when no candidate exists

## Acceptance Criteria

- `scaffoldkit from-planforge` succeeds when the primary imported blueprint is missing but a later candidate exists locally.
- The CLI tells the user when a fallback blueprint was selected.
- Unknown suggested variable names are ignored and reported, not treated as fatal.
- Missing optional import fields do not block generation.
- Invalid or incomplete imports still fail clearly when required data is absent.
- Tests cover the fallback and warning paths.

## Notes

This should remain a contract-based integration, not a runtime dependency on `agent-planforge`.
The goal is resilient interoperability, not tighter repo coupling.
