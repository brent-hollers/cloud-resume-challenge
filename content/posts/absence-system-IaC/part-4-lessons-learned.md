---
title: "IaC Part 4: Lessons Learned: Cost, Challenges, and What's Next"
subtitle: "Building Production-Grade Infrastructure - Part 4 of 4"
date: 2026-02-18
author: Dr. Brent Hollers
tags: [DevOps, Lessons Learned, Cost Optimization, Infrastructure, Best Practices]
series: "Building Production-Grade Infrastructure"
part: 4
description: "Honest reflections from production: what broke, what we'd change, real costs, and lessons for your next infrastructure project."
---

# Lessons Learned: Cost, Challenges, and What's Next

*Part 4 of 4: Building Production-Grade Infrastructure*

---

## Reality vs. Expectations

In [Parts 1-3](./part-1-from-manual-chaos-to-iac.md), we built a production-grade absence tracking system with Terraform, monitoring, and CI/CD. The code worked. The architecture was sound. The deployment succeeded.

**Then we turned it on.**

This final article covers what actually happened in production: real costs, unexpected problems, decisions we'd change, and lessons that only come from running systems at scale.

**No perfect code here. Just honest reflections.**

---

## The Cost Reality Check

### What We Actually Spend: $65/month

| Service | Monthly Cost | % of Total |
|---------|--------------|------------|
| NAT Gateway | $32.85 | 50% |
| Application Load Balancer | $16.20 | 25% |
| EC2 t3.micro | $7.50 | 12% |
| Everything else | $8.45 | 13% |

**The shock: Half our infrastructure budget is one service.**

NAT Gateway enables our EC2 instance (in a private subnet) to reach the internet for Gmail API calls and package updates. It's essential for our security model, but expensive.

**Optimization we implemented:**

Changed EC2 from on-demand to Reserved Instance:
- **Before:** $7.50/month
- **After:** $4.50/month  
- **Savings:** 40% ($36/year)
- **Risk:** Zero (no upfront commitment required)

**Optimization we're considering:**

Replace NAT Gateway with NAT instance (t3.nano):
- **Savings:** ~$27/month ($324/year)
- **Tradeoff:** Less reliable, manual patching required
- **Verdict:** Worth it for a small school, not for enterprise

### ROI Analysis

**Total 5-year cost:**
- Development: $3,000 (60 hours × $50/hr)
- Infrastructure: $3,900 (5 years × $65/month × 12)
- **Total:** $6,900

**Total 5-year savings:**
- Administrative labor: $15,000 (10 hrs/month × $25/hr × 60 months)
- Principal time: $6,000 (2 hrs/month × $50/hr × 60 months)
- **Total:** $21,000

**Net value: +$14,100 over 5 years**

**Break-even: Month 11**

**Lesson:** Infrastructure as Code has upfront costs but pays dividends. The ROI is in *not* spending time on manual work.

---

## What Actually Broke (and How We Fixed It)

### Problem 1: Circular Dependencies

**The error:**
```
Error: Cycle: module.compute, module.load_balancer
```

**What happened:**
- Compute module wanted ALB DNS for n8n configuration
- Load balancer module wanted EC2 instance ID to register target
- Terraform couldn't resolve the dependency order

**Our fix:**
```hcl
# Made ALB DNS optional
module "compute" {
  webhook_url = var.webhook_url  # Defaults to ""
}

# n8n auto-detects hostname from HTTP headers
# Workaround: Works, but not ideal
```

**Better solution (production):**
- Use Ansible for application configuration
- Terraform creates infrastructure → Ansible configures apps
- Clean separation eliminates circular dependencies

**Lesson:** Separate infrastructure provisioning from application configuration. Terraform builds, Ansible configures.

---

### Problem 2: OIDC Authentication Failed

**The error:**
```
GitHub Actions Error: Not authorized to perform sts:AssumeRoleWithWebIdentity
```

**Root cause:** Terraform variable had wrong GitHub repo name
- Variable: `staff-absence-request-system`
- Actual repo: `absence-system-infrastructure`
- Trust policy checked for wrong repo → Access denied

**How we debugged:**
```bash
# Checked trust policy
aws iam get-role --role-name absence-system-github-actions \
  --query "Role.AssumeRolePolicyDocument.Statement[0].Condition"

# Found mismatch in repo name
```

**The fix:** Updated Terraform variable, redeployed IAM role

**Lesson:** IAM errors are usually configuration mismatches, not AWS problems. Check: Does resource exist? → Does policy allow? → Does identity match?

---

### Problem 3: CloudFront Took Forever

**The problem:** `terraform apply` appeared to hang for 15 minutes during CloudFront creation.

**What was actually happening:** CloudFront legitimately takes 10-20 minutes to deploy to edge locations worldwide.

