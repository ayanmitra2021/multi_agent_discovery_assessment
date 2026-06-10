"""
Seed data for the policies database.
Quality of this data directly determines Architecture Agent output quality.
"""
from sqlalchemy.orm import Session

from ...persistence.policies_db import (
    ApprovedService,
    ComplianceFramework,
    FrameworkControl,
    PastMigration,
    Policy,
)

# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

_POLICIES = [
    # ── AWS ─────────────────────────────────────────────────────────────────
    dict(csp="aws", control_code="AWS-SEC-001", title="Encrypt data at rest with AWS KMS",
         category="security", severity="critical", is_mandatory=True,
         description="All data in S3, EBS, RDS, DynamoDB, and EFS must be encrypted at rest "
                     "using AWS KMS. Customer-managed keys (CMK) required for data classified "
                     "as Confidential or Restricted. CMK rotation must be enabled.",
         source_ref="CIS AWS Foundations Benchmark v2.0 §2.1"),
    dict(csp="aws", control_code="AWS-SEC-002", title="Enforce TLS 1.2+ for data in transit",
         category="security", severity="critical", is_mandatory=True,
         description="All service-to-service communication must use TLS 1.2 or higher. "
                     "S3 bucket policies must deny non-HTTPS requests. ALB listeners must "
                     "redirect HTTP to HTTPS. No self-signed certificates in production.",
         source_ref="AWS Security Best Practices"),
    dict(csp="aws", control_code="AWS-SEC-003", title="Block all public S3 bucket access",
         category="security", severity="critical", is_mandatory=True,
         description="S3 Block Public Access must be enabled at the account level. "
                     "Individual bucket overrides are prohibited. Static website hosting "
                     "must be served via CloudFront with OAC, not directly from S3.",
         source_ref="CIS AWS Foundations Benchmark v2.0 §2.1.5"),
    dict(csp="aws", control_code="AWS-SEC-004", title="Use IAM roles; no long-term access keys",
         category="security", severity="high", is_mandatory=True,
         description="EC2, Lambda, ECS, and EKS workloads must use IAM instance/execution "
                     "roles. No long-term IAM user access keys on production workloads. "
                     "Secrets must be stored in AWS Secrets Manager or SSM Parameter Store.",
         source_ref="CIS AWS Foundations Benchmark v2.0 §1.4"),
    dict(csp="aws", control_code="AWS-NET-001", title="Deploy in private VPC subnets",
         category="networking", severity="critical", is_mandatory=True,
         description="Application tiers (compute, database) must reside in private subnets "
                     "with no direct internet route. Internet-facing load balancers in public "
                     "subnets only. VPC Flow Logs must be enabled. NAT Gateway for egress.",
         source_ref="AWS Well-Architected Framework — Security Pillar"),
    dict(csp="aws", control_code="AWS-NET-002", title="Least-privilege Security Groups",
         category="networking", severity="high", is_mandatory=True,
         description="Security Groups must not allow 0.0.0.0/0 on management ports (22, 3389). "
                     "All inbound rules must specify a source CIDR or Security Group ID. "
                     "Default VPC must not be used for production workloads.",
         source_ref="CIS AWS Foundations Benchmark v2.0 §5.1"),
    dict(csp="aws", control_code="AWS-OPS-001", title="Enable CloudTrail in all regions",
         category="operations", severity="high", is_mandatory=True,
         description="AWS CloudTrail must be enabled in all regions with log file validation "
                     "and S3 access logging. Logs must be centralised in a dedicated security "
                     "account. CloudWatch alarms on unauthorised API calls.",
         source_ref="CIS AWS Foundations Benchmark v2.0 §3.1"),
    dict(csp="aws", control_code="AWS-OPS-002", title="Mandatory resource tagging",
         category="operations", severity="high", is_mandatory=False,
         description="All taggable resources must carry: Environment (dev/staging/prod), "
                     "Owner (team email), Project (project code), CostCenter. "
                     "Non-compliant resources blocked via AWS Config + Service Control Policies.",
         source_ref="FinOps Cloud Tagging Policy v2.1"),
    dict(csp="aws", control_code="AWS-ARCH-001", title="Container-first for new workloads",
         category="architecture", severity="medium", is_mandatory=False,
         description="New application workloads should target ECS Fargate or EKS as the "
                     "default compute platform. EC2 instances permitted only for workloads "
                     "with licensing, NUMA, or GPU requirements that preclude containers.",
         source_ref="Cloud Architecture Standard v3.0"),

    # ── Azure ────────────────────────────────────────────────────────────────
    dict(csp="azure", control_code="AZ-SEC-001", title="Enable Defender for Cloud on all subscriptions",
         category="security", severity="critical", is_mandatory=True,
         description="Microsoft Defender for Cloud must be enabled (Standard tier) on every "
                     "Azure subscription. Defender plans for Servers, SQL, Storage, Containers, "
                     "and Key Vault are mandatory. Secure Score must be reviewed weekly.",
         source_ref="Azure Security Benchmark v3 §NS-1"),
    dict(csp="azure", control_code="AZ-SEC-002", title="Encrypt all disks at rest",
         category="security", severity="critical", is_mandatory=True,
         description="All managed disks must use Azure Disk Encryption (ADE) with "
                     "customer-managed keys stored in Azure Key Vault. Platform-managed "
                     "keys are only permitted for non-production environments.",
         source_ref="Azure Security Benchmark v3 §DP-5"),
    dict(csp="azure", control_code="AZ-SEC-003", title="Use Managed Identity for service auth",
         category="security", severity="critical", is_mandatory=True,
         description="All Azure resources authenticating to other Azure services must use "
                     "System-assigned or User-assigned Managed Identity. No service principal "
                     "secrets or connection strings in application config or environment variables.",
         source_ref="Azure Security Benchmark v3 §IM-1"),
    dict(csp="azure", control_code="AZ-SEC-004", title="No public IPs without WAF",
         category="security", severity="high", is_mandatory=True,
         description="Virtual Machines must not have public IP addresses. Internet-facing "
                     "applications must be fronted by Azure Application Gateway with WAF (v2) "
                     "or Azure Front Door. Direct NIC-level public IPs are prohibited.",
         source_ref="Azure Security Benchmark v3 §NS-6"),
    dict(csp="azure", control_code="AZ-NET-001", title="Hub-Spoke topology with Azure Firewall",
         category="networking", severity="critical", is_mandatory=True,
         description="All subscriptions must connect to the hub VNet via VNet Peering or "
                     "Azure Virtual WAN. Internet egress must route through Azure Firewall "
                     "Premium in the hub. Direct internet breakout from spoke VNets is prohibited.",
         source_ref="Azure Landing Zone Architecture"),
    dict(csp="azure", control_code="AZ-NET-002", title="Private Endpoints for all PaaS services",
         category="networking", severity="high", is_mandatory=True,
         description="Azure PaaS services (Storage, SQL, CosmosDB, Key Vault, Service Bus, "
                     "ACR) must be accessed exclusively via Private Endpoints. Public network "
                     "access must be disabled on all PaaS services post-migration.",
         source_ref="Azure Security Benchmark v3 §NS-3"),
    dict(csp="azure", control_code="AZ-OPS-001", title="Centralised logging to Log Analytics",
         category="operations", severity="high", is_mandatory=True,
         description="All Diagnostic Settings must forward logs and metrics to the central "
                     "Log Analytics workspace. Activity Logs must be retained for 90 days. "
                     "Azure Monitor alerts on critical security events.",
         source_ref="Azure Security Benchmark v3 §LT-1"),
    dict(csp="azure", control_code="AZ-OPS-002", title="Mandatory Azure resource tagging",
         category="operations", severity="high", is_mandatory=False,
         description="Required tags: Environment, Owner, BusinessUnit, CostCenter, Project. "
                     "Enforced via Azure Policy 'Require tag on resources'. "
                     "Non-compliant resources trigger automated remediation task.",
         source_ref="FinOps Cloud Tagging Policy v2.1"),
    dict(csp="azure", control_code="AZ-ARCH-001", title="App Service for .NET web apps",
         category="architecture", severity="medium", is_mandatory=False,
         description=".NET 6+ web applications should target Azure App Service (P-series plans). "
                     "Azure Kubernetes Service preferred for microservices workloads. "
                     "Azure Container Apps for event-driven containerised services.",
         source_ref="Cloud Architecture Standard v3.0"),

    # ── GCP ──────────────────────────────────────────────────────────────────
    dict(csp="gcp", control_code="GCP-SEC-001", title="Enable Cloud Audit Logs for all services",
         category="security", severity="critical", is_mandatory=True,
         description="Admin Activity and Data Access audit logs must be enabled for all "
                     "GCP services. Logs must be exported to Cloud Storage and BigQuery "
                     "via Log Sinks. Log retention minimum 400 days. Org-level policy.",
         source_ref="GCP CIS Benchmark v2.0 §2.1"),
    dict(csp="gcp", control_code="GCP-SEC-002", title="CMEK for sensitive workloads",
         category="security", severity="critical", is_mandatory=True,
         description="GCS buckets, BigQuery datasets, Cloud SQL, and GKE nodes storing "
                     "Confidential data must use Customer-Managed Encryption Keys via Cloud KMS. "
                     "Key rotation period must not exceed 365 days.",
         source_ref="GCP CIS Benchmark v2.0 §1.8"),
    dict(csp="gcp", control_code="GCP-SEC-003", title="Workload Identity for GKE service accounts",
         category="security", severity="critical", is_mandatory=True,
         description="GKE workloads must use Workload Identity to authenticate to GCP APIs. "
                     "Service Account keys are prohibited for GKE workloads. "
                     "Node Service Accounts must have minimal IAM roles (storage.objectViewer max).",
         source_ref="GCP GKE Hardening Guide"),
    dict(csp="gcp", control_code="GCP-SEC-004", title="No service account keys in production",
         category="security", severity="high", is_mandatory=True,
         description="Service Account keys must not be created for production workloads. "
                     "Use Workload Identity Federation or Application Default Credentials. "
                     "Existing keys must be audited quarterly and rotated within 90 days.",
         source_ref="GCP CIS Benchmark v2.0 §1.4"),
    dict(csp="gcp", control_code="GCP-NET-001", title="Shared VPC for multi-project environments",
         category="networking", severity="high", is_mandatory=True,
         description="All GCP projects must be attached to a Shared VPC hosted in a dedicated "
                     "Host Project. Standalone VPC networks are not permitted in production. "
                     "Cloud NAT for controlled egress. No external IPs on VM instances.",
         source_ref="GCP Resource Hierarchy Best Practices"),
    dict(csp="gcp", control_code="GCP-NET-002", title="VPC Service Controls for data protection",
         category="networking", severity="high", is_mandatory=True,
         description="Projects processing sensitive data must be enclosed in a VPC Service "
                     "Controls perimeter to prevent data exfiltration. BigQuery, GCS, and "
                     "Cloud KMS must be restricted to perimeter. Access Policies enforced at org level.",
         source_ref="GCP VPC Service Controls Guide"),
    dict(csp="gcp", control_code="GCP-OPS-001", title="Cloud Monitoring with alerting policies",
         category="operations", severity="high", is_mandatory=True,
         description="All production workloads must publish metrics to Cloud Monitoring. "
                     "Alerting policies required for: CPU >80%, memory >85%, error rate >1%, "
                     "latency p99 >2s. Alerts must route to PagerDuty or equivalent.",
         source_ref="GCP Operations Suite Best Practices"),
    dict(csp="gcp", control_code="GCP-OPS-002", title="Mandatory GCP resource labelling",
         category="operations", severity="high", is_mandatory=False,
         description="Required labels: environment, owner, team, cost-center, project. "
                     "Enforced via Organisation Policy constraints/compute.requireLabels. "
                     "Budget alerts per cost-center label.",
         source_ref="FinOps Cloud Tagging Policy v2.1"),
    dict(csp="gcp", control_code="GCP-ARCH-001", title="GKE Autopilot for containerised workloads",
         category="architecture", severity="medium", is_mandatory=False,
         description="Container workloads should target GKE Autopilot (fully managed). "
                     "Cloud Run preferred for stateless HTTP services (auto-scaling to zero). "
                     "Cloud Functions for event-driven lightweight tasks only.",
         source_ref="Cloud Architecture Standard v3.0"),
]

