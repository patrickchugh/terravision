# Feature Specification: AWS Handler Refinement for Professional Architecture Diagrams

**Feature Branch**: `002-aws-handler-refinement`
**Created**: 2025-12-26
**Status**: Draft
**Input**: User description: "Review and refine AWS resource handlers for API Gateway, SageMaker, and event-driven architecture patterns to produce professional diagrams for AWS Solutions Architects"

## Clarifications

### Session 2025-12-26

- Q: What source should be used for test Terraform configurations? → A: Use official AWS/HashiCorp examples as primary reference
- Q: How should work be prioritized if implementation time is constrained? → A: Complete all P1 patterns first, then P2, then P3
- Q: How should circular event patterns be handled? → A: Existing code already handles and removes circular references (no change needed)
- Q: What should happen when API Gateway has no backend integrations in Terraform? → A: Show API Gateway with placeholder "External Integration" node
- Q: How should cross-module event source mappings be handled? → A: Existing handlers resolve cross-module references and create links (no change needed)
- Q: How should the 4 unresolved edge cases (SageMaker multi-account, nested Step Functions, ElastiCache Global Datastore, WAF missing resources) be handled? → A: Mark all 4 as out-of-scope for this feature (document as known limitations)
- Q: Should Parameter Store (`aws_ssm_parameter`) be included in scope alongside Secrets Manager? → A: Yes, add FR for Parameter Store (expand scope to include `aws_ssm_parameter`)
- Q: How should the "80% coverage" metric be defined for measurability? → A: Define as "all 11 user stories implemented" (current scope = 80% coverage)

## Constraints

### Regression Testing Requirement

All existing automated tests under `tests/` MUST continue to pass after any changes. The expected output files in `tests/json/` define the current correct behavior:

- `expected-wordpress.json` - WordPress architecture pattern
- `bastion-expected.json` - Bastion host pattern
- `expected-eks-basic.json` - EKS cluster pattern
- `expected-static-website.json` - Static website with CloudFront pattern

**If an existing test failure is discovered to be due to an error in the expected results** (not a regression caused by new code), this must be reported to the user for review before modifying any expected test output. The user will decide whether to update the expected results.

### Scope of Changes

Changes to `resource_handlers_aws.py` and `cloud_config_aws.py` must be additive where possible. Existing handler functions should only be modified if:
1. A bug is discovered that produces incorrect diagrams
2. The modification is required to support new patterns without breaking existing ones

### Implementation Prioritization

If implementation time is constrained, work should be prioritized by completing all P1 patterns first (API Gateway, Event-Driven, Caching, Authentication), then all P2 patterns, then P3 patterns. This ensures the most common AWS architectural patterns are fully functional before addressing less critical ones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - API Gateway Architecture Visualization (Priority: P1)

As an AWS Solutions Architect, I want TerraVision to correctly visualize API Gateway integrations with Lambda functions, Step Functions, and backend services so that my architecture diagrams accurately represent serverless API patterns.

**Why this priority**: API Gateway is one of the most common AWS services and a core component of serverless architectures. Current handling may not correctly show the complete request flow from Route53 through CloudFront to API Gateway to Lambda/integrations.

**Independent Test**: Can be fully tested by running TerraVision against a standard API Gateway + Lambda Terraform configuration and validating the diagram shows proper flow from users -> Route53 -> API Gateway -> Lambda -> DynamoDB.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with API Gateway REST API integrated with Lambda functions, **When** TerraVision generates a diagram, **Then** the diagram shows API Gateway as an edge service connected to Lambda functions with proper directional arrows indicating request flow.

2. **Given** a Terraform configuration with API Gateway HTTP API using VPC Link to access private resources, **When** TerraVision generates a diagram, **Then** the diagram shows API Gateway connected to VPC Link, which connects to resources inside the VPC (e.g., ALB, NLB).

3. **Given** a Terraform configuration with API Gateway connected to Step Functions, **When** TerraVision generates a diagram, **Then** the diagram shows API Gateway -> Step Functions -> integrated services flow.

