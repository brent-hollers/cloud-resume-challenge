---
title: "IaC Part 3: Automating Everything: CI/CD, Monitoring, and Workflows"
subtitle: "Building Production-Grade Infrastructure - Part 3 of 4"
date: 2026-02-17
author: Dr. Brent Hollers
tags: [DevOps, CI/CD, CloudWatch, Monitoring, SRE, GitHub Actions, OIDC, Automation]
series: "Building Production-Grade Infrastructure"
part: 3
description: "Moving beyond infrastructure to production operations: CloudWatch monitoring with SLO tracking, GitHub Actions CI/CD with OIDC, and automated workflow orchestration with n8n."
---

# Automating Everything: CI/CD, Monitoring, and Workflows

*Part 3 of 4: Building Production-Grade Infrastructure*

---

## From Infrastructure to Operations

In [Part 1](./part-1-from-manual-chaos-to-iac.md), we identified the business problem and designed our architecture. In [Part 2](./part-2-building-with-terraform.md), we built secure, modular infrastructure with Terraform.

**But infrastructure alone isn't production-ready.**

A system is only as good as our ability to:
- Know when it breaks (monitoring)
- Deploy changes safely (CI/CD)
- Automate business logic (workflows)

**This article covers making infrastructure operational:**
- CloudWatch monitoring with SLO-based alerting
- GitHub Actions CI/CD with OIDC (zero long-lived secrets)
- n8n workflow automation with conditional logic
- End-to-end testing strategies

**Target audience:** DevOps engineers, SREs, and anyone responsible for keeping systems running.

---

## The SRE Mindset: SLOs, Not Just Uptime

### Why "Five Nines" is a Lie

Early in my career, I made this promise:

> "Our system will have 99.999% uptime."

**Five nines = 5.26 minutes downtime per year.**

Then reality hit:
- AWS had a region outage (4 hours)
- We deployed a bad configuration (45 minutes)
- A dependency API went down (2 hours)

**Total actual uptime:** 98.9% (not even three nines)

**The lesson:** Stop promising impossible uptime. Instead, set **Service Level Objectives (SLOs)** based on what users actually need.

---

### Understanding SLI, SLO, and SLA

**Definitions:**

| Term | Definition | Example |
|------|------------|---------|
| **SLI** (Indicator) | What we measure | "P95 response time" |
| **SLO** (Objective) | Target for measurement | "P95 < 2 seconds" |
| **SLA** (Agreement) | Contractual commitment with consequences | "99.9% uptime or refund" |

**For our school absence system:**

```
SLI: Percentage of successful absence submissions
SLO: 99.5% of submissions succeed
Error Budget: 0.5% = 5 failed requests per 1,000

SLI: P95 response time for form submission  
SLO: 95th percentile < 2 seconds
Error Budget: 5% of requests can be slower

SLI: System availability (uptime)
SLO: 99.9% uptime per month
Error Budget: 43.8 minutes downtime allowed
```

**Why error budgets matter:**

If we're at 99.95% uptime (exceeding our 99.9% SLO), we have **budget to spend:**
- Deploy risky features
- Experiment with new tech
- Aggressive performance optimizations

If we're at 99.85% uptime (below SLO), we **freeze features:**
- Only critical bug fixes
- Focus on reliability
- Slow down and stabilize

**Interview talking point:** *"I use error budgets to balance innovation with reliability. SLOs aren't ceilings to hit—they're contracts with users. If we're exceeding SLO, we can take risks. If we're missing SLO, we focus on stability."*

---

## Production Monitoring with CloudWatch

### Our Monitoring Strategy

**Three types of alarms:**

1. **Symptom-based** (user-facing problems)
   - "Users can't submit forms" → ALB 5xx errors
   - "Form is slow" → P95 response time

2. **Cause-based** (infrastructure problems)
   - "EC2 instance failed" → Status check
   - "Target unhealthy" → ALB health check

3. **SLO-based** (error budget consumption)
   - "Approaching monthly downtime limit"
   - "Error rate trending toward breach"

**We prioritize symptom-based alarms** because they tell us what users experience.

---

### Implementing Monitoring in Terraform

