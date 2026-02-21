---
title: "From Manual Chaos to Infrastructure as Code: Designing a School Absence System"
subtitle: "Building Production-Grade Infrastructure - Part 1 of 4"
date: 2026-02-19
author: Dr. Brent Hollers
tags: [DevOps, Infrastructure as Code, Terraform, AWS, System Design]
series: "Building Production-Grade Infrastructure"
part: 1
description: "How we transformed a chaotic manual absence tracking process into an automated, enterprise-grade system using Infrastructure as Code principles."
---

# From Manual Chaos to Infrastructure as Code: Designing a School Absence System

*Part 1 of 4: Building Production-Grade Infrastructure*

---

## The 7:45 AM Problem

It's 7:45 AM on a Tuesday morning. The school secretary's phone rings. It's Mrs. Johnson calling in sick—again. The secretary scribbles a note on a sticky pad, crosses off Mrs. Johnson's name on the coverage spreadsheet, and starts making calls to find a substitute for periods 3, 5, and 7.

By 8:00 AM, three more teachers have called. Two sent emails. One left a voicemail. The principal needs to approve Mr. Smith's vacation request from next week, but that conversation happened in the hallway yesterday and nobody documented it. The front desk has no idea which periods need coverage because half the notifications came via different channels.

Welcome to absence tracking at a typical small school.

**This article series documents how we transformed this chaos into an automated, enterprise-grade system using Infrastructure as Code.**

---

## The Business Problem: Death by Sticky Notes

### Current State Pain Points

Our school, like many small institutions, relied on a patchwork of manual processes:

**For Teachers:**
- Call or email the front desk to report absences
- No confirmation that the request was received
- No visibility into approval status
- Repeat the same information to multiple people

**For the Principal:**
- Approval requests come via hallway conversations
- No audit trail of who approved what
- Can't distinguish retroactive sick leave from planned vacations
- No way to track patterns or generate reports

**For the Front Desk:**
- Manually track absences in a spreadsheet
- Phone calls interrupt other work
- No standardized information collection
- Coverage requirements unclear (which periods? full day?)
- Reporting is impossible ("How many sick days did Mrs. Johnson take this semester?")

**The Real Cost:**
- ~10 hours per month of secretarial time on absence tracking
- Missed coverage leading to classroom disruptions
- Compliance risk (no audit trail for HR)
- Principal approval bottlenecks

At $25/hour for administrative time, we're spending **$250/month** on a process that could be automated.

---

### Stakeholder Requirements

Through interviews with teachers, administrators, and front desk staff, we identified clear success criteria:

**Teachers Need:**
- ✅ Submit absence request in under 2 minutes
- ✅ Automatic confirmation email
- ✅ No phone calls during planning period

**Principal Needs:**
- ✅ Approve/deny planned absences with one click
- ✅ Automatic approval for retroactive sick leave (already happened)
- ✅ Audit trail for HR compliance

**Front Desk Needs:**
- ✅ Know exactly which periods need coverage
- ✅ Centralized tracking in Google Sheets (existing tool)
- ✅ Email notifications for coverage requirements

**IT (Me) Needs:**
- ✅ Secure, maintainable, cost-effective
- ✅ No secret credentials to manage
- ✅ Disaster recovery in under 30 minutes
- ✅ 99.9% uptime (no more than 43 minutes downtime per month)

---

## Why Infrastructure as Code?

Before diving into architecture, let's address the fundamental question: **Why build this with Infrastructure as Code instead of just clicking around the AWS console?**

### The Traditional Approach (What We Avoided)

**The "ClickOps" Method:**
1. Log into AWS console
2. Click through wizards to create VPC, subnets, security groups
3. Launch EC2 instance, configure manually
4. Set up load balancer by clicking through forms
5. Screenshot settings for "documentation"
6. Pray nothing breaks

**Problems with This Approach:**
- ❌ **"Works on my machine" syndrome:** No guarantee staging matches production
- ❌ **Knowledge loss:** When I leave, how do the next IT person recreate this?
- ❌ **No version control:** Can't track who changed what, when, or why
- ❌ **No rollback:** If a change breaks things, good luck remembering what you clicked
- ❌ **Documentation drift:** Screenshots go stale immediately
- ❌ **No peer review:** Changes go live without oversight
- ❌ **Environment inconsistency:** Staging is "kinda like" production

### The IaC Approach (What We Built)

**Infrastructure Defined in Code:**
```hcl
# This creates a VPC - same every time, reviewable, version controlled
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  
  tags = {
    Name = "absence-system-vpc"
  }
}
```