4. **Given** a Terraform configuration with multiple API Gateway stages, **When** TerraVision generates a diagram, **Then** stages are consolidated into a single API Gateway node with proper backend connections.

---

### User Story 2 - Event-Driven Architecture Patterns (Priority: P1)

As an AWS Solutions Architect, I want TerraVision to correctly visualize event-driven architectures including EventBridge, SNS, SQS, and Lambda event source mappings so that my diagrams accurately represent asynchronous processing patterns.

**Why this priority**: Event-driven architectures are fundamental to modern AWS applications. The current handlers may not correctly show event flows between EventBridge rules, SNS topics, SQS queues, and Lambda functions.

**Independent Test**: Can be fully tested by running TerraVision against an EventBridge + SNS + SQS + Lambda Terraform configuration and validating the diagram shows proper event flow with correct arrow directions.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with EventBridge rules triggering Lambda functions, **When** TerraVision generates a diagram, **Then** the diagram shows EventBridge -> Lambda with event source connections clearly visible.

2. **Given** a Terraform configuration with SNS topic subscriptions to SQS queues and Lambda, **When** TerraVision generates a diagram, **Then** the diagram shows SNS -> SQS and SNS -> Lambda fan-out pattern.

3. **Given** a Terraform configuration with SQS queue as Lambda event source, **When** TerraVision generates a diagram, **Then** the diagram shows SQS -> Lambda with proper direction indicating Lambda polls from SQS.

4. **Given** a Terraform configuration with DynamoDB Streams triggering Lambda, **When** TerraVision generates a diagram, **Then** the diagram shows DynamoDB -> Lambda stream processing pattern.

5. **Given** a Terraform configuration with Kinesis Data Streams consumed by Lambda, **When** TerraVision generates a diagram, **Then** the diagram shows Kinesis -> Lambda event-driven pattern.

---

### User Story 3 - Caching and Session Management (Priority: P1)

As an AWS Solutions Architect, I want TerraVision to correctly visualize ElastiCache clusters (Redis/Memcached) and their connections to application tiers so that my diagrams show proper caching layer architecture.

**Why this priority**: ElastiCache is one of the most common AWS services for caching and session management. Nearly every production application uses caching.

**Independent Test**: Can be fully tested by running TerraVision against an ElastiCache + EC2/ECS Terraform configuration and validating the diagram shows cache clusters in proper VPC placement.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with ElastiCache Redis cluster in a VPC, **When** TerraVision generates a diagram, **Then** the diagram shows the Redis cluster inside the appropriate subnet with replication group nodes.

2. **Given** a Terraform configuration with ElastiCache connected to ECS services, **When** TerraVision generates a diagram, **Then** the diagram shows ECS -> ElastiCache connection pattern.

3. **Given** a Terraform configuration with ElastiCache Redis cluster with multiple nodes across AZs, **When** TerraVision generates a diagram, **Then** the diagram shows numbered cache nodes distributed across availability zones.

---

### User Story 4 - Authentication and Authorization (Priority: P1)

As an AWS Solutions Architect, I want TerraVision to correctly visualize Cognito User Pools and Identity Pools and their integration with API Gateway and applications so that my diagrams show proper authentication flows.

**Why this priority**: Cognito is the standard AWS authentication service and is used in most serverless and web application architectures.

**Independent Test**: Can be fully tested by running TerraVision against a Cognito + API Gateway + Lambda Terraform configuration.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with Cognito User Pool integrated with API Gateway, **When** TerraVision generates a diagram, **Then** the diagram shows Users -> Cognito -> API Gateway authentication flow.

2. **Given** a Terraform configuration with Cognito Identity Pool for federated access, **When** TerraVision generates a diagram, **Then** the diagram shows Identity Pool connected to IAM roles and integrated services.

3. **Given** a Terraform configuration with Cognito triggers (Lambda functions), **When** TerraVision generates a diagram, **Then** the diagram shows Cognito -> Lambda trigger connections.