**File: `modules/monitoring/main.tf`**

#### SNS Topic for Alerts

```hcl
# SNS Topic - central alerting hub
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
  
  tags = {
    Name = "${var.project_name}-alerts"
  }
}

# Email subscription (must confirm via email)
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

**How it works:**
1. Alarm triggers → Publishes to SNS topic
2. SNS → Emails subscribed addresses
3. You receive alert, investigate

**Production tip:** Use PagerDuty, Slack, or OpsGenie instead of email for real production systems. Email is fine for small teams.

---

#### EC2 Health Alarm (Infrastructure Monitoring)

```hcl
resource "aws_cloudwatch_metric_alarm" "ec2_status_check" {
  alarm_name          = "${var.project_name}-ec2-status-check-failed"
  alarm_description   = "EC2 instance status check failed - n8n may be down"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2          # 2 consecutive failures required
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60         # Check every 60 seconds
  statistic           = "Maximum"
  threshold           = 1          # Any failure triggers
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"  # Important!
  
  dimensions = {
    InstanceId = var.instance_id
  }
  
  tags = {
    Name = "${var.project_name}-ec2-health-alarm"
  }
}
```

**Configuration explained:**

**`evaluation_periods = 2`**
- Requires 2 consecutive failures before alarming
- **Why?** Prevents false alarms from brief hiccups
- **Math:** 2 periods × 60 seconds = 2 minutes to detect failure

**`period = 60`**
- Check every 60 seconds
- **Why?** Fast detection (infrastructure failures)
- **Tradeoff:** More frequent checks = more API calls (minimal cost)

**`statistic = "Maximum"`**
- Use the highest value in the period
- **Why?** For binary metrics (0 or 1), Maximum catches any failure
- **Alternative:** Average would be 0.5 if half the checks failed (confusing)

**`threshold = 1`**
- Trigger if value ≥ 1
- **Why?** Status checks return 0 (pass) or 1 (fail)

**`treat_missing_data = "notBreaching"`**
- If CloudWatch can't collect data, don't trigger alarm
- **Why?** Missing data usually means CloudWatch collection issue, not EC2 failure
- **Alternative:** `"breaching"` would alarm on missing data (too sensitive for AWS-managed metrics)

**Real-world scenario:**
```
8:00 AM: Instance healthy (StatusCheckFailed = 0)
8:01 AM: Instance fails (StatusCheckFailed = 1) - Evaluation 1
8:02 AM: Instance still failing (StatusCheckFailed = 1) - Evaluation 2 → ALARM
8:03 AM: SNS sends email
8:04 AM: You investigate
```

**Detection time:** 2 minutes

---

#### ALB Unhealthy Target Alarm (Application Monitoring)

```hcl
resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_targets" {
  alarm_name          = "${var.project_name}-alb-unhealthy-targets"
  alarm_description   = "ALB target is unhealthy - n8n not responding"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "breaching"  # Different from EC2!
  
  dimensions = {
    TargetGroup  = var.target_group_arn_suffix
    LoadBalancer = var.alb_arn_suffix
  }
  
  tags = {
    Name = "${var.project_name}-alb-unhealthy-alarm"
  }
}
```

**Why `treat_missing_data = "breaching"` here?**

This is a **key distinction** from the EC2 alarm:

**EC2 status checks (AWS-managed):**
- Missing data = CloudWatch collection issue (AWS problem)
- `notBreaching` = don't alarm on AWS infrastructure problems

**ALB health checks (application-level):**
- Missing data = ALB can't reach target (our problem)
- `breaching` = if we can't measure health, assume unhealthy

**Interview talking point:** *"I use different treat_missing_data strategies based on what the metric measures. For AWS-managed infrastructure metrics, missing data is usually a collection issue. For application health checks, missing data indicates a real problem—the ALB can't reach the backend."*

---

#### Response Time SLO Alarm (User Experience Monitoring)

```hcl
resource "aws_cloudwatch_metric_alarm" "response_time_slo" {
  alarm_name          = "${var.project_name}-response-time-slo"
  alarm_description   = "Response time SLO breach - 95th percentile exceeds 2 seconds"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300        # 5 minutes (not 60!)
  extended_statistic  = "p95"      # 95th percentile
  threshold           = 2          # 2 seconds
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
  
  tags = {
    Name = "${var.project_name}-response-time-slo-alarm"
  }
}
```

**This alarm is fundamentally different from the others:**

| Aspect | Infrastructure Alarms | SLO Alarm |
|--------|----------------------|-----------|
| **Purpose** | Detect failures | Track user experience |
| **Period** | 60 seconds | 300 seconds |
| **Why** | Fast detection | Trend analysis |
| **Statistic** | Maximum | p95 |
| **Why** | Binary (up/down) | Percentile (performance) |
| **Urgency** | Page immediately | Review during business hours |

**Why `extended_statistic = "p95"` instead of `statistic = "Average"`?**

**Average hides problems:**
```
Request 1: 100ms
Request 2: 150ms
Request 3: 200ms
Request 4: 5,000ms  ← One slow request

