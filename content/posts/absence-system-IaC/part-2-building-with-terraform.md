---
title: "Building Secure, Modular Infrastructure with Terraform"
subtitle: "Building Production-Grade Infrastructure - Part 2 of 4"
date: 2026-02-19
author: Dr. Brent Hollers
tags: [Terraform, AWS, VPC, Security, IaC, DevOps, Cloud Architecture]
series: "Building Production-Grade Infrastructure"
part: 2
description: "A deep dive into Terraform module design, VPC networking, HTTPS implementation, and security best practices with real production code examples."
---

# Building Secure, Modular Infrastructure with Terraform

*Part 2 of 4: Building Production-Grade Infrastructure*

---

## From Design to Implementation

In [Part 1](./part-1-from-manual-chaos-to-iac.md), we explored **why** we chose Infrastructure as Code and **what** architecture we designed. We made critical decisions about cloud providers, networking, security, and workflow automation.

Now comes the **how**: implementing these decisions in Terraform with production-ready patterns.

**By the end of this article, you'll understand:**
- Modular Terraform design philosophy
- VPC networking with public/private subnet isolation
- Security group least-privilege implementation  
- HTTPS with Application Load Balancer and ACM
- Common pitfalls and how to avoid them

**Target audience:** This is hands-on. We're writing real Terraform code, explaining every decision, and showing patterns you can use immediately.

---

## Terraform Module Philosophy

### The Monolith Problem

Early in my career, I wrote Terraform like this:

```hcl
# main.tf - 1,247 lines of resources
resource "aws_vpc" "main" { ... }
resource "aws_subnet" "public_1" { ... }
resource "aws_subnet" "public_2" { ... }
resource "aws_subnet" "private" { ... }
resource "aws_security_group" "alb" { ... }
resource "aws_security_group" "ec2" { ... }
resource "aws_instance" "web" { ... }
resource "aws_lb" "main" { ... }
# ... 50 more resources ...
```

**Problems with this approach:**
- ❌ Impossible to navigate (1000+ lines)
- ❌ Can't reuse code across projects
- ❌ Testing individual components is painful
- ❌ Changes to networking affect compute (blast radius)
- ❌ No clear ownership (who maintains what?)

**After my first production outage caused by a networking change that broke compute, I learned modules the hard way.**

---

### Our Module Structure

```
infrastructure/
├── modules/
│   ├── networking/      # VPC, subnets, NAT, security groups
│   ├── compute/         # EC2, IAM roles, user data
│   ├── load_balancer/   # ALB, target groups, listeners
│   ├── frontend/        # S3, CloudFront
│   ├── dns/             # ACM certificate references
│   ├── monitoring/      # CloudWatch alarms, SNS
│   └── cicd/            # GitHub Actions IAM (OIDC)
├── main.tf              # Orchestrates modules
├── backend.tf           # S3 remote state
├── variables.tf         # Input parameters
└── outputs.tf           # Exposed values
```

---

### Module Design Principles

**1. Single Responsibility**

Each module does ONE thing well. 

**Bad:**
```hcl
# A "web-app" module that creates VPC + EC2 + ALB
module "web_app" {
  source = "./modules/web-app"
  # This is too coarse - can't change networking without touching compute
}
```

**Good:**
```hcl
# Separate concerns
module "networking" { source = "./modules/networking" }
module "compute" { source = "./modules/compute" }
module "load_balancer" { source = "./modules/load_balancer" }
```

**Why this matters:**
- Networking changes rarely, compute changes frequently
- Different teams can own different modules
- Can test modules independently
- Blast radius is contained

---

**2. Clear Interfaces**

Modules should have well-defined inputs (variables) and outputs.

**Module contract example:**

```hcl
# modules/networking/variables.tf
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# modules/networking/outputs.tf
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_id" {
  description = "ID of private subnet for compute resources"
  value       = aws_subnet.private.id
}
```

**Why this matters:**
- Inputs document what's configurable
- Outputs define what other modules can depend on
- Clear contracts prevent tight coupling

---

**3. Reusability**

Same module works for dev/staging/prod with different inputs.

```hcl
# Development environment
module "networking" {
  source       = "./modules/networking"
  project_name = "absence-system-dev"
  vpc_cidr     = "10.1.0.0/16"
}

# Production environment
module "networking" {
  source       = "./modules/networking"
  project_name = "absence-system-prod"
  vpc_cidr     = "10.0.0.0/16"
}
```