---

### User Story 5 - Web Application Firewall (Priority: P2)

As an AWS Solutions Architect, I want TerraVision to correctly visualize WAF (Web Application Firewall) associations with CloudFront, API Gateway, and ALB so that my diagrams show proper security boundaries.

**Why this priority**: WAF is essential for security compliance and is commonly deployed in front of public-facing services.

**Independent Test**: Can be fully tested by running TerraVision against a WAF + CloudFront/ALB Terraform configuration.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with WAF WebACL attached to CloudFront, **When** TerraVision generates a diagram, **Then** the diagram shows WAF as a security layer in front of CloudFront.

2. **Given** a Terraform configuration with WAF WebACL attached to ALB, **When** TerraVision generates a diagram, **Then** the diagram shows WAF protecting the load balancer.

3. **Given** a Terraform configuration with WAF attached to API Gateway, **When** TerraVision generates a diagram, **Then** the diagram shows WAF as a security layer at the API edge.

---

### User Story 6 - SageMaker ML Architecture Visualization (Priority: P2)

As an AWS Solutions Architect, I want TerraVision to correctly visualize SageMaker components including endpoints, models, training jobs, and associated S3/IAM resources so that my ML architecture diagrams are professional and complete.

**Why this priority**: SageMaker is increasingly common in enterprise architectures. Current handling may not correctly show the relationships between SageMaker endpoints, models, notebook instances, and their dependencies on S3 and IAM.

**Independent Test**: Can be fully tested by running TerraVision against a SageMaker endpoint deployment Terraform configuration and validating the diagram shows proper grouping of ML components.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with SageMaker endpoint and model, **When** TerraVision generates a diagram, **Then** the diagram shows SageMaker Endpoint -> Model configuration with proper grouping.

2. **Given** a Terraform configuration with SageMaker notebook instance in a VPC, **When** TerraVision generates a diagram, **Then** the notebook instance appears inside the appropriate subnet with security group boundaries.

3. **Given** a Terraform configuration with SageMaker endpoint connected to S3 for model artifacts, **When** TerraVision generates a diagram, **Then** the diagram shows SageMaker -> S3 bucket connection for model storage.

4. **Given** a Terraform configuration with SageMaker endpoint invoked by Lambda, **When** TerraVision generates a diagram, **Then** the diagram shows Lambda -> SageMaker Endpoint inference pattern.

---

### User Story 7 - Step Functions Workflow Visualization (Priority: P2)

As an AWS Solutions Architect, I want TerraVision to correctly visualize Step Functions state machines and their integrated services so that my workflow architecture diagrams show the orchestration pattern.

**Why this priority**: Step Functions is a key orchestration service. Current handling may not correctly show the relationship between state machines and their task integrations (Lambda, ECS, SageMaker, etc.).

**Independent Test**: Can be fully tested by running TerraVision against a Step Functions + Lambda Terraform configuration and validating the diagram shows proper orchestration flow.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with Step Functions state machine invoking Lambda functions, **When** TerraVision generates a diagram, **Then** the diagram shows Step Functions -> Lambda orchestration pattern.

2. **Given** a Terraform configuration with Step Functions orchestrating multiple services (Lambda, ECS, SageMaker), **When** TerraVision generates a diagram, **Then** the diagram shows Step Functions as a central orchestrator connected to all integrated services.

3. **Given** a Terraform configuration with Step Functions triggered by API Gateway, **When** TerraVision generates a diagram, **Then** the diagram shows API Gateway -> Step Functions -> backend services flow.

---

### User Story 8 - S3 Data Flow and Notifications (Priority: P2)

As an AWS Solutions Architect, I want TerraVision to correctly visualize S3 bucket event notifications, replication, and data flow patterns so that my diagrams show proper data architecture.

**Why this priority**: S3 is foundational to AWS and often serves as the hub for data flow patterns. S3 event notifications triggering Lambda or SQS are extremely common.

