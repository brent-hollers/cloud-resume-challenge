---
title: "A Real Take on the Practical Implications of AI in Tech"
subtitle: "AI is Powerful, but not Inevitable"
date: 2026-03-20
author: Dr. Brent Hollers
tags: [DevOps, Infrastructure as Code, Terraform, AWS, System Design, AI]
series: "Practical Thoughts"
part: 1
description: "What I have learned about AI use in real projects and what is not being discussed."
---

# AI Is a Powerful Tool. It's Not a Replacement for Knowing What You're Doing.

*By Dr. Brent Hollers*

---

There's a conversation happening in nearly every tech team, IT department, and engineering org right now. It usually goes one of two ways: either AI is going to replace us all, or AI is completely overhyped and we should stop worrying about it. The truth, as usual, lives somewhere in the middle — and it's a lot more interesting than either extreme.

I had a front-row seat to that truth recently while building a DNS caching resolver for our school network using AWS, Terraform, and Unbound. It was a real infrastructure project with real stakes, and I used an AI assistant throughout the process. What I walked away with wasn't just a working DNS server — it was a clearer picture of what AI tools actually are, and what they aren't.

---

## AI Gets Things Wrong. That's Not a Disqualifier.

Let me be direct about something: the AI I was working with made mistakes. Early in the project, it recommended building on AWS Lightsail — a reasonable starting point on the surface, but one that ran into a fundamental architectural limitation. Lightsail's peered VPC doesn't inherit routing from the main AWS VPC, which meant our Site-to-Site VPN couldn't reach the instance the way we needed it to. We spent real time troubleshooting before recognizing the right path was EC2 in the default VPC all along.

Later, a security group configuration issue had us going in circles. DNS queries were being refused, traffic wasn't flowing the way it should, and the AI's suggestions weren't cutting through to the root cause — until I took a step back, thought through the network path independently, and made the right change myself.

Here's the thing: neither of those moments was a failure of AI as a concept. They were reminders of what AI actually is. These models are extraordinarily good at pattern recognition, code generation, and synthesizing information across broad domains. They are not all-knowing. They don't have perfect situational awareness of your specific environment. And they can confidently suggest something that turns out to be wrong.

If you don't have the foundational knowledge to recognize when something is off, you'll follow bad advice right off a cliff — and never know why it didn't work.

---

## The Foundation Still Matters. Maybe More Than Ever.

There's a seductive narrative floating around that AI tools are making deep technical knowledge obsolete. Why learn networking if you can just ask an AI? Why study cloud architecture if a model can generate your Terraform for you?

This thinking gets it exactly backwards.

During this project, understanding subnetting was what let me spot that a `/20` subnet mask was causing a routing mismatch. Knowing how IPsec tunnel policies work was what revealed that our VPN was only passing traffic for one CIDR, not both. Understanding DNS resolution at a protocol level was what made the `systemd-resolved` conflict immediately recognizable once we saw the error.

Without that foundation, every AI suggestion is just noise you can't evaluate. With it, the AI becomes something genuinely powerful: a fast, tireless collaborator that can generate a first draft, surface options you hadn't considered, and help you move through problems faster than you could alone.

The analogy I keep coming back to is GPS navigation. GPS is an extraordinary tool that has genuinely changed how we get around. But if you have no mental model of geography — no sense of north and south, no awareness of which direction you're generally heading — you will follow GPS directions into a lake. The tool doesn't replace the need to understand the terrain. It amplifies your ability to navigate it.

---

## How You Use the Tool Changes What You Get Out of It

Here's where I think the conversation about AI in the workplace needs to go next: it's not just whether you use these tools, it's how you use them.

Midway through this project, I made a deliberate choice. Instead of asking the AI to just hand me the finished Terraform code, I asked it to tutor me — to ask me guiding questions, let me work through the logic, and only give me the answer when I genuinely couldn't get there on my own. When I got something right, just confirm it. When I was off track, redirect me with a question rather than a correction.

The difference in outcome was significant. I didn't just end up with working infrastructure — I understood why it worked. I retained the concepts. I built real mental models around Terraform resource relationships, IAM policy structure, and EC2 networking that I can apply to the next project without needing to start from scratch.

This is the underexplored opportunity in AI-assisted work. Most people use these tools in extraction mode: give me the answer, generate the code, write the thing. That's useful. But it leaves the learning on the table. When you engage the model as a thinking partner rather than an answer machine, you get both the output and the understanding behind it. That's a compounding return.

---

## Where We Go From Here

AI tools are not going away. They're going to get better, faster, and more embedded in the workflows of every technical role. The people who thrive in that environment won't be the ones who offload their thinking to the model — they'll be the ones who use the model to think better.

That means continuing to invest in foundational skills: networking, systems, cloud architecture, security. Not because AI can't help with those things, but because your ability to evaluate, direct, and correct AI output depends entirely on what you actually know.

It also means being intentional about how you engage these tools. Ask them to explain, not just produce. Ask them to push back. Ask them to teach you the concept, not just give you the answer. Use the acceleration they offer without outsourcing the understanding that makes the acceleration meaningful.

We're early in figuring out what the human-AI working relationship actually looks like at its best. But if this project taught me anything, it's that the most valuable thing AI gave me wasn't the code it wrote — it was the thinking it helped me do.

---

*Dr. Brent Hollers is the Director of Information Technology at St. Mary's Academy in Fayetteville, GA. He holds a Ph.D. in Workforce Education, an M.S. in Data Science, and is an AWS Certified Solutions Architect. Connect on [LinkedIn](https://linkedin.com/in/brenthollers) or visit [brenthollers.com](https://brenthollers.com).*