# ---------------------------------------------------------------------------
# Approved Services
# ---------------------------------------------------------------------------

_APPROVED_SERVICES = [
    # ── AWS ──────────────────────────────────────────────────────────────────
    dict(csp="aws", service_name="Amazon ECS Fargate", service_category="compute",
         capability_tags=["containers", "serverless", "microservices"],
         status="approved", constraints_note="Preferred container platform. Task CPU/memory must match workload profile."),
    dict(csp="aws", service_name="Amazon EKS", service_category="compute",
         capability_tags=["containers", "kubernetes", "microservices"],
         status="approved", constraints_note="Use Managed Node Groups. Enable Secrets Manager CSI driver for secret injection."),
    dict(csp="aws", service_name="AWS Lambda", service_category="compute",
         capability_tags=["serverless", "event-driven", "functions"],
         status="approved", constraints_note="Max 15 min runtime. Not for long-running batch jobs."),
    dict(csp="aws", service_name="Amazon RDS", service_category="database",
         capability_tags=["relational", "sql", "managed"],
         status="approved", constraints_note="Multi-AZ required for prod. Supported engines: PostgreSQL, MySQL, SQL Server, Oracle."),
    dict(csp="aws", service_name="Amazon Aurora", service_category="database",
         capability_tags=["relational", "sql", "managed", "high-availability"],
         status="approved", constraints_note="Preferred for new workloads. Aurora Serverless v2 for variable load."),
    dict(csp="aws", service_name="Amazon DynamoDB", service_category="database",
         capability_tags=["nosql", "key-value", "serverless", "high-scale"],
         status="approved", constraints_note="On-demand capacity recommended. DAX for caching."),
    dict(csp="aws", service_name="Amazon S3", service_category="storage",
         capability_tags=["object-storage", "archival", "data-lake"],
         status="approved", constraints_note="Versioning required for Confidential data. Lifecycle policies mandatory."),
    dict(csp="aws", service_name="AWS Secrets Manager", service_category="security",
         capability_tags=["secrets", "credentials", "rotation"],
         status="approved", constraints_note="Mandatory for DB passwords and API keys. Auto-rotation must be configured."),
    dict(csp="aws", service_name="Amazon SQS", service_category="messaging",
         capability_tags=["queue", "async", "decoupling"],
         status="approved", constraints_note="SQS FIFO for ordered processing. Dead-letter queues required."),
    dict(csp="aws", service_name="Amazon CloudFront", service_category="networking",
         capability_tags=["cdn", "edge", "waf"],
         status="approved", constraints_note="Required in front of all public-facing S3 and ALB endpoints. WAF rules mandatory."),

    # ── Azure ─────────────────────────────────────────────────────────────────
    dict(csp="azure", service_name="Azure App Service", service_category="compute",
         capability_tags=["web", "paas", "dotnet", "java"],
         status="approved", constraints_note="P-series plans for production. VNet Integration required. Managed Identity mandatory."),
    dict(csp="azure", service_name="Azure Kubernetes Service (AKS)", service_category="compute",
         capability_tags=["containers", "kubernetes", "microservices"],
         status="approved", constraints_note="System node pool: Standard_D4s_v5 min. RBAC + Azure AD integration mandatory."),
    dict(csp="azure", service_name="Azure Container Apps", service_category="compute",
         capability_tags=["containers", "serverless", "event-driven"],
         status="approved", constraints_note="Preferred for event-driven and microservices with auto-scale to zero requirements."),
    dict(csp="azure", service_name="Azure SQL Database", service_category="database",
         capability_tags=["relational", "sql", "managed"],
         status="approved", constraints_note="Business Critical tier for prod. Geo-redundant backup required. Defender for SQL enabled."),
    dict(csp="azure", service_name="Azure SQL Managed Instance", service_category="database",
         capability_tags=["relational", "sql", "managed", "full-compatibility"],
         status="approved", constraints_note="Use for migrations requiring SQL Agent, linked servers, or CLR. Deployed in private subnet."),
    dict(csp="azure", service_name="Azure Cosmos DB", service_category="database",
         capability_tags=["nosql", "multi-model", "global-distribution"],
         status="approved", constraints_note="API selection based on workload. Multi-region writes for global apps."),
    dict(csp="azure", service_name="Azure Blob Storage", service_category="storage",
         capability_tags=["object-storage", "archival", "data-lake"],
         status="approved", constraints_note="RA-GRS replication for prod. Soft delete 30 days. Private Endpoint mandatory."),
    dict(csp="azure", service_name="Azure Key Vault", service_category="security",
         capability_tags=["secrets", "keys", "certificates"],
         status="approved", constraints_note="HSM-backed keys for CMK. Soft-delete and purge protection mandatory. Private Endpoint required."),
    dict(csp="azure", service_name="Azure Service Bus", service_category="messaging",
         capability_tags=["queue", "pub-sub", "enterprise-messaging"],
         status="approved", constraints_note="Premium tier for prod (VNet integration). Dead-letter queue monitoring required."),
    dict(csp="azure", service_name="Azure Application Gateway + WAF", service_category="networking",
         capability_tags=["load-balancer", "waf", "ssl-termination"],
         status="approved", constraints_note="WAF v2 in Prevention mode. OWASP 3.2 ruleset. Required for all internet-facing apps."),

    # ── GCP ───────────────────────────────────────────────────────────────────
    dict(csp="gcp", service_name="GKE Autopilot", service_category="compute",
         capability_tags=["containers", "kubernetes", "managed"],
         status="approved", constraints_note="Preferred GKE mode. No node management. Binary Authorization required."),
    dict(csp="gcp", service_name="Cloud Run", service_category="compute",
         capability_tags=["containers", "serverless", "http"],
         status="approved", constraints_note="Preferred for stateless HTTP workloads. VPC connector required for private access."),
    dict(csp="gcp", service_name="Cloud SQL", service_category="database",
         capability_tags=["relational", "sql", "managed"],
         status="approved", constraints_note="High-availability config required for prod. Private IP only. Automated backups mandatory."),
    dict(csp="gcp", service_name="BigQuery", service_category="analytics",
         capability_tags=["analytics", "data-warehouse", "sql"],
         status="approved", constraints_note="Column-level security for Confidential data. VPC Service Controls perimeter required."),
    dict(csp="gcp", service_name="Cloud Spanner", service_category="database",
         capability_tags=["relational", "sql", "global-scale", "strong-consistency"],
         status="conditional", constraints_note="Approved only for globally distributed workloads requiring strong consistency. Cost review required."),
    dict(csp="gcp", service_name="Firestore", service_category="database",
         capability_tags=["nosql", "document", "serverless"],
         status="approved", constraints_note="Native mode preferred. Real-time listeners for event-driven apps."),
    dict(csp="gcp", service_name="Cloud Storage", service_category="storage",
         capability_tags=["object-storage", "archival", "data-lake"],
         status="approved", constraints_note="Uniform bucket-level access required. CMEK for Confidential data. Retention policies mandatory."),
    dict(csp="gcp", service_name="Secret Manager", service_category="security",
         capability_tags=["secrets", "credentials", "rotation"],
         status="approved", constraints_note="Mandatory for credentials and API keys. Automatic rotation via Cloud Functions."),
    dict(csp="gcp", service_name="Cloud Pub/Sub", service_category="messaging",
         capability_tags=["pub-sub", "streaming", "event-driven"],
         status="approved", constraints_note="Dead-letter topics required. Message ordering where needed."),
    dict(csp="gcp", service_name="Cloud Armor", service_category="networking",
         capability_tags=["waf", "ddos-protection", "security-policy"],
         status="approved", constraints_note="Required for all external load balancers. OWASP rules and rate limiting configured."),
]