**Independent Test**: Can be fully tested by running TerraVision against an S3 + Lambda notification Terraform configuration.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with S3 bucket notification triggering Lambda, **When** TerraVision generates a diagram, **Then** the diagram shows S3 -> Lambda event notification pattern.

2. **Given** a Terraform configuration with S3 bucket notification to SQS queue, **When** TerraVision generates a diagram, **Then** the diagram shows S3 -> SQS notification pattern.

3. **Given** a Terraform configuration with S3 cross-region replication, **When** TerraVision generates a diagram, **Then** the diagram shows S3 bucket -> S3 bucket replication flow.

---

### User Story 9 - Secrets and Configuration Management (Priority: P2)

As an AWS Solutions Architect, I want TerraVision to correctly visualize Secrets Manager and Parameter Store connections to application resources so that my diagrams show proper secrets management patterns.

**Why this priority**: Secrets Manager and Parameter Store are essential for secure application configuration and are used in nearly all production deployments.

**Independent Test**: Can be fully tested by running TerraVision against a Secrets Manager + Lambda/ECS Terraform configuration.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with Secrets Manager secret accessed by Lambda, **When** TerraVision generates a diagram, **Then** the diagram shows Lambda -> Secrets Manager connection.

2. **Given** a Terraform configuration with Secrets Manager with RDS rotation, **When** TerraVision generates a diagram, **Then** the diagram shows Secrets Manager connected to both RDS and the rotation Lambda.

3. **Given** a Terraform configuration with Parameter Store parameters accessed by ECS, **When** TerraVision generates a diagram, **Then** the diagram shows ECS -> Parameter Store connection.

---

### User Story 10 - Serverless Data Processing Pipelines (Priority: P3)

As an AWS Solutions Architect, I want TerraVision to correctly visualize data processing pipelines including Glue, Athena, Kinesis Firehose, and data lake patterns so that my analytics architecture diagrams are complete.

**Why this priority**: Data processing is a common pattern but less frequent than API and event-driven architectures.

**Independent Test**: Can be fully tested by running TerraVision against a Glue + S3 + Athena Terraform configuration.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with Glue jobs reading from and writing to S3, **When** TerraVision generates a diagram, **Then** the diagram shows S3 -> Glue -> S3 ETL pattern.

2. **Given** a Terraform configuration with Athena querying S3 data lake, **When** TerraVision generates a diagram, **Then** the diagram shows Athena -> S3 query pattern.

3. **Given** a Terraform configuration with Kinesis Firehose delivering to S3, **When** TerraVision generates a diagram, **Then** the diagram shows Kinesis Firehose -> S3 delivery stream pattern.

4. **Given** a Terraform configuration with Kinesis Firehose with Lambda transformation, **When** TerraVision generates a diagram, **Then** the diagram shows Kinesis Firehose -> Lambda -> S3 transformation pattern.

---

### User Story 11 - AppSync GraphQL APIs (Priority: P3)

As an AWS Solutions Architect, I want TerraVision to correctly visualize AppSync GraphQL APIs and their data sources so that my diagrams show proper GraphQL architecture patterns.

**Why this priority**: AppSync is growing in usage for GraphQL APIs but is less common than REST API Gateway.

**Independent Test**: Can be fully tested by running TerraVision against an AppSync + DynamoDB Terraform configuration.

**Acceptance Scenarios**:

1. **Given** a Terraform configuration with AppSync API connected to DynamoDB data sources, **When** TerraVision generates a diagram, **Then** the diagram shows AppSync -> DynamoDB connection pattern.

2. **Given** a Terraform configuration with AppSync using Lambda resolvers, **When** TerraVision generates a diagram, **Then** the diagram shows AppSync -> Lambda resolver pattern.

3. **Given** a Terraform configuration with AppSync with Cognito authentication, **When** TerraVision generates a diagram, **Then** the diagram shows Users -> Cognito -> AppSync flow.

---

### Edge Cases

