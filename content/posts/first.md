+++
title = 'My First Post'
date = 2024-01-14T07:07:07+01:00
draft = false
+++

Here is the content of the attached document converted into Markdown format.

From On-Prem to Cloud-Native: A Federal Migration & Modernization Journey 

## Objective

To develop a more concrete understanding of modernization and migration strategies for complex systems which also have specific security, resiliency, and accessibility requirements, I chose to simulate a realistic Federal Cloud Transformation scenario—migrating a legacy, stateful mission application from an on-premise data center to AWS, and subsequently refactoring it into a secure, scalable, cloud-native architecture on Kubernetes.

## The Scenario

* 
**The Client:** A federal agency is running a critical "Mission Status" application on aging on-premise hardware (Dell PowerEdge/VMware).


* 
**The Mandate:** The agency has a mandate to evacuate the data center (Cloud First Policy) and improve the application's security posture and scalability (Modernization).



---

## The Solution Architecture

### Pre-Requisites (Lab Setup)

To create a system that could be migrated, I first had to simulate an on-prem network, client, and database infrastructure.

* 
**Framework:** I chose one of the more popular frameworks, a LAMP stack.


* 
**Network Security:** I put this stack behind a network firewall using pfSense, as it is open-source and popular firewall software.


* 
**Configuration:** I had to create a port forwarding rule to access the pfSense interface from my local network since the server and the pfSense instance sit inside my local network on a separate subnet.


* 
**Client VM:** Once pfSense was running with appropriate networking, I created an Ubuntu Server client VM to host the LAMP stack.


* 
**Application:** I built a simple web server that maintains a log of entries to simulate the local, on-premises legacy application.



### Phase 1: Lift & Shift (Migration)

The goal was to re-host the virtual machine to Amazon EC2 using **AWS Application Migration Service (MGN)** to ensure immediate continuity and data integrity.

* 
**The Bridge:** I established a "bridge" between the on-premise environment and the AWS Cloud using AWS MGN, which provides block-level replication.


* 
**Source Environment:** A VMware ESXi 6.7 host running on a Dell PowerEdge R420 server in my home lab.


* **The Process:**
* Installed the AWS Replication Agent on the source Linux machine.


* The agent initiated a continuous block-level sync to the `us-east-1` region.


* Once the "Data Replication Status" reached "Healthy," I launched a Test Instance in AWS.




* 
**Validation:** Verified that the application state (the local SQLite database containing "Mission Logs") migrated intact. This proved we could evacuate the data center rapidly without rewriting code.



### Phase 2: Modernization (Refactor & Replatform)

With the application in the cloud, the next step was optimization, moving from a "pet" (long-lived VM) to "cattle" (ephemeral containers).

#### 1. Containerization & Security

I refactored the Python application into a Docker container.

* 
**Compliance:** In alignment with **NIST 800-190** (Application Container Security Guide), I ensured the container adhered to "Least Privilege" principles.


* 
**Base Image:** Used `python:3.9-slim` to minimize the attack surface.


* 
**Non-Root User:** Explicitly created a nonroot user (`uid: 5678`) to run application processes, preventing potential privilege escalation attacks.



#### 2. Infrastructure as Code (Terraform)

I avoided manual console provisioning ("ClickOps") in favor of **Terraform**, ensuring the infrastructure is reproducible and auditable.

* 
**Network Isolation:** Provisioned a VPC (`fed-demo-vpc`) with strict isolation—Worker Nodes in private subnets and Load Balancers in public subnets.


* 
**EKS Cluster:** Deployed an Amazon EKS cluster (`fed-modernization-cluster`) using the modern `terraform-aws-modules/eks/aws` v20 module.


* 
**Cost Optimization:** Configured the Node Group (`green_team`) to utilize **EC2 Spot Instances** (`capacity_type = "SPOT"`), reducing compute costs by approximately 70% compared to On-Demand pricing.



#### 3. Deployment & Orchestration

The final deployment utilized Kubernetes manifests to manage the application lifecycle.

* 
**Supply Chain:** The Docker image was pushed to a private **Amazon ECR** repository within the same account to ensure secure, low-latency access.


* 
**Availability:** Deployed the application with a LoadBalancer service type, exposing the application securely on port 80 while the container listened on port 5000.



---

## The Outcome

The legacy application is now fully modernized. It runs as a lightweight, secure container orchestrated by Kubernetes. It is self-healing, auto-scalable, and significantly cheaper to run than the original on-premises virtual machine.

---

## Lessons Learned

No migration is perfect. Here are the key technical challenges encountered and resolved during this project:

### 1. The "Ghost Token" (AWS CLI Authentication)

* 
**Issue:** Terraform operations failed with `ExpiredToken` errors, even after updating credentials.


* 
**Root Cause:** The CLI environment was caching a temporary AWS SSO session token, which took precedence over the static IAM Access Keys I was trying to use.


* 
**Fix:** Performed a "nuclear" cleanup of the PowerShell environment (`Remove-Item Env:\AWS_SESSION_TOKEN`) to force the CLI to re-authenticate using the correct static profile.



### 2. The Cross-Account Supply Chain Trap

* 
**Issue:** Kubernetes pods failed with `ImagePullBackOff`.


* 
**Root Cause:** The EKS cluster was in one AWS account, but I had initially pushed the Docker image to a registry in a different root account. By default, EKS cannot pull images from a different account's private registry.


* 
**Fix:** Adhering to the "Data Gravity" principle, I created a new ECR repository within the testing account and re-pushed the image.



### 3. Terraform Module Versioning

* 
**Issue:** The initial Terraform plan failed due to unsupported block types (`elastic_gpu_specifications`).


* 
**Root Cause:** Attempted to use an older EKS module version with the newest AWS Provider (v5.x), which had deprecated specific features.


* 
**Fix:** Upgraded the EKS module to `~> 20.0` and updated the `main.tf` configuration to align with the modern v20 schema.



---

## Future Improvements & Roadmap

While this project demonstrated an MVP migration, the following areas were identified for evolution into an enterprise-grade environment.

### 1. Implementation of CI/CD Pipelines

* 
**Current State:** Container images are built locally and pushed manually.


* 
**The Upgrade:** Implement a fully automated CI/CD pipeline using AWS CodePipeline and CodeBuild (or GitHub Actions).


* 
**Goal:** Any commit to the main branch triggers an automated build, scan, and rolling update.



### 2. Enhanced Observability with Container Insights

* 
**Current State:** Monitoring is limited to basic EC2 metrics and CLI status checks.


* 
**The Upgrade:** Enable CloudWatch Container Insights or deploy a Prometheus/Grafana stack.


* 
**Goal:** Gain granular visibility into pod-level metrics and centralized logging.



### 3. Security Hardening & Secrets Management

* 
**Current State:** Environment variables are injected directly via Kubernetes manifests.


* 
**The Upgrade:** Integrate AWS Secrets Manager using the AWS Secrets and Configuration Provider (ASCP).


* 
**Goal:** Rotate and retrieve credentials programmatically at runtime without exposing them in plain text.



### 4. Cost Optimization: Moving to Fargate

* 
**Current State:** Application runs on managed EC2 Node Groups.


* 
**The Upgrade:** Migrating the data plane to AWS Fargate for EKS.


* 
**Goal:** Run pods without managing underlying EC2 servers to reduce operational overhead.
