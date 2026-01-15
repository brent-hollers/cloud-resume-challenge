+++
title = 'AWS Gotchas: ALBs vs NLBs and VPC Enpoints, What to know for the exam'
date = 2026-01-08T04:56:02+05:30
draft = false
+++

# The AWS Architect’s "Gotcha" List: Two Concepts That Trip Everyone Up

When I sat for the Solutions Architect exam, I breezed through the questions on EC2 and RDS. But there were two specific areas where I found myself staring at the screen, second-guessing my answers.

1. **ALB vs. NLB:** "Both balance load, so why does it matter?"
2. **VPC Endpoints:** "Why are there two types, and why is one free?"

These are the "silent killers" of the exam. They seem similar on the surface, but confusing them ensures a fail on scenario-based questions. Here is the simplest way to visualize them so you never mix them up again.

## 1. ALB vs. NLB: The "Receptionist" vs. The "Bouncer"

To understand the difference, you have to stop thinking about "servers" and start thinking about how traffic is handled.

### The Application Load Balancer (ALB) is a Corporate Receptionist.

Imagine walking into a high-end office building. You approach the receptionist (the ALB). She doesn't just wave you through; she asks you questions.

* "Who are you here to see?"
* "Do you have an appointment?"
* "Are you looking for HR or Engineering?"

She looks at the specific details of your request (the HTTP headers, the URL path). If you ask for `/images`, she directs you to the marketing floor. If you ask for `/payroll`, she directs you to finance.

* **The Superpower:** "Intelligence." It operates at **Layer 7** (Application). It can route traffic based on content (e.g., sending mobile users to a different server than desktop users).
* **The Trade-off:** She takes a split second to think. It’s slightly slower.

### The Network Load Balancer (NLB) is a Nightclub Bouncer.

Now imagine a nightclub with a line of 10,000 people. The bouncer (the NLB) does not care who you are. He does not care if you want a drink or a dance. He only cares about one thing: **Ticket Valid? Go.**

* **The Superpower:** "Speed." It operates at **Layer 4** (Transport). It doesn't look at the data; it just shuffles IP packets. It can handle **millions of requests per second** with ultra-low latency. It also provides a **Static IP**, which the Receptionist (ALB) cannot do.
* **The Trade-off:** He is "dumb." He cannot route based on your URL or headers.

### The "Exam Hack" Summary

* **Scenario:** "Microservices," "Path-based routing," "HTTP/HTTPS," "WAF integration." -> **Choose ALB.**
* **Scenario:** "Extreme performance," "Millions of requests," "Static IP required," "UDP traffic," "Gaming." -> **Choose NLB.**

---

## 2. Gateway vs. Interface Endpoints: The "Map" vs. The "Cable"

This is the topic that causes the most lost points. Both endpoints do the same thing: they allow your private EC2 instances to talk to AWS services (like S3) without going over the public internet. But they work in completely different ways.

### Gateway Endpoints are a "Secret Tunnel" (The Map Change)

Imagine your VPC is a fortress. You want to get to the "S3 Warehouse" outside. You *could* go out the front gate (Internet Gateway), but that's dangerous.
Instead, you just draw a new line on your map (Route Table) that says, "If you are going to the Warehouse, take the secret tunnel."

* **How it works:** It uses a **Route Table** entry. It does not exist as a physical device in your subnet.
* **The Catch:** It **ONLY** works for **S3** and **DynamoDB**.
* **The Benefit:** It is **100% Free**.

### Interface Endpoints are a "Private Phone Line" (The Cable)

Now, imagine you want to talk to the "SQS Department." There is no secret tunnel for them.
Instead, you pay the phone company to install a dedicated red phone (Elastic Network Interface - ENI) right inside your office (Subnet). When you pick up that phone, it rings directly at the SQS department.

* **How it works:** It injects an **ENI** (Elastic Network Interface) into your subnet. It uses a private IP address from your VPC range.
* **The Catch:** It costs money (hourly fee + data processing fee).
* **The Benefit:** It works with almost **all other AWS services** (SQS, SNS, Kinesis, etc.) and supports **PrivateLink** (connecting to other accounts).

### The "Exam Hack" Summary

* **Scenario:** "Access S3 or DynamoDB," "Lowest Cost," "Route Table." -> **Choose Gateway Endpoint.**
* **Scenario:** "Access Kinesis/SQS/Athena," "PrivateLink," "Connect to a SaaS application," "ENI." -> **Choose Interface Endpoint.**

---

### Visualizing the Difference

To cement the "Endpoint" concept, this video provides a clear breakdown of when to pay for an Interface Endpoint versus when to use the free Gateway.

[S3 Gateway Endpoint vs Interface Endpoint - Explained](https://www.youtube.com/watch?v=Aw0MG99coCY)

This video is relevant because it specifically addresses the cost and architecture trade-offs between the two endpoint types, which is a frequent "distractor" in exam questions.