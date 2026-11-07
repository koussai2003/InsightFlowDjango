# Private project workspaces

Every verified account receives a private project named My workspace. Its creator is the Owner. Users can create more projects and join other projects by accepting an invitation. A person's role can differ in each project. Platform administrators manage application accounts but cannot access another person's project without membership.

## Permissions

| Action | Owner | Moderator | Data Scientist | Reviewer |
| --- | --- | --- | --- | --- |
| View own project's members and shared results | Yes | Yes | Yes | Yes |
| Prepare data, run analysis and models | Yes | Yes | Yes | No |
| Review and approve results | Yes | Yes | No | Yes |
| Invite/manage Data Scientists and Reviewers | Yes | Yes | No | No |
| Appoint/manage Moderators | Yes | No | No | No |
| Transfer ownership or delete project | Yes | No | No | No |

Dataset operations, model execution, shared results, and review decisions are still planned capabilities. The permission gates exist, but their interfaces do not claim these services have already been implemented. Current CSV previews and question drafts stay in browser memory and are cleared when switching projects.

## Using the interface

1. Open My projects and select a project from the project switcher.
2. Project settings shows its members and your role. Owners and Moderators can invite an email address with a permitted role.
3. The recipient signs in with the matching verified email and opens Invitations. Acceptance grants membership; pending status grants no access.
4. Invitations expire after seven days. They can be declined or revoked and are single use. Invitations for an unregistered address appear after the recipient registers and verifies that same address.
5. Email notification delivery is not configured. Invitations are delivered through the in-app inbox. Share the app address with the intended collaborator separately.
6. Owners can transfer to an existing member and become Moderator. Owners cannot leave or remove themselves without transferring first. Project deletion requires typing its name.

Role changes, removal, and ownership transfer revoke outstanding invitations created by the affected member. Existing accepted memberships persist. Account deletion is blocked while projects are owned, to avoid orphaning collaborative work. New project creation does not promote a platform account.

## Server and database boundaries

Projects have an authoritative `owner_id`, with membership rows for every accepted member. Owner is derived from that ID; it is not a role someone can grant through ordinary membership updates. Invitation records bind project, recipient email, role, inviter, expiry, and status. All mutations lock the project to serialize ownership and membership changes.

All project routes authenticate through the existing verified Supabase session. Membership is read from the database for each request. Nonmembers receive 404, including platform administrators. Role violations return 403. A removed member's existing session cannot access the project. Invitations never accept a caller-supplied identity or role during acceptance.

Tables are in the private `insightflow` schema with RLS enabled and no public/anonymous/authenticated grants. The server's private database connection performs authorization; there are intentionally no browser-facing RLS policies. Supabase's informational "RLS enabled, no policy" finding is expected for these backend-only tables: https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy . The existing leaked-password protection warning is separate: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection .

Future dataset, version, analysis, model, report, conversation, and audit tables must include a project identifier. Every handler and storage download must enforce membership plus action permissions before querying or returning content. Do not treat opaque IDs, client filtering, or platform-admin status as authorization. No persistent datasets existed in this implementation, so there was no shared dataset migration.

## Backlog revision

| Jira | Story | Proposed Fibonacci points |
| --- | --- | --- |
| IF-11 / US1.5 | Enforce private project roles and permissions | 8 (previously 5) |
| IF-38 / US1.6 | Create and switch private projects | 5 |
| IF-39 / US1.7 | In-app invitations and acceptance | 8 |
| IF-40 / US1.8 | Members, ownership transfer and project deletion | 5 |
| IF-41 / US6.6 | Invitation email notifications | 3, optional follow-up |

IF-1's proposed total rises from 16 to 37 points. These are estimates for team planning poker, not measured velocity. Additional stories remain unscheduled until sprint capacity is reviewed. Existing sprint assignments and completed account stories remain intact. Data/import/cleaning/EDA/modeling/reporting stories now explicitly require project isolation. Implementation must be peer-reviewed and merged before claiming the Definition of Done; IF-41 remains unimplemented.

## Validation

Tests run with a disposable PostgreSQL database. Supabase authentication is mocked at its HTTP boundary; project tests use test-only authenticated identities. Coverage includes personal workspace creation, nonmember and platform-admin isolation, differing roles across projects, email-bound single-use invitations, expiry/decline/revocation, moderator limitations, removal, ownership transfer, deletion confirmation, and legacy route retirement. No production users are created or invited during tests.
