---
title: "How I Built a $7/Month DNS Caching Resolver for a K-12 School Using AWS and Terraform"
subtitle: "Improving Latency in an Educational Environment"
date: 2026-03-20
author: Dr. Brent Hollers
tags: [DevOps, Infrastructure as Code, Terraform, AWS, System Design]
series: "Optimizing Enterprise Infrastructure"
part: 1
description: "How I built a DNS through VPN system that decreases latency and improves cached responses on the cheap."
---

# 

*By Dr. Brent Hollers | Director of Information Technology, St. Mary's Academy*

---

Every year, PSAT morning arrives like a controlled fire drill. Hundreds of Chromebooks come online simultaneously, every student navigating to the same handful of testing URLs. The network holds. The internet connection holds. But something subtle bogs down the experience in those first critical minutes: DNS.

Most IT professionals don't think about DNS until something breaks. I didn't either — until I started looking at where time was actually being lost during high-concurrency events at our school. Every single device was firing DNS queries at external resolvers (Cloudflare, Google) independently, with no local caching. The same hostname, resolved a thousand times, with zero shared benefit. It was like every student in the building individually calling 411 to ask for the same phone number.

The fix turned out to be elegant, surprisingly affordable, and a great excuse to apply some cloud architecture skills to a real-world education problem.

---

## The Problem in Plain Terms

When a student's Chromebook wants to reach `collegeboard.org`, it first asks a DNS resolver to translate that name into an IP address. Without a local caching resolver, that query goes all the way to an external server — adding 20 to 50 milliseconds every single time, for every single device.

In normal usage, that's barely noticeable. But multiply it by 300 students hitting the same URLs within the same two-minute window, and you start to feel it. Page loads stall. Testing platforms are slow to initialize. Teachers get frustrated. The help desk gets calls.

The solution is a **caching DNS resolver** — a server that sits close to your network, answers repeated queries from memory, and only reaches out to the internet when it genuinely doesn't know the answer yet. Once one device resolves `collegeboard.org`, every subsequent device on the network gets the answer instantly from cache.

---

## Why AWS Instead of a Local Box

Our school already had an AWS environment with an active Site-to-Site VPN back to our Unifi UDM Pro firewall. The VPN gives us low-latency, private connectivity between the school network and our AWS VPC — which means an EC2 instance in AWS is effectively just another device on our private network.

Putting the DNS resolver in AWS instead of on-premises gave us a few advantages:

- **No hardware to manage.** No physical box to fail, overheat, or get accidentally unplugged.
- **Rebuild from code.** The entire server is defined in Terraform. If it ever needs to be recreated, one command brings it back exactly as it was.
- **Existing infrastructure reuse.** The VPN was already there. The AWS account was already there. Marginal cost was near zero.

The total monthly cost for this setup: **around $7**.

---

## The Stack

Here's what's running:

- **AWS EC2 t4g.micro** — ARM-based Graviton instance running Ubuntu 22.04 LTS (~$6.14/month)
- **Unbound** — a purpose-built recursive, caching DNS resolver with DNSSEC validation and prefetching
- **Datadog Agent** — infrastructure monitoring and metrics
- **Terraform** — everything is infrastructure-as-code, version controlled on GitHub

The instance lives in the default AWS VPC (`172.31.0.0/16`) and is reachable from the school network via the Site-to-Site VPN. Staff and faculty devices point to the EC2 instance's private IP as their primary DNS server, with Cloudflare (`1.1.1.1`) as a fallback in case the VPN goes down.

Student devices remain unchanged — GoGuardian's DNS-based filtering stays intact on the student VLANs.

---

## How Unbound Works (The Short Version)

Unbound sits between your clients and the internet. When a device asks it to resolve `google.com`, it either:

1. **Returns it from cache** — if it's already been resolved recently. This takes under 1 millisecond.
2. **Fetches it from an upstream resolver** — if it's not cached yet. This takes 20–80ms depending on network conditions.

The key configuration options that make it shine for high-concurrency environments:

```conf
prefetch: yes        # Refreshes popular records before they expire, so cache never goes cold
cache-min-ttl: 300   # Floors the TTL at 5 minutes so records don't expire too aggressively
msg-cache-size: 64m  # Memory allocated for query cache
rrset-cache-size: 128m
```

With prefetching enabled, Unbound proactively refreshes frequently-accessed records before their TTL expires. On a busy testing morning, this means popular domains stay warm in cache all day.