**Interview talking point:** *"I design modules to be environment-agnostic. The same code deploys to dev, staging, and prod—only the inputs change. This ensures environment parity and reduces configuration drift."*

---

**4. Testability**

Can test modules independently before integration.

```bash
# Test networking module alone
cd modules/networking
terraform init
terraform plan

# Test compute module with mock networking outputs
cd ../compute
terraform plan \
  -var="subnet_id=subnet-12345" \
  -var="security_group_id=sg-67890"
```

---

## Deep Dive: Networking Module

Let's build the foundation—the networking module.

### The VPC Foundation

**File: `modules/networking/main.tf`**

```hcl
# VPC - Our private cloud network
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true  # Important for ALB DNS resolution
  enable_dns_support   = true  # Required for Route53 private zones
  
  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Data source - dynamically get available AZs
data "aws_availability_zones" "available" {
  state = "available"
}
```

**Why these settings?**

- `cidr_block = "10.0.0.0/16"`: Gives us 65,536 IP addresses (10.0.0.0 → 10.0.255.255)
- `enable_dns_hostnames = true`: ALB needs DNS resolution to work
- `enable_dns_support = true`: Enables AWS DNS server at 10.0.0.2

**Common mistake to avoid:** Forgetting `enable_dns_hostnames` causes mysterious ALB failures later. Always enable for VPCs with load balancers.

---

### Public Subnets (For ALB and NAT Gateway)

```hcl
# Public subnets - 2 required for ALB (multi-AZ)
resource "aws_subnet" "public" {
  count = 2
  
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true  # Auto-assign public IPs
  
  tags = {
    Name = "${var.project_name}-public-${count.index + 1}"
  }
}
```

**Subnet math breakdown:**
- Subnet 0: `10.0.1.0/24` → 256 IPs (10.0.1.0 - 10.0.1.255)
- Subnet 1: `10.0.2.0/24` → 256 IPs (10.0.2.0 - 10.0.2.255)

**Why `/24` subnets?**
- Smaller than VPC CIDR (`/16`), leaves room for more subnets
- 256 IPs is plenty for ALB and NAT Gateway
- Standard subnet size (easy for other engineers to understand)

**Why `count = 2` (two subnets)?**
- ALB requires subnets in at least 2 availability zones
- Multi-AZ provides high availability
- If one AZ fails, ALB still works

**Why `map_public_ip_on_launch = true`?**
- NAT Gateway needs a public IP
- Resources in public subnets can reach internet directly
- Private subnets will NOT have this (intentional!)

---

### Private Subnet (For EC2 - No Public IP!)

```hcl
# Private subnet - where EC2 lives (NO public IP!)
resource "aws_subnet" "private" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.10.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false  # CRITICAL: No public IPs!
  
  tags = {
    Name = "${var.project_name}-private"
  }
}
```

**Security principle:** `map_public_ip_on_launch = false` ensures EC2 instances CANNOT accidentally get internet-routable IPs.

**Why CIDR `10.0.10.0/24` instead of `10.0.3.0/24`?**
- Leaves room for future public subnets (10.0.3.0, 10.0.4.0, etc.)
- Makes it obvious in AWS console which subnets are private (10.0.10+)
- Convention, not requirement—just good practice

---

### Internet Gateway (For Public Internet Access)

```hcl
# Internet Gateway - allows VPC to reach internet
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  
  tags = {
    Name = "${var.project_name}-igw"
  }
}
```

**What it does:** Allows resources with public IPs to communicate with the internet (bidirectional).

---

### NAT Gateway (For Private Subnet Outbound Access)

```hcl
# Elastic IP for NAT Gateway (static public IP)
resource "aws_eip" "nat" {
  domain = "vpc"
  
  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

# NAT Gateway - allows private subnet to reach internet (outbound only)
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id  # Must be in public subnet!
  
  tags = {
    Name = "${var.project_name}-nat-gw"
  }
  
  depends_on = [aws_internet_gateway.main]  # IGW must exist first
}
```

**Why NAT Gateway?**

EC2 in private subnet needs to:
- ✅ Download package updates (yum, apt)
- ✅ Call Gmail API (send emails)
- ✅ Pull Docker images
- ❌ Accept inbound connections from internet (prevented!)

