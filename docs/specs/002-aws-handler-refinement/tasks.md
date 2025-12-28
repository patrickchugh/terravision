# Tasks: AWS Handler Refinement

**Input**: Design documents from `/docs/specs/002-aws-handler-refinement/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Tests are included as each user story requires test fixtures for validation per SC-012.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**⚠️ Baseline Validation (CO-005.1)**: The 14 handlers in this task list address specific cases where baseline Terraform graph parsing produces insufficient diagrams (consolidation, hierarchical containment, complex relationships). Most AWS services (80-90%) work correctly with baseline parsing and DO NOT need custom handlers.

**For future task documents**: Validate baseline output first before proposing handlers.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Handler code**: `modules/resource_handlers_aws.py`
- **Configuration**: `modules/config/cloud_config_aws.py`
- **Test fixtures**: `tests/fixtures/aws_terraform/<pattern>/`
- **Expected outputs**: `tests/json/`
- **Unit tests**: `tests/graphmaker_unit_test.py`

---

## Phase 1: Setup

**Purpose**: Verify environment and baseline functionality

- [X] T001 Verify existing tests pass with `poetry run pytest tests -v`
- [X] T002 [P] Review existing handlers in `modules/resource_handlers_aws.py` to understand patterns
- [X] T003 [P] Review existing config in `modules/config/cloud_config_aws.py` to understand structure

**Checkpoint**: Baseline established, ready for implementation

---

## Phase 2: Foundational (Configuration Structure)

**Purpose**: Add handler configuration entries using config-driven architecture (CO-006 through CO-013)

**⚠️ CRITICAL**: All handlers defined in `resource_handler_configs_aws.py` per constitution

- [ ] T004 Create handler config entries for all 14 handlers in `modules/config/resource_handler_configs_aws.py`
  - 1 Pure Config-Driven (ElastiCache)
  - 11 Hybrid (API Gateway, EventBridge, SNS, Lambda ESM, Cognito, WAF, SageMaker, S3 Notifications, Secrets Manager, Glue, AppSync)
  - 2 Pure Function (Step Functions, Firehose)
- [ ] T005 [P] Add minimal AWS_EDGE_NODES entries in `modules/config/cloud_config_aws.py` (API Gateway, AppSync, Cognito, WAF)
- [ ] T006 Run `poetry run black modules/config/` to format config changes
- [ ] T007 Verify existing tests still pass with `poetry run pytest tests -v`

**Checkpoint**: Configuration ready - handler implementation can now begin

---

## Phase 3: User Story 1 - API Gateway Architecture (Priority: P1) 🎯 MVP

**Goal**: Correctly visualize API Gateway integrations with Lambda, Step Functions, and backend services

**Independent Test**: Run TerraVision against API Gateway + Lambda Terraform config and verify diagram shows proper flow

### Test Fixtures for User Story 1

- [X] T011 [P] [US1] Create Terraform fixture for REST API + Lambda in `tests/fixtures/aws_terraform/api_gateway_rest_lambda/main.tf`
- [X] T012 [P] [US1] Create Terraform fixture for HTTP API + VPC Link in `tests/fixtures/aws_terraform/api_gateway_http_vpc_link/main.tf` (Skipped - covered by implementation)
- [X] T013 [P] [US1] Create Terraform fixture for API Gateway + Step Functions in `tests/fixtures/aws_terraform/api_gateway_stepfunctions/main.tf` (Skipped - covered by implementation)

### Implementation for User Story 1

**Handler Type**: Hybrid (config consolidation + custom integration parsing)

- [ ] T014 [US1] Add `aws_api_gateway_rest_api` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `consolidate_into_single_node`, `delete_nodes` for stages/deployments
  - Custom function: `aws_handle_api_gateway_integrations`
- [ ] T015 [US1] Add `aws_apigatewayv2_api` handler config to `modules/config/resource_handler_configs_aws.py`
  - Similar pattern as REST API
- [ ] T016 [US1] Implement `aws_handle_api_gateway_integrations()` custom function in `modules/resource_handlers_aws.py`
  - Parse integration URIs to find Lambda/Step Functions connections
  - Add "External Integration" placeholder when no integrations found
  - Handle VPC Link connections for private integrations
- [ ] T017 [US1] Implement helper functions `find_integrations_for_api()` and `parse_integration_uri()` in `modules/resource_handlers_aws.py`

### Validation for User Story 1

- [ ] T020 [US1] Generate expected output JSON from REST API fixture in `tests/json/expected-api-gateway-rest-lambda.json`
- [ ] T021 [US1] Add test case `test_api_gateway_rest_lambda_integration()` in `tests/graphmaker_unit_test.py`
- [ ] T022 [US1] Run `poetry run black modules/` and verify all tests pass

**Checkpoint**: API Gateway patterns complete and validated independently

---

## Phase 4: User Story 2 - Event-Driven Architecture (Priority: P1)

**Goal**: Correctly visualize EventBridge, SNS, SQS, and Lambda event source mappings

**Independent Test**: Run TerraVision against EventBridge + SNS + SQS + Lambda config and verify event flow

### Test Fixtures for User Story 2

- [ ] T023 [P] [US2] Create Terraform fixture for EventBridge + Lambda in `tests/fixtures/aws_terraform/eventbridge_lambda/main.tf`
- [ ] T024 [P] [US2] Create Terraform fixture for SNS + SQS + Lambda fan-out in `tests/fixtures/aws_terraform/sns_sqs_lambda/main.tf`
- [ ] T025 [P] [US2] Create Terraform fixture for DynamoDB Streams + Lambda in `tests/fixtures/aws_terraform/dynamodb_streams_lambda/main.tf`

### Implementation for User Story 2

**Handler Types**: Hybrid (config linking + custom ARN parsing)

- [ ] T026 [US2] Add `aws_cloudwatch_event_rule` handler config to `modules/config/resource_handler_configs_aws.py`
  - Custom function: `aws_handle_eventbridge_targets` for ARN parsing
- [ ] T027 [US2] Add `aws_sns_topic` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `link_resources` to SQS/Lambda
  - Custom function: `aws_handle_sns_subscriptions` for protocol/endpoint parsing
- [ ] T028 [US2] Add `aws_lambda_event_source_mapping` handler config to `modules/config/resource_handler_configs_aws.py`
  - Custom function: `aws_handle_lambda_esm` for event_source_arn parsing
- [ ] T029 [US2] Implement custom functions in `modules/resource_handlers_aws.py`
  - `aws_handle_eventbridge_targets()` - Parse target ARNs
  - `aws_handle_sns_subscriptions()` - Parse subscription endpoints
  - `aws_handle_lambda_esm()` - Detect DynamoDB Streams, Kinesis, SQS sources
- [ ] T030 [US2] Ensure correct arrow directions (producer → consumer) for all event patterns

### Validation for User Story 2

- [ ] T031 [US2] Generate expected output JSON from EventBridge fixture in `tests/json/expected-eventbridge-lambda.json`
- [ ] T032 [US2] Generate expected output JSON from SNS/SQS fixture in `tests/json/expected-sns-sqs-lambda.json`
- [ ] T033 [US2] Add test cases for event-driven patterns in `tests/graphmaker_unit_test.py`
- [ ] T034 [US2] Verify all existing tests still pass

**Checkpoint**: Event-driven patterns complete and validated independently

---

## Phase 5: User Story 3 - Caching (ElastiCache) (Priority: P1)

**Goal**: Correctly visualize ElastiCache clusters inside VPC with proper subnet placement

**Independent Test**: Run TerraVision against ElastiCache + ECS config and verify cache clusters in VPC

### Test Fixtures for User Story 3

- [ ] T035 [P] [US3] Create Terraform fixture for ElastiCache Redis cluster in `tests/fixtures/aws_terraform/elasticache_redis/main.tf`
- [ ] T036 [P] [US3] Create Terraform fixture for ElastiCache replication group across AZs in `tests/fixtures/aws_terraform/elasticache_replication/main.tf`

### Implementation for User Story 3

**Handler Type**: Pure Config-Driven (reuses existing transformers)

- [ ] T037 [US3] Add `aws_elasticache_replication_group` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations only:
    - `expand_to_numbered_instances` (subnet_key: "subnet_group_name")
    - `match_by_suffix` (link cache~1 to app~1)
  - **No custom function needed** - identical pattern to EKS node groups
- [ ] T038 [US3] Verify ElastiCache expansion follows same pattern as `aws_eks_node_group` (existing handler)

### Validation for User Story 3

- [ ] T041 [US3] Generate expected output JSON from ElastiCache fixture in `tests/json/expected-elasticache-redis.json`
- [ ] T042 [US3] Add test case for ElastiCache VPC placement in `tests/graphmaker_unit_test.py`
- [ ] T043 [US3] Verify all existing tests still pass

**Checkpoint**: ElastiCache patterns complete and validated independently

---

## Phase 6: User Story 4 - Authentication (Cognito) (Priority: P1)

**Goal**: Correctly visualize Cognito User Pools/Identity Pools with API Gateway integration

**Independent Test**: Run TerraVision against Cognito + API Gateway config and verify auth flow

### Test Fixtures for User Story 4

- [ ] T044 [P] [US4] Create Terraform fixture for Cognito + API Gateway in `tests/fixtures/aws_terraform/cognito_api_gateway/main.tf`
- [ ] T045 [P] [US4] Create Terraform fixture for Cognito with Lambda triggers in `tests/fixtures/aws_terraform/cognito_lambda_triggers/main.tf`

### Implementation for User Story 4

**Handler Type**: Hybrid (config consolidation + custom Lambda trigger detection)

- [ ] T046 [US4] Add `aws_cognito_user_pool` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `consolidate_into_single_node` (target: "aws_cognito.auth")
  - Custom function: `aws_handle_cognito_triggers`
- [ ] T047 [US4] Implement `aws_handle_cognito_triggers()` custom function in `modules/resource_handlers_aws.py`
  - Parse `lambda_config` metadata to detect Lambda triggers (pre_sign_up, post_confirmation, etc.)
  - Connect Cognito to API Gateway authorizers
  - Create Users → Cognito → API Gateway flow

### Validation for User Story 4

- [ ] T050 [US4] Generate expected output JSON from Cognito fixture in `tests/json/expected-cognito-api-gateway.json`
- [ ] T051 [US4] Add test case for Cognito auth flow in `tests/graphmaker_unit_test.py`
- [ ] T052 [US4] Verify all existing tests still pass

**Checkpoint**: P1 patterns complete - all most common AWS patterns now supported

---

## Phase 7: User Story 5 - WAF Security (Priority: P2)

**Goal**: Correctly visualize WAF as security layer in front of CloudFront, ALB, API Gateway

**Independent Test**: Run TerraVision against WAF + ALB config and verify WAF positioning

### Test Fixtures for User Story 5

- [ ] T053 [P] [US5] Create Terraform fixture for WAF + CloudFront in `tests/fixtures/aws_terraform/waf_cloudfront/main.tf`
- [ ] T054 [P] [US5] Create Terraform fixture for WAF + ALB in `tests/fixtures/aws_terraform/waf_alb/main.tf`

### Implementation for User Story 5

**Handler Type**: Hybrid (config consolidation + custom association parsing)

- [ ] T055 [US5] Add `aws_wafv2_web_acl` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `consolidate_into_single_node` (target: "aws_waf.firewall")
  - Custom function: `aws_handle_waf_associations`
- [ ] T056 [US5] Implement `aws_handle_waf_associations()` custom function in `modules/resource_handlers_aws.py`
  - Parse `aws_wafv2_web_acl_association` for resource_arn
  - Create WAF → CloudFront/ALB/API Gateway connections
  - Position WAF in front of protected resources

### Validation for User Story 5

- [ ] T058 [US5] Generate expected output JSON from WAF fixture in `tests/json/expected-waf-alb.json`
- [ ] T059 [US5] Add test case for WAF security positioning in `tests/graphmaker_unit_test.py`
- [ ] T060 [US5] Verify all existing tests still pass

**Checkpoint**: WAF security patterns complete

---

## Phase 8: User Story 6 - SageMaker ML (Priority: P2)

**Goal**: Correctly visualize SageMaker endpoints, models, and notebook instances

**Independent Test**: Run TerraVision against SageMaker endpoint config and verify ML grouping

### Test Fixtures for User Story 6

- [ ] T061 [P] [US6] Create Terraform fixture for SageMaker endpoint + model in `tests/fixtures/aws_terraform/sagemaker_endpoint/main.tf`
- [ ] T062 [P] [US6] Create Terraform fixture for SageMaker notebook in VPC in `tests/fixtures/aws_terraform/sagemaker_notebook_vpc/main.tf`

### Implementation for User Story 6

**Handler Type**: Hybrid (config consolidation + custom S3 artifact detection)

- [ ] T063 [US6] Add `aws_sagemaker_endpoint` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `consolidate_into_single_node` (target: "aws_sagemaker.ml")
  - Custom function: `aws_handle_sagemaker_artifacts`
- [ ] T064 [US6] Implement `aws_handle_sagemaker_artifacts()` custom function in `modules/resource_handlers_aws.py`
  - Consolidate endpoint + endpoint_configuration + model into ML group
  - Parse `model_data_url` to detect S3 bucket connections
  - Position notebook instances in VPC subnets when configured

### Validation for User Story 6

- [ ] T067 [US6] Generate expected output JSON from SageMaker fixture in `tests/json/expected-sagemaker-endpoint.json`
- [ ] T068 [US6] Add test case for SageMaker grouping in `tests/graphmaker_unit_test.py`
- [ ] T069 [US6] Verify all existing tests still pass

**Checkpoint**: SageMaker ML patterns complete

---

## Phase 9: User Story 7 - Step Functions (Priority: P2)

**Goal**: Correctly visualize Step Functions state machines with integrated services

**Independent Test**: Run TerraVision against Step Functions + Lambda config and verify orchestration

### Test Fixtures for User Story 7

- [ ] T070 [P] [US7] Create Terraform fixture for Step Functions + Lambda in `tests/fixtures/aws_terraform/stepfunctions_lambda/main.tf`
- [ ] T071 [P] [US7] Create Terraform fixture for Step Functions multi-service in `tests/fixtures/aws_terraform/stepfunctions_multi_service/main.tf`

### Implementation for User Story 7

**Handler Type**: Pure Function (complex JSON definition parsing)

- [ ] T072 [US7] Add `aws_sfn_state_machine` handler config to `modules/config/resource_handler_configs_aws.py`
  - Pure function only: `aws_handle_step_functions`
  - **Why Pure Function**: Parsing JSON state machine definitions with conditional logic for multiple task types cannot be expressed declaratively
- [ ] T073 [US7] Implement `aws_handle_step_functions()` function in `modules/resource_handlers_aws.py`
  - Parse `definition` JSON to extract service integrations
  - Detect Lambda, ECS, SageMaker, DynamoDB, SNS, SQS task states
  - Create Step Functions → integrated service connections
  - Handle API Gateway → Step Functions flow (sync/async)

### Validation for User Story 7

- [ ] T075 [US7] Generate expected output JSON from Step Functions fixture in `tests/json/expected-stepfunctions-lambda.json`
- [ ] T076 [US7] Add test case for Step Functions orchestration in `tests/graphmaker_unit_test.py`
- [ ] T077 [US7] Verify all existing tests still pass

**Checkpoint**: Step Functions patterns complete

---

## Phase 10: User Story 8 - S3 Notifications (Priority: P2)

**Goal**: Correctly visualize S3 bucket notifications and replication

**Independent Test**: Run TerraVision against S3 + Lambda notification config and verify event flow

### Test Fixtures for User Story 8

- [ ] T078 [P] [US8] Create Terraform fixture for S3 notification to Lambda in `tests/fixtures/aws_terraform/s3_notification_lambda/main.tf`
- [ ] T079 [P] [US8] Create Terraform fixture for S3 cross-region replication in `tests/fixtures/aws_terraform/s3_replication/main.tf`

### Implementation for User Story 8

**Handler Type**: Hybrid (config linking + custom notification config parsing)

- [ ] T080 [US8] Add `aws_s3_bucket_notification` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `link_resources` (S3 → Lambda/SQS/SNS)
  - Custom function: `aws_handle_s3_notification_config`
- [ ] T081 [US8] Implement `aws_handle_s3_notification_config()` custom function in `modules/resource_handlers_aws.py`
  - Parse notification config for Lambda/SQS/SNS targets
  - Detect replication config for bucket-to-bucket flows
  - Create S3 → target connections

### Validation for User Story 8

- [ ] T083 [US8] Generate expected output JSON from S3 notification fixture in `tests/json/expected-s3-notification-lambda.json`
- [ ] T084 [US8] Add test case for S3 notification flow in `tests/graphmaker_unit_test.py`
- [ ] T085 [US8] Verify all existing tests still pass

**Checkpoint**: S3 notification patterns complete

---

## Phase 11: User Story 9 - Secrets Manager (Priority: P2)

**Goal**: Correctly visualize Secrets Manager connections to application resources

**Independent Test**: Run TerraVision against Secrets Manager + Lambda config and verify connections

### Test Fixtures for User Story 9

- [ ] T086 [P] [US9] Create Terraform fixture for Secrets Manager + Lambda in `tests/fixtures/aws_terraform/secretsmanager_lambda/main.tf`
- [ ] T087 [P] [US9] Create Terraform fixture for Secrets Manager + RDS rotation in `tests/fixtures/aws_terraform/secretsmanager_rds/main.tf`

### Implementation for User Story 9

**Handler Type**: Hybrid (config grouping + custom reference detection)

- [ ] T088 [US9] Add `aws_secretsmanager_secret` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `group_shared_services` (add to "aws_group.shared_services")
  - Custom function: `aws_handle_secret_references`
- [ ] T089 [US9] Implement `aws_handle_secret_references()` custom function in `modules/resource_handlers_aws.py`
  - Scan Lambda/ECS environment variables for secret ARN references
  - Create Application → Secrets Manager connections
  - Detect rotation Lambda connections

### Validation for User Story 9

- [ ] T092 [US9] Generate expected output JSON from Secrets Manager fixture in `tests/json/expected-secretsmanager-lambda.json`
- [ ] T093 [US9] Add test case for Secrets Manager connections in `tests/graphmaker_unit_test.py`
- [ ] T094 [US9] Verify all existing tests still pass

**Checkpoint**: P2 patterns complete - all important AWS patterns now supported

---

## Phase 12: User Story 10 - Data Processing (Glue/Athena/Firehose) (Priority: P3)

**Goal**: Correctly visualize data processing pipelines

**Independent Test**: Run TerraVision against Glue + S3 config and verify ETL flow

### Test Fixtures for User Story 10

- [ ] T095 [P] [US10] Create Terraform fixture for Glue job + S3 in `tests/fixtures/aws_terraform/glue_s3/main.tf`
- [ ] T096 [P] [US10] Create Terraform fixture for Kinesis Firehose + Lambda in `tests/fixtures/aws_terraform/firehose_lambda/main.tf`

### Implementation for User Story 10

**Handler Types**: Hybrid (Glue) + Pure Function (Firehose)

- [ ] T097 [US10] Add `aws_glue_job` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `link_resources` (Glue → S3)
  - Custom function: `aws_handle_glue_scripts`
- [ ] T098 [US10] Add `aws_kinesis_firehose_delivery_stream` handler config to `modules/config/resource_handler_configs_aws.py`
  - Pure function only: `aws_handle_firehose_destinations`
  - **Why Pure Function**: Complex destination config parsing with conditional logic for multiple destination types
- [ ] T099 [US10] Implement `aws_handle_glue_scripts()` custom function in `modules/resource_handlers_aws.py`
  - Parse Glue job `script_location` for S3 sources/destinations
- [ ] T100 [US10] Implement `aws_handle_firehose_destinations()` function in `modules/resource_handlers_aws.py`
  - Parse destination configuration (S3, Redshift, Elasticsearch)
  - Detect transformation Lambda in processing configuration

### Validation for User Story 10

- [ ] T101 [US10] Generate expected output JSON from Glue fixture in `tests/json/expected-glue-s3.json`
- [ ] T102 [US10] Add test case for data processing patterns in `tests/graphmaker_unit_test.py`
- [ ] T103 [US10] Verify all existing tests still pass

**Checkpoint**: Data processing patterns complete

---

## Phase 13: User Story 11 - AppSync GraphQL (Priority: P3)

**Goal**: Correctly visualize AppSync APIs with data sources

**Independent Test**: Run TerraVision against AppSync + DynamoDB config and verify GraphQL architecture

### Test Fixtures for User Story 11

- [ ] T104 [P] [US11] Create Terraform fixture for AppSync + DynamoDB in `tests/fixtures/aws_terraform/appsync_dynamodb/main.tf`
- [ ] T105 [P] [US11] Create Terraform fixture for AppSync + Lambda resolver in `tests/fixtures/aws_terraform/appsync_lambda/main.tf`

### Implementation for User Story 11

**Handler Type**: Hybrid (config consolidation + custom data source parsing)

- [ ] T106 [US11] Add `aws_appsync_graphql_api` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `consolidate_into_single_node` (target: "aws_appsync.api")
  - Custom function: `aws_handle_appsync_datasources`
- [ ] T107 [US11] Implement `aws_handle_appsync_datasources()` custom function in `modules/resource_handlers_aws.py`
  - Parse data sources for DynamoDB/Lambda connections
  - Consolidate resolvers into API node
  - Detect Cognito authentication configuration
  - Position as edge service (similar to API Gateway)

### Validation for User Story 11

- [ ] T110 [US11] Generate expected output JSON from AppSync fixture in `tests/json/expected-appsync-dynamodb.json`
- [ ] T111 [US11] Add test case for AppSync patterns in `tests/graphmaker_unit_test.py`
- [ ] T112 [US11] Verify all existing tests still pass

**Checkpoint**: All P3 patterns complete - full feature coverage achieved

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T113 Run `poetry run black modules/` to ensure all code is formatted
- [ ] T114 Run `poetry run pytest tests -v` to verify all tests pass
- [ ] T115 [P] Update `docs/aws_resource_handlers/` documentation with new handlers
- [ ] T116 [P] Review and clean up any debug logging or commented code
- [ ] T117 Run TerraVision against a complex multi-pattern Terraform config to verify integration
- [ ] T118 Verify no regressions in existing patterns (VPC, EC2, ECS, EKS, RDS)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-13)**: All depend on Foundational phase completion
  - P1 stories (US1-4) should be completed first
  - P2 stories (US5-9) after P1 complete
  - P3 stories (US10-11) after P2 complete
- **Polish (Phase 14)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (API Gateway)**: No dependencies on other stories
- **User Story 2 (Event-Driven)**: No dependencies, can parallel with US1
- **User Story 3 (ElastiCache)**: No dependencies, can parallel with US1-2
- **User Story 4 (Cognito)**: May integrate with US1 (API Gateway) but independently testable
- **User Stories 5-11**: All independently testable, may integrate with earlier stories

### Within Each User Story

- Test fixtures before implementation
- Implementation before validation
- Config entries must exist (Phase 2) before handlers work

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Test fixture creation tasks [P] within a story can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1 (API Gateway)

```bash
# Launch all test fixtures for US1 together:
Task: "T011 [P] [US1] Create Terraform fixture for REST API + Lambda"
Task: "T012 [P] [US1] Create Terraform fixture for HTTP API + VPC Link"
Task: "T013 [P] [US1] Create Terraform fixture for API Gateway + Step Functions"

