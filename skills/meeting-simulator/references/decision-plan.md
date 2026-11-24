# Plan and Batch Format (`decision-plan.md`)

## Base Plan (`plan.json`)

```json
{
  "issue": "Approve Pilot A v2 release package",
  "starting_proposal": "Publish v2 package with updated captions",
  "evidence": ["captions_v2.srt", "cut_v2_manifest.json"],
  "roles": [
    {"name": "PROD-M", "priorities": ["timing", "continuity"], "authority": "revise|retain|hold"},
    {"name": "CNT-M", "priorities": ["taxonomy", "metadata"], "authority": "revise|retain|hold"},
    {"name": "COM-M", "priorities": ["institutional_posture"], "authority": "revise|retain|hold"}
  ],
  "variants": [
    {"id": "order-b", "role_order": ["COM-M", "PROD-M", "CNT-M"]}
  ]
}
```

## Trace Format (`traces.json`)

```json
{
  "runs": [
    {
      "plan_id": "base",
      "steps": [
        {
          "role": "PROD-M",
          "action": "revise",
          "proposal": "Publish v2 package after fixing Beat 2 trim",
          "open_objections": ["Needs G06 sign-off"],
          "blockers": []
        }
      ]
    }
  ]
}
```

- **`action`**: `"revise"`, `"retain"`, or `"hold"`.
- **Handoff rule**: Each step's `role` must match the plan's `roles` order, and `"hold"` requires at least one non-empty item in `blockers`.