# ---------------------------------------------------------------------------
# Compliance Frameworks
# ---------------------------------------------------------------------------

_FRAMEWORKS = [
    dict(framework_code="SOC2", framework_name="SOC 2 Type II",
         jurisdiction="US", version="2017"),
    dict(framework_code="ISO27001", framework_name="ISO/IEC 27001",
         jurisdiction="International", version="2022"),
    dict(framework_code="GDPR", framework_name="General Data Protection Regulation",
         jurisdiction="EU", version="2018"),
    dict(framework_code="PCIDSS", framework_name="PCI DSS",
         jurisdiction="International", version="v4.0"),
    dict(framework_code="HIPAA", framework_name="Health Insurance Portability and Accountability Act",
         jurisdiction="US", version="1996/2013"),
]

# ---------------------------------------------------------------------------
# Past Migrations
# ---------------------------------------------------------------------------

_PAST_MIGRATIONS = [
    # ── AWS ──────────────────────────────────────────────────────────────────
    dict(csp="aws", app_archetype="legacy-desktop", complexity_tier="critical",
         source_pattern="VB6 desktop app + SQL Server 2008 R2 (12 COM+ integrations)",
         target_pattern=".NET 8 Blazor Server on ECS Fargate + RDS SQL Server Multi-AZ",
         outcome="success", duration_weeks=32,
         lessons_learned="VB6 to .NET requires complete rewrite; UI migration consumed 45% of effort. "
                         "COM+ integrations replaced with REST APIs — add 2 weeks per integration. "
                         "SQL Server stored procedures required extensive refactoring (T-SQL -> EF Core). "
                         "Budget 3× estimate buffer for VB6 apps. Batch jobs needed Hangfire replacement."),
    dict(csp="aws", app_archetype="web", complexity_tier="medium",
         source_pattern=".NET Framework 4.8 MVC on IIS + SQL Server 2016 (on-prem)",
         target_pattern=".NET 8 on ECS Fargate + RDS SQL Server + ElastiCache Redis",
         outcome="success", duration_weeks=16,
         lessons_learned=".NET Framework to .NET 8 is 70% lift-and-shift; remaining 30% in breaking APIs. "
                         "Session state migration (in-proc → Redis) required 1 week. "
                         "Windows Authentication replacement (NTLM → Azure AD/OIDC) add 2 weeks. "
                         "Target 10–12 weeks for typical .NET Framework web app."),
    dict(csp="aws", app_archetype="api", complexity_tier="high",
         source_pattern="Java EE 8 monolith (JBoss) + Oracle DB 12c (150+ stored procs)",
         target_pattern="Spring Boot 3 microservices on EKS + RDS Aurora PostgreSQL",
         outcome="success", duration_weeks=40,
         lessons_learned="Monolith decomposition: domain identification took 3 weeks with EventStorming. "
                         "Oracle to PostgreSQL: PL/SQL migration took 8 weeks (150 stored procs). "
                         "Oracle-specific types (ROWNUM, CONNECT BY) need manual rewrite. "
                         "Recommend strangler fig pattern; avoid big-bang for 150k+ LOC apps."),
    dict(csp="aws", app_archetype="batch", complexity_tier="low",
         source_pattern="RHEL 7 VMs (VMware) + Oracle Database 11g (lift-and-shift)",
         target_pattern="EC2 (RHEL 9) Auto Scaling + RDS Oracle SE2 Multi-AZ",
         outcome="success", duration_weeks=8,
         lessons_learned="Rehost is fastest path; expect 6–10 weeks for VM+DB lift-and-shift. "
                         "Oracle SE2 licensing on RDS costs 30% more than on-prem — factor into TCO. "
                         "AWS Database Migration Service (DMS) handled schema + data migration in 3 days. "
                         "Validate all cron jobs / scheduled tasks post-migration."),
    dict(csp="aws", app_archetype="analytics", complexity_tier="high",
         source_pattern="SQL Server SSIS/SSRS data warehouse on-prem (5 TB, nightly ETL)",
         target_pattern="AWS Glue ETL + S3 data lake + Redshift Serverless + QuickSight",
         outcome="success", duration_weeks=24,
         lessons_learned="SSIS to Glue conversion: 1 Glue job per SSIS package; allow 1 day per package. "
                         "SSRS to QuickSight: limited visual parity; stakeholder sign-off on report redesign needed. "
                         "Historical data load (5 TB) took 4 days via DMS. "
                         "Redshift Serverless cheaper than provisioned for < 8 hours/day query workloads."),

    # ── Azure ─────────────────────────────────────────────────────────────────
    dict(csp="azure", app_archetype="web", complexity_tier="medium",
         source_pattern="ASP.NET 4.x WebForms + SQL Server 2014 AlwaysOn (on-prem)",
         target_pattern="ASP.NET Core 8 on Azure App Service + Azure SQL Managed Instance",
         outcome="success", duration_weeks=14,
         lessons_learned="WebForms has no direct Azure PaaS equivalent — requires rewrite to MVC/Razor Pages. "
                         "SQL Managed Instance supports most SQL Server features; linked servers require evaluation. "
                         "App Service Easy Auth for Azure AD SSO integration saves 1 week. "
                         "Deployment Slots (blue-green) simplify cutover with zero downtime."),
    dict(csp="azure", app_archetype="legacy-desktop", complexity_tier="high",
         source_pattern=".NET WinForms + WCF services + SQL Server 2012 (line-of-business)",
         target_pattern="React SPA + Azure API Management + App Service .NET 8 APIs + Azure SQL",
         outcome="success", duration_weeks=24,
         lessons_learned="WinForms to React: full UI rewrite required; UX redesign phase critical (3 weeks). "
                         "WCF to REST: contract-first API design using OpenAPI saves downstream integration time. "
                         "API Management added 2 weeks but provides rate limiting, auth, versioning. "
                         "Phased rollout (department by department) reduced change risk significantly."),
    dict(csp="azure", app_archetype="database", complexity_tier="low",
         source_pattern="SQL Server 2016 AlwaysOn AG (on-prem, 2 TB, mission-critical)",
         target_pattern="Azure SQL Hyperscale Business Critical (geo-replica to secondary region)",
         outcome="success", duration_weeks=6,
         lessons_learned="SQL Hyperscale: near-instant backup/restore; excellent for VLDB (> 1 TB). "
                         "Azure Database Migration Service handled online migration with < 1 min cutover window. "
                         "Linked servers to other SQL instances must be replaced (not supported in Azure SQL). "
                         "Estimated 4–8 weeks for SQL-only lift-and-shift migrations."),
    dict(csp="azure", app_archetype="api", complexity_tier="high",
         source_pattern="SAP ECC 6.0 on-prem (Windows, Oracle DB, 800 users)",
         target_pattern="SAP S/4HANA on Azure VMs (E-series) + Azure NetApp Files + ExpressRoute",
         outcome="success", duration_weeks=20,
         lessons_learned="SAP on Azure: Microsoft-certified VM families (M-series, E-series) only. "
                         "ExpressRoute (not VPN) mandatory for SAP production. "
                         "Azure NetApp Files required for NFS shares (SAPMNT, SAPTRANS). "
                         "HANA DB migration from Oracle took 6 weeks (R3load tool). Involve SAP Basis team early."),
    dict(csp="azure", app_archetype="analytics", complexity_tier="medium",
         source_pattern="Hadoop on-prem cluster (HDFS/Hive/Spark, 10 TB)",
         target_pattern="Azure Data Factory + Azure Data Lake Storage Gen2 + Azure Synapse Analytics",
         outcome="success", duration_weeks=16,
         lessons_learned="Hive to Synapse: most HiveQL compatible with T-SQL with minor rewrites. "
                         "HDFS to ADLS Gen2: AzCopy tool for bulk data transfer (10 TB in ~18 hrs). "
                         "Spark workloads migrate to Synapse Spark pools with minimal changes. "
                         "Delta Lake format recommended for ADLS Gen2 for ACID transactions."),

    # ── GCP ───────────────────────────────────────────────────────────────────
    dict(csp="gcp", app_archetype="analytics", complexity_tier="medium",
         source_pattern="Hadoop/Hive on-prem (CDH 6.x, 8 TB, 200 Hive queries/day)",
         target_pattern="BigQuery + Cloud Dataflow (Apache Beam) + Cloud Storage data lake",
         outcome="success", duration_weeks=16,
         lessons_learned="HiveQL to BigQuery SQL: 90% compatible; DISTRIBUTE BY, LATERAL VIEW need rewrites. "
                         "Cloud Storage Transfer Service handled 8 TB in 12 hours. "
                         "Dataflow (Beam) replaces MapReduce/Spark for ETL pipelines. "
                         "BigQuery slot reservations recommended for consistent query performance at scale."),
    dict(csp="gcp", app_archetype="api", complexity_tier="high",
         source_pattern="Spring Boot monolith (Java 11, MySQL 5.7, 80k req/min peak)",
         target_pattern="Spring Boot 3 microservices on GKE Autopilot + Cloud SQL PostgreSQL",
         outcome="success", duration_weeks=28,
         lessons_learned="MySQL to PostgreSQL migration: Flyway scripts needed updates (AUTO_INCREMENT → SERIAL). "
                         "GKE Autopilot simplifies ops but requires Kubernetes-aware teams (training: 2 weeks). "
                         "Workload Identity setup: 3 days per microservice team. "
                         "Cloud SQL Proxy for secure private connectivity from GKE. Istio service mesh optional."),
    dict(csp="gcp", app_archetype="web", complexity_tier="low",
         source_pattern="Node.js Express API + MongoDB (on-prem VMs)",
         target_pattern="Cloud Run (containerised) + Firestore + Cloud Armor",
         outcome="success", duration_weeks=6,
         lessons_learned="MongoDB to Firestore: document model is compatible; query API differs significantly. "
                         "Cloud Run: containerise with Docker (allow 1 week) then deploy (1 day). "
                         "Cloud Armor WAF setup: 2 days to configure OWASP ruleset. "
                         "Estimated 4–8 weeks for Node.js/Python stateless APIs to Cloud Run."),
    dict(csp="gcp", app_archetype="database", complexity_tier="medium",
         source_pattern="Oracle Database 19c on-prem (2 TB, 300 stored procedures, ODP.NET clients)",
         target_pattern="Cloud SQL PostgreSQL 15 + Pglogical for ongoing replication",
         outcome="success", duration_weeks=18,
         lessons_learned="Oracle to PostgreSQL: ora2pg tool automates 60–70% of schema conversion. "
                         "PL/SQL to PL/pgSQL: ROWNUM→ROW_NUMBER(), SYSDATE→NOW(), sequences differ. "
                         "300 stored procedures: allow 3 weeks for conversion and testing. "
                         "ODP.NET clients migrate to Npgsql (Npgsql EF Core provider available). "
                         "Pglogical for zero-downtime cutover with < 30 second switchover."),
    dict(csp="gcp", app_archetype="batch", complexity_tier="medium",
         source_pattern="Python ML training pipelines on bare-metal GPUs (on-prem)",
         target_pattern="Vertex AI Pipelines + Cloud Storage + Artifact Registry",
         outcome="success", duration_weeks=14,
         lessons_learned="Custom training containers migrate to Vertex AI Custom Jobs (1:1 mapping). "
                         "Vertex AI Pipelines (Kubeflow) require pipeline SDK refactoring (2 weeks). "
                         "Model registry in Vertex AI enables versioning and A/B deployment. "
                         "TPU vs GPU cost tradeoff: TPUs 40% cheaper for Transformer models > 7B params. "
                         "Data in Cloud Storage significantly faster than on-prem NFS for training."),
]