**Handled:**
- API Gateway with no backend integrations (e.g., OpenAPI spec): Show API Gateway with placeholder "External Integration" node
- Circular event patterns (e.g., Lambda -> SNS -> Lambda): Existing code handles and removes circular references - no change needed
- Cross-module event source mappings: Existing handlers resolve cross-module references and create links - no change needed

**Out of Scope (known limitations for this feature):**
- SageMaker resources deployed across multiple accounts: Not supported - single-account Terraform configurations only
- Nested Step Functions (state machines calling other state machines): Not supported - show as separate unconnected state machines
- ElastiCache clusters with Global Datastore (cross-region): Not supported - single-region clusters only
- WAF rules referencing resources not in Terraform configuration: Not supported - WAF shown without those connections
- S3 bucket policies granting cross-account access: Not supported - cross-account relationships not visualized

## Requirements *(mandatory)*

### Functional Requirements

#### API Gateway
- **FR-001**: System MUST detect and properly connect API Gateway resources (REST API, HTTP API) to their backend integrations (Lambda, Step Functions, HTTP endpoints, VPC Link)
- **FR-002**: System MUST consolidate API Gateway resources (stages, deployments, methods, integrations) into a single logical API Gateway node
- **FR-003**: System MUST position API Gateway as an edge service outside VPC boundaries
- **FR-003a**: When API Gateway has no backend integrations defined in Terraform (e.g., OpenAPI spec), system MUST show API Gateway connected to a placeholder "External Integration" node

#### Event-Driven Architecture
- **FR-004**: System MUST detect EventBridge rules and connect them to their target resources (Lambda, Step Functions, SNS, SQS)
- **FR-005**: System MUST properly represent SNS -> SQS -> Lambda subscription patterns with correct arrow directions
- **FR-006**: System MUST detect Lambda event source mappings and create connections from source (SQS, Kinesis, DynamoDB Streams) to Lambda

#### Caching and Authentication
- **FR-007**: System MUST detect ElastiCache clusters and position them inside VPC subnets with proper security group associations
- **FR-008**: System MUST expand ElastiCache replication groups across availability zones with numbered node instances
- **FR-009**: System MUST detect Cognito User Pools and Identity Pools and connect them to API Gateway and application resources
- **FR-010**: System MUST show Cognito Lambda triggers as connections from Cognito to Lambda functions

#### Security
- **FR-011**: System MUST detect WAF WebACL associations and show WAF as a security layer in front of CloudFront, ALB, or API Gateway
- **FR-012**: System MUST consolidate WAF rules and rule groups into a single WAF node

#### Machine Learning
- **FR-013**: System MUST consolidate SageMaker resources (endpoint, endpoint configuration, model) into a logical ML service group
- **FR-014**: System MUST connect SageMaker components to their S3 model artifact locations
- **FR-015**: System MUST position SageMaker notebook instances inside VPC subnets when VPC configuration exists

#### Workflow Orchestration
- **FR-016**: System MUST detect Step Functions state machines and connect them to integrated services
- **FR-017**: System MUST handle API Gateway -> Step Functions -> Lambda orchestration patterns

#### Data and Storage
- **FR-018**: System MUST detect S3 bucket notifications and create connections to Lambda, SQS, or SNS targets
- **FR-019**: System MUST detect S3 replication configurations and show source -> destination bucket relationships
- **FR-020**: System MUST detect Secrets Manager secrets and connect them to resources that access them
- **FR-020a**: System MUST detect Parameter Store parameters (`aws_ssm_parameter`) and connect them to resources that access them (Lambda, ECS, EC2)
- **FR-021**: System MUST detect and properly connect Glue jobs to their S3 data sources and targets
- **FR-022**: System MUST detect Kinesis Firehose delivery streams and show data flow to destinations

#### AppSync
- **FR-023**: System MUST detect AppSync APIs and connect them to their data sources (DynamoDB, Lambda, HTTP)
- **FR-024**: System MUST position AppSync as an edge service similar to API Gateway