**Our solution:** Set expectations

```hcl
output "deployment_notice" {
  value = <<-EOT
    ⏳ CloudFront deploys to ~400 edge locations.
    Takes 10-20 minutes - this is normal!
    Monitor: https://console.aws.amazon.com/cloudfront/
  EOT
}
```

**Lesson:** Some AWS services are slow by design. Document this so teammates don't panic.

---

### Problem 4: Docker Volume Permissions

**The error:**
```
docker: Error response from daemon: 
EACCES: permission denied, open '/home/node/.n8n/config'
```

**Root cause:** Host directory owned by root, container runs as user `node` (UID 1000)

**Our workaround (demo):**
```bash
# Don't mount volume - acceptable for POC
docker run -d --name n8n -p 5678:5678 n8nio/n8n
```

**Production solution:**
```hcl
# Use AWS EFS with proper IAM
resource "aws_efs_file_system" "n8n" {
  encrypted = true
}

# Mount in EC2, let AWS handle permissions
```

**Lesson:** Docker volume permissions are tricky. Use managed storage (EFS, EBS) for production.

---

## What We'd Do Differently

### 1. Ansible from Day One

**Current:** EC2 user data script
**Problem:** Changes require instance replacement

**Better:**
```yaml
# ansible/playbook.yml
- hosts: n8n_servers
  roles:
    - docker
    - n8n
    - cloudwatch_agent
```

**Benefits:**
- Changes don't require instance replacement
- Idempotent (safe to re-run)
- Separates infrastructure from configuration

---

### 2. Multi-Environment from Start

**Current:** Single production environment

**Better:**
```
environments/
├── dev/terraform.tfvars
├── staging/terraform.tfvars
└── prod/terraform.tfvars
```

**Benefits:**
- Test changes in dev before production
- Same code, different variables
- Confidence in deployments

---

### 3. Cost Alerting Day One

**Should have created:**
```hcl
resource "aws_budgets_budget" "monthly" {
  budget_type  = "COST"
  limit_amount = "100"
  limit_unit   = "USD"
  
  notification {
    threshold = 80  # Alert at $80
    notification_type = "ACTUAL"
  }
}
```

**Why:** First bill was $82 (over our $65 budget). Alert would have caught it.

---

### 4. Secrets Manager from Start

**Current:** OAuth tokens in n8n (in memory)

**Better:**
```hcl
resource "aws_secretsmanager_secret" "gmail_oauth" {
  name = "${var.project_name}/gmail/oauth"
}

# EC2 retrieves at runtime
aws secretsmanager get-secret-value --secret-id ...
```

**Why:** Secrets in Secrets Manager = centralized rotation, audit logging, IAM access control

---

## Key Lessons for Your Next Project

### 1. Start Simple, Iterate

**Our timeline:**
- **Week 1:** Basic form → n8n → Google Sheets (MVP)
- **Week 2:** HTTPS + custom domain
- **Week 3:** Monitoring + alarms
- **Week 4:** CI/CD automation

**Lesson:** Ship working software, improve incrementally. Perfect is the enemy of shipped.

---

### 2. Security is Not Retrofittable