Average = 1,362ms (looks okay!)
P95 = 5,000ms (captures the outlier)
```

**P95 captures what 5% of users experience** (the slowest requests). This is what matters for SLOs.

**Why `period = 300` (5 minutes)?**
- SLO tracking looks at trends, not instant spikes
- One slow request shouldn't trigger an alarm
- 5 minutes smooths out noise
- Still responsive enough (10 minutes to detect sustained slowness)

**Real-world scenario:**
```
8:00-8:05: P95 = 1.8s (good)
8:05-8:10: P95 = 2.3s (slow) - Evaluation 1
8:10-8:15: P95 = 2.5s (still slow) - Evaluation 2 → ALARM
8:16: Email arrives: "Response time SLO breach - investigate"
```

**Detection time:** 10-15 minutes (acceptable for performance degradation)

---

### Monitoring Module Variables

**File: `modules/monitoring/variables.tf`**

```hcl
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "instance_id" {
  description = "EC2 instance ID to monitor"
  type        = string
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix for CloudWatch dimensions"
  type        = string
}

variable "target_group_arn_suffix" {
  description = "Target group ARN suffix for CloudWatch dimensions"
  type        = string
}

variable "alert_email" {
  description = "Email address for CloudWatch alarms"
  type        = string
}
```

**Why ARN suffix instead of full ARN?**

CloudWatch dimensions use ARN suffix:
```hcl
# Wrong
dimensions = {
  LoadBalancer = "arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/alb/xyz"
}

# Right
dimensions = {
  LoadBalancer = "app/alb/xyz"  # Just the suffix!
}
```

**We extract suffix in load_balancer module:**
```hcl
output "alb_arn_suffix" {
  value = aws_lb.main.arn_suffix  # Terraform provides this!
}
```

---

## CI/CD with GitHub Actions & OIDC

### The Problem with Traditional CI/CD

**The old way (DON'T do this):**

```yaml
# .github/workflows/deploy.yml
- name: Configure AWS Credentials
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_KEY }}
```

**Problems:**
- ❌ Long-lived credentials (keys never expire)
- ❌ If GitHub is compromised, attacker has permanent AWS access
- ❌ Must manually rotate keys
- ❌ Can't restrict by branch (any branch can use the key)
- ❌ Violates principle of least privilege

**Real-world horror story:** A company stored AWS keys in GitHub Secrets. An intern accidentally pushed them to a public repo's commit history. **$50,000 AWS bill** from crypto miners before they noticed.

---

### The Modern Way: OIDC (OpenID Connect)

**How OIDC works:**

```
1. GitHub Actions job starts
2. GitHub generates short-lived JWT token (signed by GitHub)
3. Job presents token to AWS STS (Security Token Service)
4. AWS verifies:
   - Is this really GitHub? (validates signature)
   - Is it the right repo? (checks token claims)
   - Is it the right branch? (checks ref)