def seed_database(engine) -> None:
    """
    Idempotent seed: skips if Policy table already has rows.
    Call once at application startup after init_db().
    """
    with Session(engine) as session:
        if session.query(Policy).count() > 0:
            return  # already seeded

        # Policies
        policy_objs = [Policy(**p) for p in _POLICIES]
        session.add_all(policy_objs)

        # Approved services
        session.add_all([ApprovedService(**s) for s in _APPROVED_SERVICES])

        # Compliance frameworks
        fw_objs = [ComplianceFramework(**f) for f in _FRAMEWORKS]
        session.add_all(fw_objs)
        session.flush()  # ensure IDs assigned

        # Framework ↔ Policy mappings (sample: SOC2 and ISO27001 → security controls)
        soc2 = session.query(ComplianceFramework).filter_by(framework_code="SOC2").first()
        iso = session.query(ComplianceFramework).filter_by(framework_code="ISO27001").first()
        security_policies = (
            session.query(Policy).filter(Policy.category == "security").all()
        )
        for pol in security_policies:
            if soc2:
                session.add(FrameworkControl(
                    framework_id=soc2.id, policy_id=pol.id,
                    mapping_note=f"SOC 2 CC6 — {pol.title}"))
            if iso:
                session.add(FrameworkControl(
                    framework_id=iso.id, policy_id=pol.id,
                    mapping_note=f"ISO 27001 A.8 — {pol.title}"))

        # Past migrations
        session.add_all([PastMigration(**m) for m in _PAST_MIGRATIONS])

        session.commit()