The upstream connection uses **DNS over TLS** to Cloudflare and Google on port 853 — so even the queries that do leave the building are encrypted.

---

## The Build: What I Learned the Hard Way

I'll be honest — this wasn't a straight line from idea to working system. A few things caught me that are worth passing along.

**Ubuntu ships with `systemd-resolved` occupying port 53.**
This is the built-in stub DNS resolver in modern Ubuntu. It binds to port 53, which conflicts directly with Unbound trying to do the same thing. The fix is to stop and disable `systemd-resolved` before installing Unbound, and update `/etc/resolv.conf` to point to a real upstream resolver so the instance itself can still reach the internet.

**Terraform's `templatefile()` and bash `${}` syntax conflict.**
When you use `templatefile()` in Terraform to inject variables into a shell script, Terraform interprets `${VARIABLE}` as a template substitution. Any bash variable using that syntax needs to be escaped as `$${VARIABLE}` in the script, otherwise Terraform throws an error at plan time.

**Lightsail's VPC peering has a routing limitation.**
I originally planned to use AWS Lightsail for the simpler pricing model, but discovered that Lightsail's peered VPC (`172.26.0.0/16`) doesn't inherit routes from the main VPC's route table. Since our Site-to-Site VPN routes are propagated to the main VPC only, an EC2 instance in the default VPC was the right call. The extra cost over Lightsail is minimal.

**TLS certificate verification requires explicit configuration.**
Unbound needs to be told where to find the system's CA certificate bundle to verify the TLS connection to upstream resolvers. Without this line in the config, DNS over TLS silently fails:

```conf
tls-cert-bundle: "/etc/ssl/certs/ca-certificates.crt"
```

---

## The Terraform Structure

The project is fully infrastructure-as-code. Key resources:

- `aws_instance` — the EC2 instance with user_data bootstrapping
- `aws_security_group` — port 53 (UDP/TCP) and SSH inbound from school CIDRs only; all outbound
- `aws_eip` — elastic IP for a stable public address
- `aws_iam_role` + `aws_iam_instance_profile` — CloudWatch and EC2 read permissions for Datadog
- `data "aws_ami"` — dynamically resolves the latest Ubuntu 22.04 ARM64 AMI so the build never goes stale

Sensitive values like the Datadog API key are kept out of source control entirely, passed at apply time via environment variables or a `.tfvars` file that's excluded from the repo via `.gitignore`.

---

## The Result

After pointing staff and faculty devices at the new resolver:

- **First query:** ~80ms (fetched from upstream)
- **Cached query:** ~0ms (served from local cache)
- **Cache hit rate:** Above 60% within 24 hours of normal use

On PSAT morning, the first device to resolve a testing URL warms the cache for everyone else. The 200th student gets their DNS answer in under a millisecond.

---

## Can You Replicate This?

Yes — and the full project including Terraform code, the Unbound configuration, and the bootstrapping script is on GitHub at [github.com/brent-hollers](https://github.com/brent-hollers).

To adapt it for your environment you'll need:

1. An AWS account with a Site-to-Site VPN to your local network
2. A Unifi UDM Pro or equivalent firewall with static routing capability
3. Your local network CIDR (to lock down the DNS access-control and security group rules)
4. Terraform installed locally
5. A Datadog account (optional — Netdata is a free alternative)

The bootstrapping script handles everything automatically on first launch: stopping `systemd-resolved`, configuring Unbound, installing the Datadog agent, and adding the hostname entry to `/etc/hosts`. A fresh `terraform apply` produces a fully configured DNS resolver with no manual steps.

---

## Final Thoughts

This project is a good example of what happens when cloud skills get applied to education IT problems. The architecture isn't complicated — it's a single small VM running well-established open source software. But the outcome is real: faster page loads, better reliability under load, and an entire server defined in code that can be rebuilt in minutes.

If you're running a school network and still relying entirely on external DNS resolvers, this is one of the highest-leverage, lowest-cost infrastructure improvements you can make. The hardest part isn't the technology — it's knowing the problem exists in the first place.

---

*Dr. Brent Hollers is the Director of Information Technology at St. Mary's Academy in Fayetteville, GA. He holds a Ph.D. in Workforce Education, an M.S. in Data Science, and is an AWS Certified Solutions Architect. Connect on [LinkedIn](https://linkedin.com/in/brenthollers) or visit [brenthollers.com](https://brenthollers.com).*