5. AWS issues temporary credentials (15 min expiration)
6. Job uses credentials
7. Credentials automatically expire
```

**Benefits:**
- ✅ Zero long-lived secrets
- ✅ Credentials expire in 15 minutes (can't leak permanently)
- ✅ Can restrict by repo AND branch
- ✅ Audit trail in CloudTrail (every authentication logged)
- ✅ No manual rotation needed

---

### Terraform Implementation

**File: `modules/cicd/main.tf`**

#### GitHub OIDC Provider

```hcl
# One-time setup: Trust GitHub's OIDC provider
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  
  # GitHub's certificate thumbprints (static, provided by GitHub)
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]
  
  tags = {
    Name = "${var.project_name}-github-oidc"
  }
}
```

**What this does:** Establishes trust between AWS and GitHub.

---

#### IAM Role for GitHub Actions

```hcl
resource "aws_iam_role" "github_actions" {
  name        = "${var.project_name}-github-actions"
  description = "Role for GitHub Actions to deploy frontend"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          # CRITICAL: Only main branch of specific repo can assume
          "token.actions.githubusercontent.com:sub" = 
            "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
        }
      }
    }]
  })
  
  tags = {
    Name = "${var.project_name}-github-actions-role"
  }
}
```

**The security magic is in the Condition:**

```json
"token.actions.githubusercontent.com:sub" = 
  "repo:brent-hollers/absence-system-infrastructure:ref:refs/heads/main"
```

**This means:**
- ✅ ONLY the `brent-hollers/absence-system-infrastructure` repo
- ✅ ONLY the `main` branch
- ❌ Feature branches can't deploy
- ❌ Other repos can't assume this role
- ❌ Pull requests can't deploy (must merge first)

**Interview talking point:** *"I use OIDC trust policies to enforce GitOps workflows. Only merged code on main can deploy to production. This prevents accidental deployments from feature branches and enforces code review."*

---

#### Least-Privilege IAM Policy

```hcl
resource "aws_iam_policy" "github_actions" {
  name        = "${var.project_name}-github-actions-policy"
  description = "Minimum permissions for deploying frontend"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Upload"
        Effect = "Allow"
        Action = [
          "s3:PutObject",      # Upload files
          "s3:GetObject"       # Verify uploads
        ]
        Resource = "arn:aws:s3:::${var.s3_bucket_name}/*"
      },
      {
        Sid    = "CloudFrontInvalidation"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation",  # Clear cache
          "cloudfront:ListDistributions"    # Find distribution
        ]
        Resource = "*"  # ListDistributions requires wildcard
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions.arn
}
```

**What's allowed:**
- ✅ Upload files to specific S3 bucket
- ✅ Invalidate CloudFront cache

**What's NOT allowed:**
- ❌ Delete S3 objects
- ❌ Modify infrastructure (EC2, VPC, etc.)
- ❌ Access other S3 buckets
- ❌ Modify CloudFront distribution settings

**Principle:** Give just enough permission to do the job, nothing more.

---

### GitHub Actions Workflow

**File: `.github/workflows/deploy-frontend.yml`**

```yaml
name: Deploy Frontend to S3

on:
  push:
    branches:
      - main
    paths:
      - 'frontend/index.html'  # Only trigger when form changes

# Required for OIDC authentication
permissions:
  id-token: write  # Generate OIDC token
  contents: read   # Read repo code

jobs:
  deploy:
    name: Deploy to S3 and Invalidate CloudFront
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Configure AWS Credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::005608856189:role/absence-system-github-actions
          aws-region: us-east-1
      
      - name: Upload to S3
        run: |
          aws s3 cp frontend/index.html \
            s3://absence-system-frontend-xxx/index.html \
            --content-type "text/html" \
            --cache-control "max-age=300"
      
      - name: Get CloudFront Distribution ID
        id: cloudfront
        run: |
          DIST_ID=$(aws cloudfront list-distributions \
            --query "DistributionList.Items[?contains(Origins.Items[0].DomainName, 'absence-system-frontend')].Id" \
            --output text)
          echo "distribution_id=$DIST_ID" >> $GITHUB_OUTPUT
      
      - name: Invalidate CloudFront cache
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ steps.cloudfront.outputs.distribution_id }} \
            --paths "/index.html"
      
      - name: Deployment summary
        run: |
          echo "✅ Frontend deployed successfully!"
          echo "📦 S3 Bucket: absence-system-frontend-xxx"
          echo "🔗 URL: https://form.absences.smaschool.org"