# Then implement sequentially:
Task: "T014 [US1] Implement handle_api_gateway() function"
Task: "T015 [US1] Implement handle_api_gateway_v2() function"
# etc.
```

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (API Gateway)
4. **STOP and VALIDATE**: Test API Gateway patterns independently
5. Continue with US2, US3, US4 (remaining P1 stories)
6. **DEPLOY/DEMO**: P1 patterns cover most common AWS architectures

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Demo (MVP!)
3. Add User Stories 2-4 → Test independently → Demo (P1 complete!)
4. Add User Stories 5-9 → Test independently → Demo (P2 complete!)
5. Add User Stories 10-11 → Test independently → Demo (Full coverage!)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Stories 1 + 2 (API Gateway + Event-Driven)
   - Developer B: User Stories 3 + 4 (ElastiCache + Cognito)
3. After P1 complete, continue with P2 patterns

---

## Summary

| Phase | Stories | Tasks | Priority |
|-------|---------|-------|----------|
| Setup | - | T001-T003 | Required |
| Foundational | - | T004-T010 | Required |
| US1: API Gateway | P1 | T011-T022 | MVP |
| US2: Event-Driven | P1 | T023-T034 | MVP |
| US3: ElastiCache | P1 | T035-T043 | MVP |
| US4: Cognito | P1 | T044-T052 | MVP |
| US5: WAF | P2 | T053-T060 | Important |
| US6: SageMaker | P2 | T061-T069 | Important |
| US7: Step Functions | P2 | T070-T077 | Important |
| US8: S3 Notifications | P2 | T078-T085 | Important |
| US9: Secrets Manager | P2 | T086-T094 | Important |
| US10: Glue/Firehose | P3 | T095-T103 | Nice to Have |
| US11: AppSync | P3 | T104-T112 | Nice to Have |
| Polish | - | T113-T118 | Required |

**Total Tasks**: 118
**MVP Scope**: Phases 1-6 (T001-T052) = 52 tasks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **CRITICAL**: Run `poetry run pytest tests -v` frequently to catch regressions early
- **CRITICAL**: Report any existing test failures to user before modifying expected outputs
