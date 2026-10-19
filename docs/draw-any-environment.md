---
title: Draw prod without prod access
description: Draw production without production access, or infrastructure that does not exist yet. TerraVision draws from Terraform code and a variables file, never from a live cloud account, so one codebase gives dev, staging and prod diagrams.
---

# Draw prod without prod access

TerraVision draws what your Terraform **will** deploy, not what is running. It reads the code and a variables file, plans it against empty local state, and draws the result. It never connects to the accounts the code deploys to, and never reads their state.

- **The infrastructure does not need to exist.** Draw a new platform, region or account before anyone has built it, and review the design in a pull request before it is applied.
- **You need no access to the accounts it deploys to.** Draw production without production credentials. A developer, reviewer, auditor or AI assistant with no access to any of the target accounts gets the same diagram the platform team would.
- **One codebase draws every environment.** The variables file picks the environment, so the same code gives you a dev, a staging and a prod diagram.

Live cloud scanners cannot do any of this: they draw only an account they have been given access to, and only what is already deployed. See [how they compare](alternatives.md#terravision-vs-live-cloud-scanners-hava-cloudviz-holori).

## Why it matters

### Security review of another team's code

A security reviewer is usually given a design document and a hand-drawn diagram, and asked to approve what the team says it will deploy. Neither is guaranteed to match the code, nothing is deployed yet to scan, and the reviewer rarely has access to the team's accounts anyway. So the review rests on trust.

With TerraVision the reviewer draws the team's own code, with the variables file for the environment under review, and sees what it will actually deploy:

- **Check it against the design document.** A public subnet, an internet-facing load balancer or a database outside its private subnet that the document never mentioned shows up on the diagram.
- **Check it against the pattern approved last time.** Keep the diagram approved in the previous review round, draw the code again at the next one, and push back on anything that differs from the approved pattern.
- **Check the settings.** In the [interactive HTML](usage-guide.md#terravision-visualise) diagram, click any resource to see its settings, such as encryption, public access, open ports and IAM.

The reviewer needs read access to the repository, not to the team's cloud accounts.

### Onboarding a new team member

A new engineer wants to understand the infrastructure before they have been given access to any of its accounts, which in many organisations takes weeks or is never granted for production. They can draw every environment from the repository on their first day, and see how dev, staging and prod differ.

### Shared modules that change underneath you

Many organisations give teams central, approved Terraform modules (a VPC, a cluster, a database) so that what teams build is compliant by design. When the platform team changes a module, every stack that uses it changes too, often without anyone in those teams reading the module's code. Because the diagram is drawn from the plan, modules included, the next drawing shows what the new module version deploys. Redraw [in CI](cicd-integration.md) on every change, including the pull request that bumps the module version, so the diagram in each team's docs follows the latest module, and reviewers see what a module upgrade changes in their own architecture before it is applied.

### More uses

- **Disaster recovery that only exists as code.** Draw the standby region from `dr.tfvars` before you ever need it, and review it while nothing is on fire.
- **Environment parity.** Draw staging and prod side by side to check that staging really is a faithful copy, or to see exactly where it is not.
- **Audits and compliance evidence.** Give auditors a diagram of production drawn from the released code, without giving them access to production. When CI [commits the redrawn diagram back to the repository](cicd-integration.md#commit-diagrams-back-to-repository), the repository's history becomes a versioned record of how the architecture changed: every version of the diagram, when it changed, and the code change behind it.
- **Contractors, partners and due diligence.** Share how a system is built, or review an acquired company's repositories, without granting account access.
- **One deployment per customer or region.** Where each customer or region has its own variables file, draw any of them on request.
- **AI assistants without cloud access.** An assistant in a sandbox can draw your Terraform as long as it can run a plan, or from a plan you hand it.

## Dev, staging and prod from the same code

```bash
terravision draw --source ./infra --varfile dev.tfvars     --outfile architecture-dev
terravision draw --source ./infra --varfile staging.tfvars --outfile architecture-staging
terravision draw --source ./infra --varfile prod.tfvars    --outfile architecture-prod
```

Each diagram shows what that environment's variables make the code deploy: conditionals, `count` and `for_each` are resolved per environment. Environments built from the same code often differ like this:

| What the variables set | dev | staging | prod |
|---|---|---|---|
| Availability zones | 2 | 2 | 3 |
| App servers | 1 | 2 | 6 |
| NAT gateways | 1, shared | 1, shared | 1 per zone |
| Database | single instance | Multi-AZ | Multi-AZ with 2 read replicas |
| Cache, CDN and WAF | off | cache only | all on |
| Instance size | `t3.small` | `m7i.large` | `m7i.2xlarge` |

Differences in shape (how many, which resources, in which zones) show on the diagram itself. Settings that change no shape, such as instance size, show when you click a resource in the [interactive HTML](usage-guide.md#terravision-visualise) diagram (`terravision visualise`).

Other ways environments are separated work the same way:

- **Layered variable files:** pass `--varfile` more than once, for example `--varfile common.tfvars --varfile prod.tfvars`.
- **Workspaces:** `--workspace production`.
- **A folder per environment** (plain Terraform or Terragrunt): point `--source` at it, for example `--source ./live/prod`.

Through an AI assistant, ask for it in plain words: *"Draw ./infra as production, using prod.tfvars"*.

## What you need

- The Terraform code and the environment's variables file.
- Terraform, Graphviz and Git on the machine that draws.
- Read-only credentials for **any** account with the same cloud provider, such as your own sandbox. Terraform checks that the credentials are valid before it plans, but planning resources that do not exist yet reads nothing from the target account.

To draw with no cloud credentials at all, run `terraform plan` once wherever credentials exist and pass the result with `--planfile` and `--graphfile`. See [Pre-Generated Plan Input](usage-guide.md#pre-generated-plan-input).

## When the target account is still needed

Code that reads from the target account needs read access to whatever it reads:

- **Data sources that look up existing resources** there, such as a VPC, subnet or secret found by id or name. Lookups any account can answer, such as a public machine image, work with any credentials.
- **`terraform_remote_state`**, which reads another stack's state from its backend.
- **A provider block that assumes a role** in the target account (`assume_role`), which needs permission to assume it.

For code like this, plan once where access exists and draw from the plan files, as above.

## Related

- [FAQ: security and credentials](faq.md#security-and-privacy)
- [CI/CD Integration](cicd-integration.md): keep a diagram per environment current on every change
- [Terraform diagram generator](terraform-diagram-generator.md)