#### General
- **FR-025**: System MUST ensure all event-driven connections have correct arrow directions (source -> consumer)
- **FR-026**: System MUST NOT create duplicate connections for transitive relationships (e.g., if A -> B -> C exists, don't also add A -> C unless architecturally significant)
- **FR-027**: System MUST maintain backward compatibility with all existing test cases under tests/

### Key Entities

- **API Gateway Resources**: `aws_api_gateway_rest_api`, `aws_api_gateway_stage`, `aws_api_gateway_deployment`, `aws_api_gateway_integration`, `aws_api_gateway_method`, `aws_apigatewayv2_api`, `aws_apigatewayv2_integration`, `aws_apigatewayv2_vpc_link`
- **Event-Driven Resources**: `aws_cloudwatch_event_rule`, `aws_cloudwatch_event_target`, `aws_sns_topic`, `aws_sns_topic_subscription`, `aws_sqs_queue`, `aws_lambda_event_source_mapping`, `aws_kinesis_stream`, `aws_dynamodb_table` (with streams)
- **Caching Resources**: `aws_elasticache_cluster`, `aws_elasticache_replication_group`, `aws_elasticache_subnet_group`
- **Authentication Resources**: `aws_cognito_user_pool`, `aws_cognito_user_pool_client`, `aws_cognito_identity_pool`, `aws_cognito_user_pool_domain`
- **Security Resources**: `aws_wafv2_web_acl`, `aws_wafv2_web_acl_association`, `aws_waf_web_acl`
- **SageMaker Resources**: `aws_sagemaker_endpoint`, `aws_sagemaker_endpoint_configuration`, `aws_sagemaker_model`, `aws_sagemaker_notebook_instance`
- **Step Functions Resources**: `aws_sfn_state_machine`
- **Storage Resources**: `aws_s3_bucket_notification`, `aws_s3_bucket_replication_configuration`, `aws_secretsmanager_secret`, `aws_ssm_parameter`
- **Data Processing Resources**: `aws_glue_job`, `aws_glue_catalog_database`, `aws_glue_crawler`, `aws_athena_workgroup`, `aws_kinesis_firehose_delivery_stream`
- **AppSync Resources**: `aws_appsync_graphql_api`, `aws_appsync_datasource`, `aws_appsync_resolver`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing automated tests under `tests/` continue to pass without modification to expected results (unless a bug in expected results is identified and approved for correction)
- **SC-002**: All test Terraform configurations for common AWS patterns (API Gateway, Event-Driven, Caching, Authentication, SageMaker, Step Functions) generate diagrams that an AWS Solutions Architect would recognize as correct
- **SC-003**: API Gateway patterns show clear request flow from edge to backend with no orphaned or incorrectly connected resources
- **SC-004**: Event-driven patterns show correct producer -> consumer arrow directions for all event sources
- **SC-005**: ElastiCache clusters appear inside VPC with proper subnet and security group placement
- **SC-006**: Cognito resources show proper authentication flow integration with API Gateway and applications
- **SC-007**: WAF appears as a security boundary in front of protected resources
- **SC-008**: SageMaker resources are grouped logically and show dependencies on S3 and IAM
- **SC-009**: Step Functions orchestration patterns clearly show the state machine as a central coordinator
- **SC-010**: S3 event notifications show proper event flow to Lambda/SQS/SNS targets
- **SC-011**: No regression in existing AWS resource handling (VPC, EC2, ECS, EKS, RDS patterns continue to work correctly)
- **SC-012**: Test Terraform configurations covering each pattern are created (based on official AWS/HashiCorp examples) and committed to the repository for ongoing validation
- **SC-013**: All 11 user stories are implemented and validated, providing coverage of the top 80% most common AWS architectural patterns (API Gateway, Event-Driven, ElastiCache, Cognito, WAF, SageMaker, Step Functions, S3 Notifications, Secrets Manager/Parameter Store, Glue/Firehose, AppSync)