**Benefits:**
- ✅ **Reproducible:** `terraform apply` creates identical infrastructure every time
- ✅ **Version controlled:** Every change in Git with author, timestamp, reason
- ✅ **Peer reviewed:** Pull requests catch issues before production
- ✅ **Self-documenting:** Code IS the documentation (can't drift)
- ✅ **Disaster recovery:** Lost infrastructure? `terraform apply` rebuilds in minutes
- ✅ **Team collaboration:** Multiple engineers can work without conflicts (state locking)
- ✅ **Environment parity:** Dev, staging, prod use same code with different variables

### Real-World Example: The 3 PM Incident

Two weeks after launch, our EC2 instance crashed at 3 PM—right when teachers submit afternoon absences.

**Without IaC:**
1. Panic
2. Try to remember: What instance type was it? Which AMI? What IAM role?
3. Manually recreate from screenshots (45+ minutes)
4. Cross fingers that it matches original config
5. Hope nothing was forgotten

**With IaC:**
```bash
$ terraform apply
# 12 minutes later: identical infrastructure rebuilt
# Same configuration, same security, same monitoring
# Guaranteed.
```

**Our actual downtime:** 12 minutes. **Manual approach:** Would have been 60+ minutes.

This incident alone justified the IaC investment.

---

### Why This Matters for Schools

Small IT teams (often just 1-2 people) face unique challenges:

**Limited Resources:**
- Can't afford dedicated DevOps engineer
- IaC multiplies effectiveness of small teams
- Automation reduces toil

**Budget Constraints:**
- Manual labor is expensive ($250/month in our case)
- IaC enables self-service (teachers submit forms, no admin time)
- Infrastructure costs are predictable and optimizable

**Compliance Requirements:**
- Audit logs required for HR
- No manual changes = no unauthorized modifications
- Version control provides complete change history

**Staff Turnover:**
- Knowledge captured in code, not in people's heads
- New IT staff can understand system by reading Terraform
- Onboarding time reduced from weeks to days

**Cost-Benefit Analysis:**
- **Time investment in IaC:** ~40 hours initial setup
- **Time saved per infrastructure change:** ~2 hours (manual) → 10 minutes (code)
- **Break-even point:** After ~20 changes (about 6 months)
- **ROI after 1 year:** Massive (changes become trivial)

---

## Architecture Design Decisions

Now that we understand *why* Infrastructure as Code, let's examine *how* we designed the system.

Every architecture decision involves tradeoffs. Here's our decision-making process:

---

### Decision 1: Cloud Provider - AWS

**Chosen:** Amazon Web Services (AWS)

**Why:**
- School already uses Google Workspace → needed integration
- AWS has mature Gmail/Google Sheets SDK support
- My team has AWS experience
- Strong ecosystem (CloudFormation, Terraform support, extensive documentation)
- Cost predictability with usage calculators

**Alternatives Considered:**
- **Azure:** Excellent for Microsoft-heavy environments, but we're Google Workspace
- **Google Cloud:** Considered seriously (native Google integration), but AWS had better Terraform module ecosystem
- **On-premises:** Rejected immediately (hardware costs, maintenance, no HA)

**Tradeoff:**
- AWS complexity vs. mature ecosystem
- We chose maturity and community support
- Accepted: Steeper learning curve for some AWS-specific services

---

### Decision 2: Networking - Private Subnet Isolation

**Chosen:** VPC with public/private subnet architecture

**Design:**
```
Internet
    ↓
Internet Gateway
    ↓
Public Subnets (ALB, NAT Gateway)
    ↓
Private Subnet (EC2 - no public IP!)
    ↓
NAT Gateway (for outbound only)
    ↓
Internet (Gmail API, package updates)
```

**Why:**
- **Defense in depth:** EC2 instance has zero exposure to internet
- **Compliance:** Meets security best practices for sensitive data
- **Attack surface reduction:** Can't SSH from internet even if port opened accidentally
- **Audit trail:** All access via AWS Systems Manager Session Manager (logged)

**Alternatives Considered:**
- **Public subnet with SSH:** Simple, but violates security principles
- **VPN access only:** Considered, but overhead not justified for small team
- **Single subnet (public only):** Rejected immediately (unacceptable risk)

**Tradeoff:**
- Added complexity (NAT Gateway, routing tables) vs. security
- Added cost (~$32/month for NAT Gateway) vs. peace of mind
- **We chose security.** Worth every penny.

**Interview talking point:** *"I implemented private subnet isolation because treating EC2 instances as internet-accessible by default is an anti-pattern. Defense in depth means assuming breach at every layer."*

---

### Decision 3: HTTPS Everywhere with Custom Domain

**Chosen:** Application Load Balancer with SSL/TLS termination + custom domain

**Design:**
```
User visits: https://absences.smaschool.org
    ↓
ALB terminates SSL (port 443)
    ↓
Forwards plain HTTP to EC2 (port 5678)
    ↓
n8n responds
    ↓
ALB encrypts response, sends to user
```

**Why:**
- **Trust:** Teachers trust `absences.smaschool.org` more than random AWS URLs
- **Security:** HTTPS required for OAuth (Gmail login)
- **Professionalism:** Green padlock = legitimate school system
- **Simplicity:** ALB handles SSL certificates, EC2 doesn't need to

**Alternatives Considered:**
- **Direct EC2 with SSL:** Rejected (certificate management burden, no HA)
- **CloudFront only:** Considered, but ALB provides better health checks for our use case
- **HTTP only:** Rejected immediately (unacceptable for authentication)

**Tradeoff:**
- Cost (~$16/month for ALB) vs. professional appearance + security
- Certificate management complexity vs. AWS Certificate Manager (ACM) automation
- **We chose professionalism.** The custom domain alone increased teacher adoption.

---

### Decision 4: Workflow Engine - n8n vs. Custom Code

**Chosen:** n8n (open-source workflow automation platform)

**Why:**
- **Visual workflows:** Non-developers can understand and modify
- **Rapid iteration:** Drag-and-drop beats coding for workflow changes
- **Built-in integrations:** Gmail, Google Sheets, webhooks out-of-box
- **Lower maintenance:** No custom code to debug or update

**Alternatives Considered:**
- **AWS Step Functions:** Too expensive for our scale (~$25/month minimum)
- **Custom Lambda functions:** Rejected (more code to maintain, slower iteration)
- **Zapier/Make:** Rejected (vendor lock-in, recurring SaaS costs)
- **Pure code (Python/Node.js):** Rejected (principal can't modify workflow logic)

**Tradeoff:**
- Running another service (Docker container) vs. development speed
- n8n learning curve vs. Lambda familiarity
- **We chose speed.** Workflow changes take minutes, not days.

**Real-world benefit:** When principal requested adding "coverage period" tracking, I updated the n8n workflow in 15 minutes. With Lambda, this would have been a sprint story.

---

### Decision 5: CI/CD - GitHub Actions with OIDC

**Chosen:** GitHub Actions with OpenID Connect (OIDC) authentication

**Design:**
```
Developer pushes to GitHub
    ↓
GitHub Actions triggers
    ↓
GitHub generates short-lived token
    ↓
AWS verifies token (OIDC)
    ↓
AWS issues temporary credentials (15 min)
    ↓
Deploy to S3, invalidate CloudFront
    ↓
Credentials expire automatically
```

**Why:**
- **Zero long-lived secrets:** No AWS keys stored in GitHub
- **Automated deployment:** Frontend changes go live in ~5 minutes
- **Audit trail:** Every deployment tracked in GitHub Actions logs
- **Branch restrictions:** Only `main` branch can deploy to production

**Alternatives Considered:**
- **AWS access keys in GitHub Secrets:** Rejected (security anti-pattern)
- **Manual deployment:** Rejected (slow, error-prone, doesn't scale)
- **Jenkins self-hosted:** Rejected (more infrastructure to manage)

**Tradeoff:**
- Setup complexity (OIDC, IAM trust policies) vs. long-term security
- **We chose security.** OIDC is industry best practice.

**Interview talking point:** *"I use OIDC instead of long-lived credentials because credentials that can't leak are credentials that won't leak. The upfront complexity pays dividends in security posture."*

---

### Decision 6: Monitoring - CloudWatch with SLO Tracking

**Chosen:** CloudWatch alarms with Service Level Objective (SLO) tracking

**Design:**
- **Error budget:** 99.9% uptime = 43.8 minutes downtime allowed per month
- **SLO alarm:** P95 latency < 2 seconds
- **Proactive alerting:** Email when error budget consumption accelerates

**Why:**
- **Data-driven decisions:** Know when we're trending toward SLO breach
- **Prevents alert fatigue:** SLO-based alarms vs. arbitrary thresholds
- **Business alignment:** SLOs match what stakeholders care about ("Is the system fast enough?")

**Alternatives Considered:**
- **Just uptime monitoring:** Rejected (too coarse, misses degraded performance)
- **Third-party monitoring (Datadog):** Rejected (cost not justified for our scale)
- **No monitoring:** Rejected immediately (flying blind is malpractice)

**Tradeoff:**
- Effort to define SLOs vs. ad-hoc "is it up?" checks
- **We chose rigor.** SLOs provide confidence, not just hope.

---

## Final Architecture Overview

Here's what we built:

### High-Level System Flow

```
Teacher submits absence request
    ↓
Static HTML form (S3/CloudFront) - HTTPS
    ↓
Application Load Balancer - SSL termination
    ↓
EC2 instance (private subnet, no public IP)
    ↓
n8n workflow engine
    ↓
Decision: Past date or future date?
    ├─ Past → Auto-approve → Log to Google Sheets → Email confirmation
    └─ Future → Email principal for approval → Wait → Log → Notify
```

### Tech Stack

**Infrastructure Layer:**
- **Infrastructure as Code:** Terraform (7 modules, 30+ AWS resources)
- **Cloud Provider:** AWS
- **Networking:** Custom VPC (10.0.0.0/16), public/private subnets, NAT Gateway
- **Compute:** EC2 t3.micro (Amazon Linux 2)
- **Load Balancing:** Application Load Balancer with HTTPS
- **DNS/SSL:** Route53 + AWS Certificate Manager (ACM)
- **Frontend:** S3 + CloudFront (static HTML form)

**Application Layer:**
- **Workflow Engine:** n8n (Docker container)
- **Integrations:** Gmail (OAuth), Google Sheets (API)
- **Authentication:** Google OAuth 2.0

**DevOps Layer:**
- **CI/CD:** GitHub Actions with OIDC
- **Monitoring:** CloudWatch (alarms, dashboards, SLO tracking)
- **Alerting:** SNS → Email
- **State Management:** S3 backend + DynamoDB locking
- **Version Control:** Git (all code, workflows, documentation)

**Security Layer:**
- **Network:** Private subnets, security groups (least privilege)
- **Access:** IAM roles (no access keys), Systems Manager Session Manager
- **Encryption:** HTTPS (in transit), S3 encryption (at rest)
- **Compliance:** CloudTrail logs, audit trail in Google Sheets

---

### Architecture Diagram

![System Architecture](../diagrams/output/architecture.png)
*Auto-generated using Python Diagrams library - because documentation that's code can't go stale*

**Key architectural principles visible in the diagram:**

1. **Defense in Depth:** Multiple security layers (Internet Gateway → ALB → Security Groups → Private Subnet)
2. **Single Responsibility:** Each component does one thing well (networking, compute, load balancing separate)
3. **Fail-Safe Defaults:** Everything blocked by default, explicitly allow needed traffic only
4. **Least Privilege:** Minimal IAM permissions, no SSH access, read-only where possible

---

## Cost & Resource Summary

**Monthly AWS Costs (estimated):**
- EC2 t3.micro: $7.50
- Application Load Balancer: $16.20
- NAT Gateway: $32.85
- S3 + CloudFront: $1.50
- Other (Route53, CloudWatch, etc.): $7.00
- **Total: ~$65/month**

**Resources Created:**
- 1 VPC with 3 subnets across 2 availability zones
- 1 Internet Gateway
- 1 NAT Gateway with Elastic IP
- 2 Security Groups (ALB, EC2)
- 1 EC2 instance (t3.micro)
- 1 Application Load Balancer
- 1 Target Group with health checks
- 2 ALB listeners (HTTP → HTTPS redirect, HTTPS)
- 1 S3 bucket + CloudFront distribution
- 1 ACM certificate
- 3 CloudWatch alarms
- 1 SNS topic
- IAM roles and policies

**Development Time:**
- Initial setup: ~40 hours
- Iterations and refinements: ~20 hours
- **Total:** ~60 hours over 3 weeks

**ROI Calculation:**
- **Cost:** $65/month infrastructure + $150/month amortized development time (first year)
- **Savings:** $250/month in administrative labor
- **Net savings:** $35/month (positive ROI from day one)
- **Year 2+:** $250/month savings (development costs fully amortized)

---

## What's Next

We've explored the **why** (business problem, IaC benefits) and the **what** (architecture decisions, tradeoffs).

**In Part 2**, we'll dive deep into the **how**:
- Terraform module design philosophy
- VPC networking implementation (with actual code)
- HTTPS setup with ACM and ALB
- Security group least-privilege implementation
- Remote state configuration and team collaboration

**You'll see:**
- Real Terraform code with explanations
- Common pitfalls and how to avoid them
- Interview-worthy talking points for every decision
- Production-ready patterns you can use tomorrow

**Follow along:** All code is available on [GitHub](https://github.com/brent-hollers/absence-system-infrastructure)

---

## Key Takeaways

1. **Real problems drive better learning** than toy examples
2. **Infrastructure as Code** isn't just for large teams - small organizations benefit even more
3. **Architecture is tradeoffs** - document your reasoning, not just your choices
4. **Security and monitoring** should be designed in, not retrofitted
5. **Start simple, iterate** - we didn't build everything on day one

---

*This is Part 1 of a 4-part series on building production-grade infrastructure. [Part 2: Building Secure, Modular Infrastructure with Terraform](./part-2-building-with-terraform.md) dives into the implementation details.*

**Questions or feedback?** Connect with me on [LinkedIn](https://linkedin.com/in/brent-hollers) or check out the [GitHub repo](https://github.com/brent-hollers/absence-system-infrastructure).

---

**Tags:** #DevOps #InfrastructureAsCode #Terraform #AWS #CloudArchitecture #SRE #SystemDesign #CaseStudy