**Things we did right from day one:**
- ✅ Private subnets (can't retrofit easily)
- ✅ OIDC for CI/CD (better than rotating keys later)
- ✅ Security groups by ID (logical relationships)

**Things we added later (should have been day one):**
- ❌ Secrets Manager
- ❌ WAF
- ❌ GuardDuty

**Lesson:** Security debt compounds. Build it in from the start.

---

### 3. Monitoring Before Problems

**We set SLOs before launch:**
- P95 response time < 2 seconds
- 99.9% uptime
- Error budget tracking

**First week:** One alarm fired during AWS maintenance window. Caught issue before users noticed.

**Lesson:** You can't improve what you don't measure. Observability enables confidence.

---

### 4. Documentation is Code

**What worked:**
- ✅ Architecture diagrams auto-generated (Python Diagrams)
- ✅ Terraform modules are self-documenting
- ✅ Workflow JSON in Git

**What didn't:**
- ❌ Manual README updates (fell out of date)

**Fix:**
```bash
# Pre-commit hook
terraform-docs markdown table . > README.md
```

**Lesson:** If it's not code, it will drift. Automate everything.

---

### 5. Cost Optimization is Ongoing

**Month 1:** $85 (no optimization)  
**Month 2:** $65 (identified NAT Gateway as 50% of bill)  
**Month 3:** Evaluating Reserved Instances and NAT alternatives

**Lesson:** Monitor costs like performance. Set budgets. Review monthly.

---

### 6. Real Engineering Has Tradeoffs

Every decision involved tradeoffs:

| Decision | Trade-off |
|----------|-----------|
| NAT Gateway vs Instance | Reliability vs cost |
| Self-hosted n8n vs Zapier | Control vs convenience |
| OIDC vs AWS keys | Security vs setup time |
| Private subnet vs public EC2 | Security vs simplicity |

**Lesson:** No perfect answers. Document your reasoning.

---

### 7. Test in Production (Safely)

**Our strategy:**
- Pre-deploy: Terraform plan, manual testing
- Post-deploy: Canary with one teacher first
- Monitoring: CloudWatch dashboards
- Safety net: Git rollback + Terraform state

**Lesson:** You can't test everything in staging. Production is the real test. Build safety nets.

---

### 8. Infrastructure as Code Pays Off

**Initial investment:** 60 hours

**Time saved per change:**
- Manual: ~2 hours
- IaC: ~10 minutes

**Break-even:** 30 changes (~6 months for us)

**After 1 year:** Changes are trivial. Massive ROI.

**Lesson:** IaC feels slow at first. Stick with it. The payoff is real.

---

## Measuring Success

### Technical Metrics (Month 1)

- **Uptime:** 100% (target: 99.9%) ✅
- **P95 latency:** 1.2s (target: <2s) ✅
- **Success rate:** 100% (847/847 requests) ✅

### Business Impact

- **Teacher adoption:** 96% in week 1
- **Time to submit:** 1.5 min (target: <2 min) ✅
- **Admin time saved:** 10 hrs/month → $250/month
- **Principal time saved:** 2 hrs/month → $100/month

### User Feedback

Surveyed 48 teachers:
- 96% said "easier than old process"
- 98% would recommend
- Principal: "Best upgrade in years"

---

## What's Next

### Immediate (Q1 2026)
- [ ] Implement Reserved Instance ($3/month savings)
- [ ] Add cost alerting (AWS Budgets)
- [ ] Secrets Manager for OAuth tokens
- [ ] Ansible for configuration management

### Scaling (Q2-Q3 2026)
- [ ] Multi-environment (dev/staging/prod)
- [ ] Auto Scaling for high availability
- [ ] RDS PostgreSQL (replace Google Sheets for audit log)
- [ ] WAF + GuardDuty for security

### Innovation (2027+)
- [ ] Multi-tenant SaaS (serve multiple schools)
- [ ] Mobile app
- [ ] AI-powered coverage suggestions
- [ ] Predictive analytics

---

## Final Reflections

### What Surprised Us

**Positive:**
- Teachers adopted it immediately (96% week 1)
- Zero downtime in first month
- IaC made changes trivial

**Negative:**
- NAT Gateway costs more than EC2 itself
- CloudFront deployments take 15 minutes every time
- Docker permissions more complex than expected

### What We're Proud Of

1. **Zero manual AWS console work** - Everything in Git
2. **Security exceeds requirements** - Private subnets, OIDC, audit trail
3. **SRE practices in a school** - SLO tracking with error budgets
4. **Real impact on time** - 10+ hrs/month saved

### What We'd Tell Our Past Selves

1. "Use Ansible from day one"
2. "Set up cost alerting immediately"
3. "NAT Gateway will be your biggest cost"
4. "Document the 'why' not just the 'what'"
5. "Trust the process - IaC payoff comes after 20+ changes"

---

## Conclusion

**We went from:**
- Manual phone calls → Automated workflow
- Sticky notes → Audit trail in Google Sheets
- 10 hrs/month overhead → Zero manual work
- Hope and prayers → 99.9% uptime SLO

**The bigger lesson:**

Small teams with limited budgets can build enterprise-grade systems. You don't need a 10-person team or $100K budget. You need:
- ✅ Willingness to learn
- ✅ Commitment to automation
- ✅ Focus on fundamentals (security, monitoring, IaC)
- ✅ Patience to iterate

**This wasn't just about absence tracking.** It was about proving that DevOps/SRE practices work at any scale.

---

## Thank You

**The Complete Series:**

1. [Part 1: From Manual Chaos to Infrastructure as Code](./part-1-from-manual-chaos-to-iac.md)
2. [Part 2: Building Secure, Modular Infrastructure with Terraform](./part-2-building-with-terraform.md)
3. [Part 3: Automating Everything - CI/CD, Monitoring, and Workflows](./part-3-automating-everything.md)
4. **Part 4: Lessons Learned - Cost, Challenges, and What's Next** (you are here)

**Connect:**
- [GitHub Repository](https://github.com/brent-hollers/absence-system-infrastructure)
- [LinkedIn](https://linkedin.com/in/brent-hollers)
- [Live Demo](https://form.absences.smaschool.org)

**If this series helped you:** Star the repo, share your story, pay it forward.

---

*Thank you for reading. Now go build something amazing.* 🚀

**Tags:** #DevOps #LessonsLearned #Infrastructure #AWS #Terraform #CostOptimization #RealWorld