```

**Workflow breakdown:**

**Trigger:**
```yaml
on:
  push:
    branches: [main]
    paths: ['frontend/index.html']
```
- Only runs when `index.html` changes on `main` branch
- Saves GitHub Actions minutes (don't run on README changes)

**OIDC authentication:**
```yaml
permissions:
  id-token: write  # THIS IS CRITICAL!
```
- Without this, GitHub won't generate OIDC tokens
- Common mistake: Forgetting this permission

**Cache control:**
```bash
--cache-control "max-age=300"
```
- Browsers/CDN cache for 5 minutes
- Balance: Fresh content vs. reduced S3 requests
- **Alternatives:**
  - `max-age=0`: No caching (always fetch latest)
  - `max-age=3600`: Cache for 1 hour (less fresh, cheaper)

**Dynamic distribution lookup:**
```bash
DIST_ID=$(aws cloudfront list-distributions ...)
```
- Don't hardcode distribution ID
- Works if distribution is recreated
- Workflow is portable

**Invalidation optimization:**
```bash
--paths "/index.html"
```
- Only invalidate what changed
- **Cost:** First 1,000 invalidations/month free, then $0.005/path
- Invalidating `/*` costs more and takes longer

---

### End-to-End Flow

**Developer workflow:**

```
1. Developer edits frontend/index.html locally
2. git add frontend/index.html
3. git commit -m "feat: add period selection"
4. git push origin main

   ↓ (GitHub detects push to main)

5. GitHub Actions starts workflow
6. GitHub generates OIDC token
7. Workflow assumes AWS IAM role (temporary credentials)
8. Upload index.html to S3 (replaces old version)
9. Invalidate CloudFront cache
10. Within 5 minutes: Changes live!

Total time: ~2-3 minutes
Developer involvement: Just git push
```

**Zero manual AWS console work!**

---

## Workflow Automation with n8n

### Business Logic Review

**Our absence request workflow:**

```
Teacher submits form
    ↓
Is date in the past? (already happened)
    ├─ YES → Auto-approve (retroactive sick leave)
    │         → Log to Google Sheets
    │         → Email confirmation to teacher
    │
    └─ NO → Send approval email to principal
               ↓
            Principal clicks Approve/Deny
               ↓
            If APPROVED:
               ├─ Coverage needed?
               │   ├─ YES → Email front desk (periods 1-8)
               │   └─ NO → Skip
               ├─ Log to Google Sheets
               └─ Email confirmation to teacher
            
            If DENIED:
               └─ Email teacher (explain next steps)
```

---

### n8n Implementation

**Node 1: Webhook Trigger**

```json
{
  "path": "/webhook/absence-request",
  "method": "POST",
  "responseMode": "onReceived",
  "authentication": "none"
}
```

**Receives data:**
```json
{
  "name": "Jane Doe",
  "email": "jane@smaschool.org",
  "date": "2026-02-20",
  "reason": "Medical appointment",
  "coverageNeeded": "yes",
  "periodsAbsent": ["Period 1", "Period 2", "Period 3"]
}
```

---

**Node 2: Code - Date Logic**

```javascript
// Check if request date is in the past
const requestDate = new Date(items[0].json.date);
const today = new Date();
today.setHours(0, 0, 0, 0);  // Normalize to midnight

const isPastDate = requestDate < today;

return items.map(item => ({
  json: {
    ...item.json,
    isPastDate: isPastDate,
    requiresApproval: !isPastDate,
    requestId: `REQ-${Date.now()}`,  // Unique ID for tracking
    timestamp: new Date().toISOString()
  }
}));
```

**What this adds:**
- `isPastDate`: Boolean for routing decision
- `requiresApproval`: Inverse (clearer naming)
- `requestId`: Unique identifier for this request
- `timestamp`: When workflow processed it

---

**Node 3: IF - Branch by Date**

```javascript
// Condition
{{ $json.isPastDate }} === true
```

**Creates two paths:**
- **TRUE path:** Past date → Auto-approve
- **FALSE path:** Future date → Approval workflow

---

**Node 4a (Past Date): Set - Format Data**

```javascript
{
  "status": "Approved - Retroactive",
  "approver": "System (Auto-approved sick leave)",
  "approvalDate": "{{ $now }}",
  "requiresCoverage": false
}
```

---

**Node 4b (Future Date): Gmail - Send Approval Request**

```html
<h2>Absence Request from {{ $json.name }}</h2>

<p><strong>Email:</strong> {{ $json.email }}</p>
<p><strong>Date:</strong> {{ $json.date }}</p>
<p><strong>Reason:</strong> {{ $json.reason }}</p>
<p><strong>Coverage Required:</strong> {{ $json.coverageNeeded }}</p>
<p><strong>Periods:</strong> {{ $json.periodsAbsent.join(', ') }}</p>

<p>
  <a href="https://absences.smaschool.org/webhook/approve?id={{ $json.requestId }}" 
     style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
    ✅ Approve Request
  </a>
  
  <a href="https://absences.smaschool.org/webhook/deny?id={{ $json.requestId }}" 
     style="background: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
    ❌ Deny Request
  </a>
</p>
```

**Principal receives email with:**
- All request details
- Two buttons (Approve/Deny)
- Clicking button triggers another webhook
- Request ID embedded in URL for tracking

---

**Node 5: Wait for Webhook (Approval Response)**

```json
{
  "path": "/webhook/approve",
  "method": "GET"
}
```

**Workflow pauses** until principal clicks button.

**When clicked:**
```
GET https://absences.smaschool.org/webhook/approve?id=REQ-1708534800000
```

**Workflow resumes** with approval decision.

---

**Node 6: IF - Check Coverage**

```javascript
{{ $json.coverageNeeded }} === "yes"
```

**If TRUE:**
- Email front desk with period details

**If FALSE:**
- Skip coverage notification

---

**Node 7: Gmail - Notify Front Desk**

```html
<h2>Coverage Needed: {{ $json.date }}</h2>

<p><strong>Teacher:</strong> {{ $json.name }}</p>
<p><strong>Date:</strong> {{ $json.date }}</p>
<p><strong>Periods requiring coverage:</strong></p>
<ul>
  {{ $json.periodsAbsent.map(p => `<li>${p}</li>`).join('') }}
</ul>

<p>Please arrange substitute coverage for the periods listed above.</p>
```

---

**Node 8: Google Sheets - Append Row**

```javascript
{
  "Name": "{{ $json.name }}",
  "Email": "{{ $json.email }}",
  "Date": "{{ $json.date }}",
  "Reason": "{{ $json.reason }}",
  "Status": "{{ $json.status }}",
  "Approver": "{{ $json.approver }}",
  "Coverage": "{{ $json.coverageNeeded }}",
  "Periods": "{{ $json.periodsAbsent.join(', ') }}",
  "Timestamp": "{{ $json.timestamp }}"
}
```

**Creates audit trail** in Google Sheets.

**Sheet columns:**
| Name | Email | Date | Reason | Status | Approver | Coverage | Periods | Timestamp |
|------|-------|------|--------|--------|----------|----------|---------|-----------|
| Jane Doe | jane@... | 2026-02-20 | Medical | Approved | Principal | yes | P1, P2, P3 | 2026-02-19T15:30:00Z |

---

**Node 9: Gmail - Confirmation to Teacher**

```html
<h2>Absence Request {{ $json.status }}</h2>

<p>Dear {{ $json.name }},</p>

<p>Your absence request for {{ $json.date }} has been {{ $json.status }}.</p>

<p><strong>Request Details:</strong></p>
<ul>
  <li>Date: {{ $json.date }}</li>
  <li>Reason: {{ $json.reason }}</li>
  <li>Status: {{ $json.status }}</li>
  <li>Request ID: {{ $json.requestId }}</li>
</ul>

<p>This request has been logged and the front desk has been notified.</p>
```

---

### Workflow as Code

**We export the workflow JSON and store in Git:**

```bash
workflows/
└── absence-approval-workflow.json
```

**Benefits:**
- ✅ Version controlled (track changes)
- ✅ Can diff between versions
- ✅ Can import to new n8n instance
- ✅ Part of infrastructure as code

**Importing workflow:**
```bash
# In n8n UI:
# Workflows → Import from File → Select JSON
# Or via API:
curl -X POST https://absences.smaschool.org/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d @workflows/absence-approval-workflow.json
```

---

## Testing Strategies

### Unit Testing (Individual Components)

**Test 1: Date logic**
```bash
curl -X POST http://localhost:5678/webhook-test/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-02-10",
    "name": "Test"
  }'

# Expected: isPastDate = true
```

**Test 2: Future date**
```bash
curl -X POST http://localhost:5678/webhook-test/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-03-01",
    "name": "Test"
  }'

# Expected: isPastDate = false, approval email sent
```

---

### Integration Testing (End-to-End)

**Test scenario: Complete approval workflow**

```bash
# 1. Submit future absence request
curl -X POST https://absences.smaschool.org/webhook/absence-request \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Integration Test",
    "email": "test@smaschool.org",
    "date": "2026-03-15",
    "reason": "Vacation",
    "coverageNeeded": "yes",
    "periodsAbsent": ["Period 1", "Period 2"]
  }'

# 2. Check email inbox - approval request received?
# 3. Click "Approve" button
# 4. Check Google Sheets - row added?
# 5. Check email - confirmation sent to teacher?
# 6. Check email - front desk notified of coverage?
```

**Success criteria:**
- ✅ Principal receives approval email within 30 seconds
- ✅ Google Sheets row appears
- ✅ Teacher receives confirmation email
- ✅ Front desk receives coverage notification
- ✅ All emails contain correct data

---

### Load Testing

**Simulate 100 concurrent requests:**

```bash
# Using Apache Bench
ab -n 100 -c 10 -p request.json -T application/json \
  https://absences.smaschool.org/webhook/absence-request

# Expected results:
# - All requests succeed (100%)
# - P95 response time < 2 seconds
# - No errors in CloudWatch logs
```

---

## Putting It All Together

**Complete deployment flow:**

```
Developer changes index.html
    ↓
git push origin main
    ↓
GitHub Actions (OIDC auth)
    ↓
Upload to S3 + Invalidate CloudFront
    ↓
Changes live in 5 minutes
    
Teacher submits form
    ↓
CloudFront serves form
    ↓
Form POSTs to ALB (HTTPS)
    ↓
ALB → EC2 (private subnet)
    ↓
n8n processes workflow
    ├─ Past date → Auto-approve
    └─ Future date → Principal approval
    ↓
Google Sheets logging
    ↓
Email confirmations
    
CloudWatch monitors
    ├─ EC2 health
    ├─ ALB targets
    └─ Response time (SLO)
    ↓
SNS alerts if threshold exceeded
```

**Everything is automated.**

---

## Key Takeaways

1. **SLOs > uptime promises** - Error budgets balance innovation with reliability
2. **Different alarms need different configurations** - Infrastructure (60s), SLO (300s), treat_missing_data varies
3. **OIDC eliminates credential management** - Zero long-lived secrets, branch restrictions built-in
4. **Workflow as code** - n8n JSON in Git, just like Terraform
5. **Testing is multi-layered** - Unit tests (components), integration tests (E2E), load tests (scale)
6. **Automation compounds** - CI/CD + monitoring + workflows = fully operational system

---

## What's Next

We've built the complete operational stack—infrastructure, monitoring, CI/CD, and workflows.

**In Part 4 (final article)**, we'll reflect on:
- What worked, what didn't, what we'd change
- Cost analysis and optimization strategies
- Scaling beyond one school (multi-tenant)
- Security hardening for production
- Future enhancements roadmap
- Lessons for your next project

---

*This is Part 3 of a 4-part series. [Part 4: Lessons Learned - Cost, Challenges, and What's Next](./part-4-lessons-learned.md) wraps up with honest reflections and future thinking.*

**Questions?** Connect on [LinkedIn](https://linkedin.com/in/brent-hollers) or explore the [GitHub repo](https://github.com/brent-hollers/absence-system-infrastructure).

---

**Tags:** #DevOps #CI/CD #CloudWatch #Monitoring #SRE #GitHubActions #OIDC #Automation #n8n