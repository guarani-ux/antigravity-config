# ARCHIVED WORKFLOW — POST-BUILD CLAIM VERIFICATION
Archived: 2026-09-25
Status: DEPRECATED / ARCHIVED in favor of demand-loaded Verification Workflows (Software 3.0).

## Historical Content
1. Implementation finishes.
2. A verifier that did NOT author the implementation receives: frozen approved plan, exact git diff, current repository, acceptance tests, CI results.
3. Build a claim ledger: PLAN CLAIM -> IMPLEMENTATION LOCATION -> TEST THAT PROVES IT -> PHYSICAL RESULT -> VERIFIED / UNVERIFIED / FALSE.
4. Check specifically: every required plan change actually exists, code is wired into the production path, no alternate path bypasses the new invariant, tests prove behavior rather than existence.
5. If any material claim is UNVERIFIED: do not report complete.