**NAT Gateway = one-way door:**
- Outbound: ✅ Private subnet → NAT → Internet
- Inbound: ❌ Internet cannot initiate connections to private subnet

**Why `depends_on = [aws_internet_gateway.main]`?**
- NAT Gateway needs IGW to exist
- Explicit dependency prevents race condition
- Without this, Terraform might try to create them simultaneously and fail

**Cost consideration:** NAT Gateway costs ~$32/month. For production, worth it. For dev environments, consider:
- NAT instance (t3.nano ~$5/month) - less reliable, manual management
- VPC endpoints (if only calling AWS services) - $7/month per endpoint
- No NAT (if compute doesn't need internet) - free

---

### Route Tables (The Traffic Cops)

```hcl
# Public route table - internet traffic goes to IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block = "0.0.0.0/0"  # All internet traffic
    gateway_id = aws_internet_gateway.main.id
  }
  
  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

# Private route table - internet traffic goes to NAT Gateway
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block     = "0.0.0.0/0"  # All internet traffic
    nat_gateway_id = aws_nat_gateway.main.id
  }
  
  tags = {
    Name = "${var.project_name}-private-rt"
  }
}

# Associate public subnets with public route table
resource "aws_route_table_association" "public" {
  count = 2
  
  subnet_id      = aws_subnet.public[count.index].id
  route_table_association_id = aws_route_table.public.id
}

# Associate private subnet with private route table
resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}
```

**What's happening:**

| Subnet Type | Destination | Next Hop | What This Means |
|-------------|-------------|----------|-----------------|
| Public | 0.0.0.0/0 | IGW | "Any internet traffic goes directly to Internet Gateway" |
| Private | 0.0.0.0/0 | NAT GW | "Any internet traffic goes through NAT Gateway" |

**Flow example - EC2 in private subnet calls Gmail API:**
```
1. EC2 (10.0.10.50) → "I need to reach gmail.com"
2. Route table: "0.0.0.0/0 matches, send to NAT Gateway"
3. NAT Gateway: "I'll translate your private IP to my public IP"
4. NAT Gateway → Internet Gateway → Gmail servers
5. Response comes back, NAT translates back to EC2's private IP
6. EC2 receives response
```

**Security benefit:** Gmail API never sees EC2's private IP. Can't reach it directly even if compromised.

---

### Security Groups - Least Privilege in Action

**Security groups are stateful firewalls.** Every rule should have a clear purpose.

**ALB Security Group:**

```hcl
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id
  
  # Allow HTTPS from anywhere (public-facing)
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }
  
  # Allow HTTP from anywhere (will redirect to HTTPS)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from internet (redirects to HTTPS)"
  }
  
  # Allow outbound ONLY to EC2 on port 5678
  egress {
    from_port       = 5678
    to_port         = 5678
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]  # Reference by ID, not CIDR!
    description     = "Forward to n8n on EC2"
  }
  
  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}
```

**Key security decisions:**

1. **`cidr_blocks = ["0.0.0.0/0"]` for ingress:** ALB is public-facing, must accept traffic from internet
2. **`security_groups = [aws_security_group.ec2.id]` for egress:** This is powerful!
   - NOT using `cidr_blocks = ["10.0.10.0/24"]` (entire private subnet)
   - Using security group ID creates dynamic relationship
   - Only traffic to resources with ec2 security group is allowed
   - If EC2 IP changes, rule still works

**Interview talking point:** *"I reference security groups by ID instead of CIDR blocks because it creates a logical relationship, not a network-based one. If the EC2 instance moves to a different IP, the rule still works. This is more precise than allowing entire subnets."*

---

**EC2 Security Group:**

```hcl
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Security group for EC2 instance running n8n"
  vpc_id      = aws_vpc.main.id
  
  # Allow ONLY from ALB on port 5678
  ingress {
    from_port       = 5678
    to_port         = 5678
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]  # ONLY from ALB!
    description     = "n8n from ALB only"
  }
  
  # Allow all outbound (needs to call APIs, download packages)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic (via NAT Gateway)"
  }
  
  tags = {
    Name = "${var.project_name}-ec2-sg"
  }
}
```

**Security analysis:**

**Ingress:**
- ✅ Port 5678 ONLY (n8n)
- ✅ From ALB ONLY (not internet, not other resources)
- ✅ No SSH port 22 (access via Systems Manager instead)
- ✅ No RDP, no databases, no other services

**Egress:**
- ✅ All outbound allowed (EC2 needs to call Gmail API, download updates)
- ⚠️ Could be more restrictive in paranoid environments (specific IP ranges)
- ✅ Goes through NAT Gateway (private IP hidden)

**What we're preventing:**
- ❌ Direct internet access to EC2
- ❌ EC2 accepting connections from anything except ALB
- ❌ SSH access from internet (even if someone opens port 22)
- ❌ Lateral movement (EC2 can't talk to other resources in VPC unless explicitly allowed)

---

### Module Outputs

**File: `modules/networking/outputs.tf`**

```hcl
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_id" {
  description = "ID of private subnet for compute"
  value       = aws_subnet.private.id
}

output "alb_security_group_id" {
  description = "Security group ID for ALB"
  value       = aws_security_group.alb.id
}

output "ec2_security_group_id" {
  description = "Security group ID for EC2"
  value       = aws_security_group.ec2.id
}

output "nat_gateway_ip" {
  description = "Public IP of NAT Gateway (for allowlist purposes)"
  value       = aws_eip.nat.public_ip
}
```

**Why these outputs?**
- Other modules need these IDs to create resources in the VPC
- `vpc_id`: Required for almost all resources
- `public_subnet_ids`: ALB needs these (multi-AZ requirement)
- `private_subnet_id`: EC2 goes here
- Security group IDs: Other modules reference for rules
- `nat_gateway_ip`: If external APIs need to allowlist our traffic

---

## Deep Dive: HTTPS with Application Load Balancer

**The challenge:** n8n runs on plain HTTP port 5678. We need HTTPS for production.

**The solution:** Application Load Balancer terminates SSL/TLS.

### The Flow

```
User types: https://absences.smaschool.org
    ↓
DNS resolves to ALB IP
    ↓
User connects to ALB port 443 (HTTPS)
    ↓
ALB uses ACM certificate to establish TLS
    ↓
ALB decrypts HTTPS request
    ↓
ALB forwards plain HTTP to EC2 port 5678
    ↓
n8n processes request, responds with plain HTTP
    ↓
ALB encrypts response with TLS
    ↓
User receives HTTPS response (secure!)
```

**Benefits of this approach:**
- ✅ EC2 doesn't manage certificates (simpler)
- ✅ Certificate renewal handled by AWS
- ✅ Can add/remove backend servers easily
- ✅ ALB health checks ensure traffic only goes to healthy targets

---

### Load Balancer Module

**File: `modules/load_balancer/main.tf`**

```hcl
# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false  # Internet-facing
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids  # Must be 2+ AZs
  
  enable_deletion_protection = false  # Set true in production!
  
  tags = {
    Name = "${var.project_name}-alb"
  }
}

# Target Group - defines backend targets and health checks
resource "aws_lb_target_group" "main" {
  name     = "${var.project_name}-tg"
  port     = 5678
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  
  health_check {
    enabled             = true
    healthy_threshold   = 2      # 2 consecutive successes = healthy
    unhealthy_threshold = 2      # 2 consecutive failures = unhealthy
    timeout             = 5      # 5 second timeout
    interval            = 30     # Check every 30 seconds
    path                = "/"    # n8n homepage
    matcher             = "200"  # Expect HTTP 200
  }
  
  tags = {
    Name = "${var.project_name}-tg"
  }
}

# Register EC2 instance with target group
resource "aws_lb_target_group_attachment" "main" {
  target_group_arn = aws_lb_target_group.main.arn
  target_id        = var.instance_id
  port             = 5678
}
```

**Health check tuning:**

- `healthy_threshold = 2`: Requires 2 consecutive successes before routing traffic (prevents flapping)
- `unhealthy_threshold = 2`: Requires 2 consecutive failures before removing (tolerates transient errors)
- `interval = 30`: Check every 30 seconds (balance between responsiveness and cost)
- `timeout = 5`: If no response in 5 seconds, consider it a failure
- `path = "/"`: n8n homepage (lightweight check)

**Math:** If instance fails, detected in 30-60 seconds (1-2 intervals). If instance recovers, back in rotation in 60 seconds.

---

### HTTPS Listener

```hcl
# HTTPS Listener (port 443) - where users connect
resource "aws_lb_listener" "https" {
  count = var.enable_https && var.certificate_arn != "" ? 1 : 0
  
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"  # Modern TLS only
  certificate_arn   = var.certificate_arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
  
  tags = {
    Name = "${var.project_name}-https-listener"
  }
}
```

**Key decisions:**

1. **`ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"`**
   - Only TLS 1.2 and 1.3 (modern, secure)
   - Rejects TLS 1.0, 1.1 (vulnerable)
   - Balance between security and compatibility

2. **Conditional creation:** `count = var.enable_https ? 1 : 0`
   - Allows disabling HTTPS for dev environments
   - Production should ALWAYS have this enabled

3. **`certificate_arn`:** Passed from DNS module (created via ACM)

---

### HTTP → HTTPS Redirect

```hcl
# HTTP Listener (port 80) - redirect to HTTPS
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type = var.enable_https ? "redirect" : "forward"
    
    # If HTTPS enabled, redirect
    dynamic "redirect" {
      for_each = var.enable_https ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"  # Permanent redirect
      }
    }
    
    # If HTTPS not enabled, forward to target group
    target_group_arn = var.enable_https ? null : aws_lb_target_group.main.arn
  }
  
  tags = {
    Name = "${var.project_name}-http-listener"
  }
}
```

**What happens:**

```
User visits: http://absences.smaschool.org
    ↓
ALB HTTP listener (port 80)
    ↓
Returns HTTP 301 (permanent redirect)
    Location: https://absences.smaschool.org
    ↓
Browser automatically follows redirect
    ↓
User lands on HTTPS version
```

**Why HTTP 301 instead of 302?**
- `301`: Permanent redirect (browsers cache it)
- `302`: Temporary redirect (browsers don't cache)
- We use 301 because HTTP should ALWAYS redirect to HTTPS

**Dynamic block explained:**
```hcl
dynamic "redirect" {
  for_each = var.enable_https ? [1] : []
  content { ... }
}
```
- If `enable_https = true`: `[1]` creates one redirect block
- If `enable_https = false`: `[]` creates zero redirect blocks
- This is Terraform's way of doing conditional blocks

---

### ACM Certificate Integration

**File: `modules/dns/main.tf`**

```hcl
# Reference existing ACM certificate
data "aws_acm_certificate" "main" {
  domain   = var.domain_name
  statuses = ["ISSUED"]
  
  # Certificates must be in us-east-1 for CloudFront
  # For ALB, must be in same region as ALB
  provider = aws.us-east-1  # Adjust based on use case
}
```

**Important lesson learned:** 
- CloudFront requires certificates in `us-east-1` (global service)
- ALB requires certificates in same region as ALB
- If using both, you need TWO certificates (one per region)

**We use `data` source instead of creating certificate because:**
- Certificate already requested manually (DNS validation required)
- DNS provider (mysitearea.com) not managed by Terraform
- Could automate with Route53, but that's overkill for one domain

---

## Putting It All Together: Root Module Orchestration

**File: `infrastructure/main.tf`**

```hcl
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Default tags applied to ALL resources
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Module 1: Networking (no dependencies)
module "networking" {
  source = "./modules/networking"
  
  project_name = var.project_name
  vpc_cidr     = "10.0.0.0/16"
}

# Module 2: Compute (depends on networking outputs)
module "compute" {
  source = "./modules/compute"
  
  project_name      = var.project_name
  subnet_id         = module.networking.private_subnet_id
  security_group_id = module.networking.ec2_security_group_id
  n8n_domain        = var.domain_name
  enable_https      = var.enable_https
}

# Module 3: DNS (can run in parallel with compute)
module "dns" {
  count  = var.enable_https ? 1 : 0
  source = "./modules/dns"
  
  domain_name = var.domain_name
}

# Module 4: Load Balancer (depends on networking + compute + dns)
module "load_balancer" {
  source = "./modules/load_balancer"
  
  project_name           = var.project_name
  vpc_id                 = module.networking.vpc_id
  public_subnet_ids      = module.networking.public_subnet_ids
  alb_security_group_id  = module.networking.alb_security_group_id
  instance_id            = module.compute.instance_id
  enable_https           = var.enable_https
  certificate_arn        = var.enable_https ? module.dns[0].certificate_arn : ""
}

# Module 5: Frontend (depends on nothing - can be created anytime)
module "frontend" {
  source = "./modules/frontend"
  
  project_name    = var.project_name
  custom_domain   = var.frontend_domain
  certificate_arn = var.frontend_certificate_arn
}
```

---

### Terraform Dependency Graph

**Terraform automatically builds a dependency graph by analyzing resource references.**

```
networking (no dependencies)
   ├─ outputs: vpc_id, subnet_ids, security_group_ids
   ↓
compute (needs networking outputs)
   ├─ uses: private_subnet_id, ec2_security_group_id
   ├─ outputs: instance_id
   ↓
load_balancer (needs networking + compute outputs)
   ├─ uses: vpc_id, public_subnet_ids, alb_sg_id, instance_id
   ├─ outputs: alb_dns_name
   ↓
frontend (independent - could run anytime)
   ├─ uses: project_name
   ├─ outputs: cloudfront_url
```

**Interview talking point:** *"Terraform is declarative, not procedural. I don't specify execution order—Terraform analyzes dependencies and creates resources in the correct sequence. Module order in my code is for human readability, not execution order."*

---

## Common Pitfalls & Solutions

### Pitfall 1: Circular Dependencies

**Problem:**
```hcl
# Compute module wants ALB DNS
module "compute" {
  alb_dns_name = module.load_balancer.alb_dns_name  # Needs load_balancer
}

# Load Balancer wants instance ID
module "load_balancer" {
  instance_id = module.compute.instance_id  # Needs compute
}

# ERROR: Cycle detected!
```

**Solution 1: Make dependencies optional**
```hcl
module "compute" {
  alb_dns_name = var.alb_dns_name  # Optional, defaults to ""
}

# n8n auto-detects hostname from HTTP headers
# Workaround: Not ideal, but works
```

**Solution 2: Two-stage deployment**
```bash
terraform apply -target=module.networking
terraform apply -target=module.compute
terraform apply  # Everything else
```

**Solution 3: Use data sources (query after creation)**
```hcl
data "aws_lb" "main" {
  name = "${var.project_name}-alb"
}

# Use in compute module
alb_dns_name = data.aws_lb.main.dns_name
```

**Best solution for production:** Separate infrastructure (Terraform) from configuration (Ansible). We'll discuss this in Part 4.

---

### Pitfall 2: Hardcoded Values

**Bad:**
```hcl
resource "aws_subnet" "private" {
  cidr_block = "10.0.10.0/24"  # Hardcoded!
  # What if we want to change the VPC CIDR later?
}
```

**Good:**
```hcl
variable "vpc_cidr" {
  default = "10.0.0.0/16"
}

locals {
  private_subnet_cidr = cidrsubnet(var.vpc_cidr, 8, 10)
  # Dynamically calculates 10.0.10.0/24 from VPC CIDR
}

resource "aws_subnet" "private" {
  cidr_block = local.private_subnet_cidr
}
```

---

### Pitfall 3: No Destroy Protection

**Problem:** Accidental `terraform destroy` wipes production.

**Solution:**
```hcl
resource "aws_vpc" "main" {
  # ... other config ...
  
  lifecycle {
    prevent_destroy = true  # Terraform will error if trying to destroy
  }
}
```

**Use for:**
- Databases (RDS)
- S3 buckets with important data
- VPCs in production

---

### Pitfall 4: Missing IAM Permissions

**Problem:** Terraform plan succeeds, apply fails midway with:
```
Error: Insufficient permissions to create NAT Gateway
```

**Solution:** Test IAM permissions before big deployments.

```bash
# Dry run with terraform plan
terraform plan -out=tfplan

# Review plan carefully
terraform show tfplan

# Apply only if confident
terraform apply tfplan
```

**Least-privilege IAM for Terraform:**
```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "elasticloadbalancing:*",
        "s3:*",
        "cloudfront:*",
        "iam:*",
        "acm:*"
      ],
      "Resource": "*"
    }
  ]
}
```

**Note:** `*` permissions are broad. Production should use more restrictive policies with resource-specific ARNs.

---

## Deployment Process

### Step 1: Bootstrap (One-Time)

**Create S3 backend for remote state:**

```bash
cd infrastructure/bootstrap
terraform init
terraform apply

# Outputs:
# backend_bucket_name = "hollers-absence-tfstate-005608856189"
# dynamodb_table = "absence-system-terraform-locks"
```

**Copy outputs to `infrastructure/backend.tf`:**

```hcl
terraform {
  backend "s3" {
    bucket         = "hollers-absence-tfstate-005608856189"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "absence-system-terraform-locks"
    encrypt        = true
  }
}
```

---

### Step 2: Deploy Infrastructure

```bash
cd infrastructure

# Initialize with remote backend
terraform init

# Format code (consistency)
terraform fmt -recursive

# Validate syntax
terraform validate

# Preview changes
terraform plan

# Apply (creates ~30 resources)
terraform apply
```

**What gets created:**

| Category | Resources | Count |
|----------|-----------|-------|
| **Networking** | VPC, IGW, NAT, EIP, Subnets, Route Tables, Associations, Security Groups | ~14 |
| **Compute** | EC2, IAM Role, Instance Profile, Policy Attachments | ~4 |
| **Load Balancer** | ALB, Target Group, Attachment, Listeners (HTTP, HTTPS) | ~5 |
| **Frontend** | S3 Bucket, CloudFront, OAC, Bucket Policy | ~4 |
| **Monitoring** | CloudWatch Alarms, SNS Topic, Subscription | ~5 |
| **CI/CD** | OIDC Provider, IAM Role, Policy, Attachment | ~4 |

**Total:** 30+ resources

**Deployment time:** ~10-15 minutes (CloudFront takes longest)

---

### Step 3: Verify Deployment

```bash
# Get outputs
terraform output

# Should show:
# alb_url = "https://absences.smaschool.org"
# cloudfront_url = "https://form.absences.smaschool.org"
# ec2_instance_id = "i-0742d677db10dbec7"
# vpc_id = "vpc-0adbd57db722f569e"

# Test HTTPS
curl -I https://absences.smaschool.org
# Should return HTTP/2 200
```

---

## Cost Breakdown (Monthly)

| Service | Cost | Explanation |
|---------|------|-------------|
| **NAT Gateway** | $32.85 | $0.045/hour + $0.045/GB processed |
| **ALB** | $16.20 | $0.0225/hour |
| **EC2 t3.micro** | $7.50 | On-demand pricing |
| **Elastic IP (NAT)** | $3.65 | $0.005/hour (attached to NAT) |
| **S3 + CloudFront** | $1.50 | Minimal storage, low traffic |
| **CloudWatch** | $1.00 | 3 alarms, basic metrics |
| **Route53** | $0.50 | 2 hosted zones |
| **Data Transfer** | $2.00 | Mostly covered by free tier |
| **DynamoDB** | $0.00 | State locking (free tier) |
| **SNS** | $0.00 | Low volume (free tier) |
| **Total** | **~$65/month** | |

**50% of cost is NAT Gateway.** Consider optimization strategies in Part 4.

---

## Key Takeaways

1. **Modules enable reusability and testability** - Single responsibility, clear interfaces
2. **Security groups by ID, not CIDR** - Creates logical relationships, not network dependencies
3. **Private subnet isolation is foundational** - Design it in from day one, hard to retrofit
4. **ALB SSL termination simplifies certificate management** - Let AWS handle renewal
5. **Terraform dependency graph is automatic** - Focus on clean module design, let Terraform optimize
6. **Remote state + locking prevents conflicts** - Essential for team collaboration
7. **Test with `plan`, verify with `show`** - Catch issues before production

---

## What's Next

We've built the foundation—secure, modular infrastructure with Terraform.

**In Part 3**, we'll make it operational:
- CloudWatch monitoring with SLO tracking
- GitHub Actions CI/CD with OIDC (zero secrets!)
- n8n workflow automation
- End-to-end testing strategies

**You'll learn:**
- Setting up production monitoring
- Automated deployment pipelines
- Workflow-as-code patterns
- Testing infrastructure changes

---

*This is Part 2 of a 4-part series. [Part 3: Automating Everything - CI/CD, Monitoring, and Workflows](./part-3-automating-everything.md) shows how to make this infrastructure production-ready.*

**Questions?** Connect on [LinkedIn](https://linkedin.com/in/brent-hollers) or explore the [GitHub repo](https://github.com/brent-hollers/absence-system-infrastructure).

---

**Tags:** #Terraform #AWS #VPC #Security #DevOps #IaC #CloudArchitecture #Networking #HTTPS