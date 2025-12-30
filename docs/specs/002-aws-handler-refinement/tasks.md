# Tasks: AWS Handler Refinement

**Input**: Design documents from `/docs/specs/002-aws-handler-refinement/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Tests are included as each user story requires test fixtures for validation per SC-012.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**⚠️ Baseline Validation (CO-005.1)**: The 14 handlers in this task list address specific cases where baseline Terraform graph parsing produces insufficient diagrams (consolidation, hierarchical containment, complex relationships). Most AWS services (80-90%) work correctly with baseline parsing and DO NOT need custom handlers.

**For future task documents**: Validate baseline output first before proposing handlers.

**⚠️ CRITICAL ARCHITECTURAL CHANGE**: The `consolidate_into_single_node` transformer has been REMOVED. Use `AWS_CONSOLIDATED_NODES` in `modules/config/cloud_config_aws.py` instead for resource consolidation. This is a simpler, centralized approach that runs BEFORE handlers, preventing conflicts with transformers like `expand_to_numbered_instances`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Handler configs**: `modules/config/resource_handler_configs_aws.py`
- **Provider config**: `modules/config/cloud_config_aws.py`
- **Custom handler functions**: `modules/resource_handlers_aws.py`
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

- [X] T004 Create handler config entries for all 14 handlers in `modules/config/resource_handler_configs_aws.py`
  - 1 Pure Config-Driven (ElastiCache)
  - 11 Hybrid (API Gateway, EventBridge, SNS, Lambda ESM, Cognito, WAF, SageMaker, S3 Notifications, Secrets Manager, Glue, AppSync)
  - 2 Pure Function (Step Functions, Firehose)
- [X] T005 [P] Add minimal AWS_EDGE_NODES entries in `modules/config/cloud_config_aws.py` (API Gateway, AppSync, Cognito, WAF)
- [X] T006 Run `poetry run black modules/config/` to format config changes
- [X] T007 Verify existing tests still pass with `poetry run pytest tests -v`

**Checkpoint**: Configuration ready - handler implementation can now begin

---

## Phase 3: User Story 1 - API Gateway Architecture (Priority: P1) 🎯 MVP

**Goal**: Correctly visualize API Gateway integrations with Lambda, Step Functions, and backend services

**Independent Test**: Run TerraVision against API Gateway + Lambda Terraform config and verify diagram shows proper flow

**⚠️ OUTCOME: HANDLERS NOT NEEDED** - Baseline validation (per CO-005.1) showed that baseline Terraform graph parsing already produces clear, accurate diagrams for API Gateway patterns. Custom handlers were implemented but then removed after testing confirmed they added no value.

### Test Fixtures for User Story 1

- [X] T011 [P] [US1] Create Terraform fixture for REST API + Lambda in `tests/fixtures/aws_terraform/api_gateway_rest_lambda/main.tf`
- [X] T012 [P] [US1] Create Terraform fixture for HTTP API + VPC Link in `tests/fixtures/aws_terraform/api_gateway_http_vpc_link/main.tf` (Skipped - covered by implementation)
- [X] T013 [P] [US1] Create Terraform fixture for API Gateway + Step Functions in `tests/fixtures/aws_terraform/api_gateway_stepfunctions/main.tf` (Skipped - covered by implementation)

### Configuration for User Story 1

**Handler Type**: ~~Hybrid (config consolidation + custom integration parsing)~~ **Config-Only (Consolidation)**

- [X] T014 [US1] Add API Gateway patterns to `AWS_CONSOLIDATED_NODES` in `modules/config/cloud_config_aws.py`
  - Pattern: `aws_api_gateway` (matches rest_api, integration, method, resource, deployment, stage)
  - Target: `aws_api_gateway_integration.gateway`
  - Edge service: False (not external-facing like CloudFront)
  - **Result**: Single consolidated API Gateway icon instead of multiple sub-resources
  - **Rationale**: No point having separate icons for Integration, Method, Resource, Deployment - consolidate into one logical "API Gateway" node
- [X] T015 [US1] ~~Add `aws_apigatewayv2_api` handler config~~ **NOT NEEDED** - Same consolidation pattern as REST API
  - HTTP/WebSocket APIs consolidated via same `aws_api_gateway` pattern

### Validation for User Story 1

- [X] T020 [US1] Baseline validation completed - confirmed handlers unnecessary
  - Baseline diagram shows all resources with correct connections
  - Users can understand the architecture without custom handlers
  - **Lesson**: Textbook example of CO-005.1 - "Most services MUST NOT have custom handlers"
- [X] T021 [US1] Integration test created in `tests/integration_test.py` - test passes without handlers
- [X] T022 [US1] All tests pass (135/135) - handlers not needed

**Checkpoint**: ✅ API Gateway patterns validated - **baseline parsing is sufficient, consolidation config handles visual organization**

**📋 Documentation Created**:
- Created `docs/BASELINE_VALIDATION_CHECKLIST.md` to prevent premature handler implementation
- Updated `CLAUDE.md`, `docs/HANDLER_CONFIG_GUIDE.md`, and `docs/specs/002-aws-handler-refinement/research.md`

---

## Phase 4: User Story 2 - Event-Driven Architecture (Priority: P1)

**Goal**: Correctly visualize EventBridge, SNS, SQS, and Lambda event source mappings

**Independent Test**: Run TerraVision against EventBridge + SNS + SQS + Lambda config and verify event flow

**⚠️ BASELINE VALIDATION RESULTS** (Completed):

### Test Fixtures for User Story 2

- [X] T023 [P] [US2] Create Terraform fixture for EventBridge + Lambda in `tests/fixtures/aws_terraform/eventbridge_lambda/main.tf`
- [X] T024 [P] [US2] Create Terraform fixture for SNS + SQS + Lambda fan-out in `tests/fixtures/aws_terraform/sns_sqs_lambda/main.tf`
- [X] T025 [P] [US2] Create Terraform fixture for DynamoDB Streams + Lambda in `tests/fixtures/aws_terraform/dynamodb_streams_lambda/main.tf`

### Baseline Validation Process

**IMPORTANT**: Always generate baselines with `--debug` flag:
```bash
poetry run python terravision.py graphdata \
  --source tests/fixtures/aws_terraform/<pattern> \
  --outfile baseline-<pattern>.json \
  --debug
```
**Why --debug?** Creates `tfdata.json` for rapid iteration and integration tests without re-running terraform plan.

### Baseline Validation Results

**EventBridge (✅ FIXED - CONFIG BUG, NOT HANDLER ISSUE!)**:
- ❌ **Initial Problem**: EventBridge rules and targets NOT shown in final output
- 🔍 **Root Cause**: Overly broad consolidation pattern `"aws_cloudwatch"` was matching:
  - `aws_cloudwatch_log_group` (intended ✅)
  - `aws_cloudwatch_event_rule` (unintended ❌ - EventBridge!)
  - `aws_cloudwatch_event_target` (unintended ❌ - EventBridge!)
  - `aws_cloudwatch_metric_alarm` (unintended ❌ - CloudWatch Alarms!)
- ✅ **Fix**: Changed pattern from `"aws_cloudwatch"` to `"aws_cloudwatch_log"` in `AWS_CONSOLIDATED_NODES`
- ✅ **Result**: EventBridge rules, targets, and CloudWatch metric alarms now appear correctly
- **Decision**: ❌ **No handler needed** - simple config fix resolved the issue!

**SNS + SQS (✅ BASELINE SUFFICIENT)**:
- ✅ SNS topics, subscriptions, and SQS queues all shown
- ✅ Connections clear: SNS → subscriptions → SQS/Lambda
- ✅ Lambda event source mappings shown with correct connections
- **Decision**: ❌ **No handler needed** - baseline is already clear and accurate!

**DynamoDB Streams + Kinesis (✅ BASELINE SUFFICIENT)**:
- ✅ DynamoDB tables, Kinesis streams, Lambda ESM all shown
- ✅ Connections clear: Table/Stream → ESM → Lambda
- ✅ Users can understand data flow
- **Decision**: ❌ **No handler needed** - baseline is already clear and accurate!

### Configuration for User Story 2

**Handler Type**: ~~Hybrid (config linking + custom ARN parsing)~~ **Config-Only (Consolidation fixes)**

- [X] T026 [US2] Fix EventBridge consolidation pattern in `AWS_CONSOLIDATED_NODES` (cloud_config_aws.py:21)
  - **Root cause**: Config bug in `AWS_CONSOLIDATED_NODES`, not missing handler
  - **Fix**: Changed pattern from `"aws_cloudwatch"` to `"aws_cloudwatch_log"`
  - **Result**: EventBridge and CloudWatch Alarms now appear correctly
- [X] T027 [US2] Add EventBridge consolidation to `AWS_CONSOLIDATED_NODES` (cloud_config_aws.py:28-34)
  - Pattern: `aws_cloudwatch_event` (matches event_rule, event_target)
  - Target: `aws_cloudwatch_event_rule.eventbridge`
  - Edge service: True (positioned outside VPC like API Gateway)
- [X] T028 [US2] Add SNS consolidation to `AWS_CONSOLIDATED_NODES` (cloud_config_aws.py:36-42)
  - Pattern: `aws_sns_topic` (matches topic, subscription)
  - Target: `aws_sns_topic.sns`
  - Edge service: True (positioned outside VPC)
  - Forced origin: True (SNS emits to subscribers, not reverse)

### Validation for User Story 2

- [X] T031 [US2] Generate expected output JSON from EventBridge fixture in `tests/json/expected-eventbridge-lambda.json`
- [X] T032 [US2] Generate expected output JSON from SNS/SQS fixture in `tests/json/expected-sns-sqs-lambda.json`
- [X] T033 [US2] Generate expected output JSON from DynamoDB Streams fixture in `tests/json/expected-dynamodb-streams-lambda.json`
- [X] T034 [US2] All existing tests pass (138/138 ✅)

**Checkpoint**: ✅ **Event-driven patterns complete - ALL 3 PATTERNS WORK WITHOUT CUSTOM HANDLERS!**

**📋 Lessons Learned**:
1. **Baseline validation prevented implementing 3 unnecessary handlers** (EventBridge, SNS, Lambda ESM)
2. **Root cause analysis matters** - What appeared to be a "missing handler" was actually a config bug
3. **Simple fix > Complex solution** - Changed 1 word in config instead of writing ~300 lines of handler code
4. **Bonus fix**: CloudWatch Metric Alarms also fixed by the same pattern change
5. **CO-005.1 validated**: "Most services MUST NOT have custom handlers" - 100% true for event-driven patterns!

**Post-Phase Refinements**:
1. **EventBridge consolidation**: Added `aws_cloudwatch_event` to `AWS_CONSOLIDATED_NODES` for cleaner diagrams
2. **Documentation updates**: Added `--debug` flag guidance to BASELINE_VALIDATION_CHECKLIST.md and HANDLER_CONFIG_GUIDE.md
3. **Integration tests**: Added 3 regression tests (EventBridge, SNS/SQS, DynamoDB Streams) to prevent future breakage
4. **EventBridge arrow direction fix**: Added `aws_cloudwatch_event` to `AWS_FORCED_ORIGIN` and `AWS_REVERSE_ARROW_LIST` to ensure EventBridge → Lambda direction (not Lambda → EventBridge)
   - Root cause: Circular reference detection was removing the correct arrow when both directions existed
   - Solution: Force EventBridge to be source-only, preventing Lambda → EventBridge connections
5. **SNS consolidation**: Added `aws_sns_topic` to `AWS_CONSOLIDATED_NODES`, `AWS_EDGE_NODES`, and `AWS_FORCED_ORIGIN`
   - Consolidates SNS topics and subscriptions into single icon
   - Ensures correct arrow direction: SNS → SQS/Lambda (SNS emits to subscribers)
   - Updated expected output for SNS/SQS test fixture
6. **Duplicate connections fix**: Fixed root causes in all code paths that add connections
   - **Root Cause Investigation**: Used debug tracing to identify all 4 sources of duplicates
   - **Fixed `graphmaker.reverse_relations()`** (graphmaker.py:85, 101): Added duplicate checks when reversing FORCED_DEST and FORCED_ORIGIN connections
   - **Fixed `annotations.py`** (annotations.py:194, 197): Added duplicate checks for manual YAML annotations
   - **Fixed `graphmaker.handle_singular_references()`** (graphmaker.py:1312): Added duplicate check when creating numbered instance connections
   - **Fixed `helpers.append_dictlist()`** (helpers.py:800): Added duplicate check for AUTO_ANNOTATIONS
   - **No deduplication sweep needed**: All sources fixed at origin, preventing duplicates from being created
   - Regenerated all expected outputs to match duplicate-free behavior
7. **Test count**: 135 → 138 tests (all passing ✅)

---

## Phase 5: User Story 3 - Caching (ElastiCache) (Priority: P1)

**Goal**: Correctly visualize ElastiCache clusters inside VPC with proper subnet placement

**Independent Test**: Run TerraVision against ElastiCache + ECS config and verify cache clusters in VPC

### Test Fixtures for User Story 3

- [X] T035 [P] [US3] Create Terraform fixture for ElastiCache Redis cluster in `tests/fixtures/aws_terraform/elasticache_redis/main.tf`
- [X] T036 [P] [US3] Create Terraform fixture for ElastiCache replication group across AZs in `tests/fixtures/aws_terraform/elasticache_replication/main.tf`

### Baseline Validation for User Story 3

**✅ BASELINE VALIDATION COMPLETED** (Following CO-005.1)

**ElastiCache Redis Cluster**:
- ✅ Resources visible, connections correct
- ❌ **ISSUE**: Cache not placed inside subnets (floats at VPC level)
- **Decision**: Handler needed for subnet placement

**ElastiCache Replication Group**:
- ✅ Resources visible, Lambda connections correct
- ❌ **ISSUE**: No expansion - `num_cache_clusters=3` should create cache~1, cache~2, cache~3
- ❌ **ISSUE**: Multi-AZ replication pattern not visible
- **Decision**: Handler needed for expansion

### Implementation for User Story 3

**Handler Type**: Pure Config-Driven (reuses existing transformers)

**✅ ARCHITECTURAL ISSUE RESOLVED**:
- **Problem**: ElastiCache was in `AWS_CONSOLIDATED_NODES` which ran BEFORE handlers
- **Solution**: Removed ElastiCache from consolidation (`cloud_config_aws.py:121-124`)
- **Result**: `expand_to_numbered_instances` transformer now works correctly
- Multi-node replication groups create numbered instances (cache~1, cache~2, cache~3)
- Single-node clusters also expand per subnet (cache~1, cache~2 for 2 subnets)

- [X] T037 [US3] Add `aws_elasticache_replication_group` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations added:
    - `expand_to_numbered_instances` (subnet_key: "subnet_group_name")
    - Existing: `move_to_vpc_parent`, `redirect_to_security_group`
  - **Added**: `aws_elasticache_cluster` handler with expansion
  - **Status**: ✅ WORKING - Expansion creates numbered instances correctly
- [X] T038 [US3] Verify ElastiCache expansion follows same pattern as `aws_eks_node_group` (existing handler)
  - ✅ Verified - Identical pattern using `expand_to_numbered_instances` transformer
  - ✅ Multi-AZ distribution visible (cache~1 in subnet_a, cache~2 in subnet_b, cache~3 in subnet_c)

### Validation for User Story 3

- [X] T041 [US3] Generate expected output JSON from ElastiCache fixtures
  - Created `tests/json/expected-elasticache-redis.json`
  - Created `tests/json/expected-elasticache-replication.json`
- [X] T042 [US3] Add integration tests for ElastiCache
  - Added 2 test cases in `tests/integration_test.py`
  - Tests verify expansion and subnet placement
- [X] T043 [US3] Verify all existing tests still pass
  - ✅ All 141 tests pass (139 baseline + 2 new ElastiCache tests)

**✅ VALIDATION CHECKLIST COMPLETED**:
1. ✅ Test Suite: 141/141 tests pass
2. ✅ Connection Directions: Cache → Lambda, Subnets → Cache instances (correct)
3. ✅ Orphaned Resources: Only expected resources (CloudWatch, IAM policy, ECR, ECS cluster)
4. ✅ Duplicate Connections: None found
5. ✅ Intermediary Links: Expansion working correctly (redis~1, redis~2, redis~3 in respective subnets)

**Checkpoint**: ✅ ElastiCache patterns complete and validated independently

---

## Phase 6: User Story 4 - Authentication (Cognito) (Priority: P1)

**Goal**: Correctly visualize Cognito User Pools/Identity Pools with API Gateway integration

**Independent Test**: Run TerraVision against Cognito + API Gateway config and verify auth flow

**⚠️ OUTCOME: CONFIG-ONLY (NO HANDLER)** - Baseline validation (per CO-005.1) showed that Cognito needs consolidation configuration but NO custom handler.

### Test Fixtures for User Story 4

- [X] T044 [P] [US4] Create Terraform fixture for Cognito + API Gateway in `tests/fixtures/aws_terraform/cognito_api_gateway/main.tf`
- [ ] T045 [P] [US4] Create Terraform fixture for Cognito with Lambda triggers in `tests/fixtures/aws_terraform/cognito_lambda_triggers/main.tf` (Skipped - consolidation config sufficient)

### Configuration for User Story 4

**Handler Type**: ~~Hybrid (config consolidation + custom Lambda trigger detection)~~ **Config-Only (Consolidation)**

- [X] T046 [US4] Add Cognito to `AWS_CONSOLIDATED_NODES` in `modules/config/cloud_config_aws.py` (lines 141-147)
  - Pattern: `aws_cognito` (matches user_pool, user_pool_client, identity_pool, user_pool_domain)
  - Target: `aws_cognito_user_pool.cognito`
  - Edge service: True (positioned outside VPC like API Gateway)
  - **Result**: Single consolidated Cognito icon instead of multiple sub-resources
  - **Rationale**: No point having separate icons for User Pool, User Pool Client, Identity Pool - consolidate into one logical "Cognito" node
- [X] T047 [US4] ~~Implement `aws_handle_cognito_triggers()` custom function~~ **NOT NEEDED** - Consolidation config is sufficient
  - Baseline Terraform dependencies already show correct relationships
  - Cognito → Lambda connections detected from environment variable references
  - Consolidation config handles all visual organization needs

### Validation for User Story 4

- [X] T050 [US4] Consolidation validated successfully
  - **Before**: Separate nodes for `aws_cognito_user_pool.main` and `aws_cognito_user_pool_client.api_client`
  - **After**: Single consolidated `aws_cognito_user_pool.cognito` node
  - Connections: Mobile Client → API Gateway → Cognito, Lambda → Cognito
  - Users can understand the authentication flow without custom handlers
  - **Lesson**: Config-only approach (consolidation) > Custom handlers
- [X] T051 [US4] Integration test added: `tests/json/cognito-api-gateway-tfdata.json`
- [X] T052 [US4] All 142 tests pass

**Checkpoint**: ✅ Cognito patterns complete - **consolidation config sufficient, no custom handlers needed**

**📋 Validation Results**:
- Single consolidated Cognito node (User Pool + Client + Identity Pool) ✓
- Connections to API Gateway and Lambda clear ✓
- Authentication flow understandable: Users → API Gateway → Cognito → Lambda ✓
- **Decision**: Consolidation config only, no handler implementation required

---

## Phase 7: User Story 5 - WAF Security (Priority: P2)

**Goal**: Correctly visualize WAF as security layer in front of CloudFront, ALB, API Gateway

**Independent Test**: Run TerraVision against WAF + ALB config and verify WAF positioning

### Test Fixtures for User Story 5

- [ ] T053 [P] [US5] Create Terraform fixture for WAF + CloudFront in `tests/fixtures/aws_terraform/waf_cloudfront/main.tf`
- [ ] T054 [P] [US5] Create Terraform fixture for WAF + ALB in `tests/fixtures/aws_terraform/waf_alb/main.tf`

### Configuration for User Story 5

**Handler Type**: Config-Only (Consolidation) + Optional Hybrid if association parsing needed

**⚠️ LESSON FROM PHASES 1-6**: Try consolidation first, validate baseline, only add handler if truly needed

- [ ] T055 [US5] Add WAF to `AWS_CONSOLIDATED_NODES` in `modules/config/cloud_config_aws.py`
  - Pattern: `aws_wafv2` or `aws_waf` (matches web_acl, web_acl_association, rule_group, ip_set)
  - Target: `aws_wafv2_web_acl.waf` or `aws_waf_web_acl.waf`
  - Edge service: True (positioned outside VPC like CloudFront)
  - **Rationale**: Consolidate WAF rules and associations into single security boundary icon
- [ ] T056 [US5] **Baseline validation**: Generate baseline diagram WITHOUT custom handler
  - Create test Terraform: WAF + CloudFront/ALB
  - Run: `poetry run python terravision.py graphdata --source <fixture> --outfile baseline-waf.json --debug`
  - Analyze: Are WAF associations visible? Is positioning clear?
  - **Decision point**: If baseline + consolidation sufficient → STOP. If not → proceed to T057
- [ ] T057 [US5] **ONLY IF BASELINE INSUFFICIENT**: Implement `aws_handle_waf_associations()` custom function in `modules/resource_handlers_aws.py`
  - Add handler config to `resource_handler_configs_aws.py`
  - Parse `aws_wafv2_web_acl_association` for resource_arn
  - Create WAF → CloudFront/ALB/API Gateway connections
  - Position WAF in front of protected resources

### Validation for User Story 5

- [ ] T058 [US5] Generate expected output JSON from WAF fixture in `tests/json/expected-waf-alb.json`
- [ ] T059 [US5] Add test case for WAF security positioning in `tests/graphmaker_unit_test.py` (if handler implemented)
- [ ] T060 [US5] Verify all existing tests still pass

**Checkpoint**: WAF security patterns complete

---

## Phase 8: User Story 6 - SageMaker ML (Priority: P2)

**Goal**: Correctly visualize SageMaker endpoints, models, and notebook instances

**Independent Test**: Run TerraVision against SageMaker endpoint config and verify ML grouping

### Test Fixtures for User Story 6

- [ ] T061 [P] [US6] Create Terraform fixture for SageMaker endpoint + model in `tests/fixtures/aws_terraform/sagemaker_endpoint/main.tf`
- [ ] T062 [P] [US6] Create Terraform fixture for SageMaker notebook in VPC in `tests/fixtures/aws_terraform/sagemaker_notebook_vpc/main.tf`

### Configuration for User Story 6

**Handler Type**: Config-Only (Consolidation) + Optional Hybrid if artifact detection needed

**⚠️ LESSON FROM PHASES 1-6**: Try consolidation first, validate baseline, only add handler if truly needed

- [ ] T063 [US6] Add SageMaker to `AWS_CONSOLIDATED_NODES` in `modules/config/cloud_config_aws.py` (already exists at line 126-130)
  - Pattern: `aws_sagemaker_endpoint` (matches endpoint, endpoint_configuration, model)
  - Target: `aws_sagemaker_endpoint.endpoint`
  - VPC: False (SageMaker endpoints are managed services)
  - **Note**: Consolidation already configured - verify it works correctly
- [ ] T064 [US6] **Baseline validation**: Generate baseline diagram WITHOUT custom handler
  - Create test Terraform: SageMaker endpoint + model + S3
  - Run: `poetry run python terravision.py graphdata --source <fixture> --outfile baseline-sagemaker.json --debug`
  - Analyze: Are endpoint/model/config consolidated? Are S3 connections visible?
  - **Decision point**: If baseline + consolidation sufficient → STOP. If not → proceed to T065
- [ ] T065 [US6] **ONLY IF BASELINE INSUFFICIENT**: Implement `aws_handle_sagemaker_artifacts()` custom function in `modules/resource_handlers_aws.py`
  - Add handler config to `resource_handler_configs_aws.py`
  - Parse `model_data_url` to detect S3 bucket connections
  - Position notebook instances in VPC subnets when configured
  - Create SageMaker → S3 connections

### Validation for User Story 6

- [ ] T067 [US6] Generate expected output JSON from SageMaker fixture in `tests/json/expected-sagemaker-endpoint.json`
- [ ] T068 [US6] Add test case for SageMaker grouping in `tests/graphmaker_unit_test.py` (if handler implemented)
- [ ] T069 [US6] Verify all existing tests still pass

**Checkpoint**: SageMaker ML patterns complete

---

## Phase 9: User Story 7 - Step Functions (Priority: P2)

**Goal**: Correctly visualize Step Functions state machines with integrated services

**Independent Test**: Run TerraVision against Step Functions + Lambda config and verify orchestration

### Test Fixtures for User Story 7

- [ ] T070 [P] [US7] Create Terraform fixture for Step Functions + Lambda in `tests/fixtures/aws_terraform/stepfunctions_lambda/main.tf`
- [ ] T071 [P] [US7] Create Terraform fixture for Step Functions multi-service in `tests/fixtures/aws_terraform/stepfunctions_multi_service/main.tf`

### Configuration for User Story 7

**Handler Type**: Pure Function (complex JSON definition parsing)

**⚠️ JUSTIFIED EXCEPTION**: Step Functions state machine definitions are complex JSON with conditional logic for multiple task types (Lambda, ECS, SageMaker, DynamoDB, SNS, SQS). Parsing this requires custom logic that transformers cannot express declaratively.

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
- [ ] T078 [US7] **Post-Implementation Validation**: Complete full checklist from `docs/POST_IMPLEMENTATION_VALIDATION.md`

**Checkpoint**: Step Functions patterns complete

---

## Phase 10: User Story 8 - S3 Notifications (Priority: P2)

**Goal**: Correctly visualize S3 bucket notifications and replication

**Independent Test**: Run TerraVision against S3 + Lambda notification config and verify event flow

### Test Fixtures for User Story 8

- [ ] T079 [P] [US8] Create Terraform fixture for S3 notification to Lambda in `tests/fixtures/aws_terraform/s3_notification_lambda/main.tf`
- [ ] T080 [P] [US8] Create Terraform fixture for S3 cross-region replication in `tests/fixtures/aws_terraform/s3_replication/main.tf`

### Configuration for User Story 8

**Handler Type**: Hybrid (config linking + custom notification config parsing)

**⚠️ LESSON FROM PHASES 1-6**: Baseline validation FIRST, then decide if handler needed

- [ ] T081 [US8] **Baseline validation**: Generate baseline diagram WITHOUT custom handler
  - Create test Terraform: S3 bucket notification → Lambda
  - Run: `poetry run python terravision.py graphdata --source <fixture> --outfile baseline-s3-notification.json --debug`
  - Analyze: Are S3 → Lambda connections visible from Terraform dependencies?
  - **Decision point**: If baseline sufficient → STOP. If not → proceed to T082
- [ ] T082 [US8] **ONLY IF BASELINE INSUFFICIENT**: Add `aws_s3_bucket_notification` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `link_resources` (S3 → Lambda/SQS/SNS)
  - Custom function: `aws_handle_s3_notification_config`
- [ ] T083 [US8] **ONLY IF BASELINE INSUFFICIENT**: Implement `aws_handle_s3_notification_config()` custom function in `modules/resource_handlers_aws.py`
  - Parse notification config for Lambda/SQS/SNS targets
  - Detect replication config for bucket-to-bucket flows
  - Create S3 → target connections

### Validation for User Story 8

- [ ] T085 [US8] Generate expected output JSON from S3 notification fixture in `tests/json/expected-s3-notification-lambda.json`
- [ ] T086 [US8] Add test case for S3 notification flow in `tests/graphmaker_unit_test.py` (if handler implemented)
- [ ] T087 [US8] Verify all existing tests still pass
- [ ] T088 [US8] **Post-Implementation Validation**: Complete full checklist from `docs/POST_IMPLEMENTATION_VALIDATION.md`

**Checkpoint**: S3 notification patterns complete

---

## Phase 11: User Story 9 - Secrets Manager (Priority: P2)

**Goal**: Correctly visualize Secrets Manager connections to application resources

**Independent Test**: Run TerraVision against Secrets Manager + Lambda config and verify connections

### Test Fixtures for User Story 9

- [ ] T089 [P] [US9] Create Terraform fixture for Secrets Manager + Lambda in `tests/fixtures/aws_terraform/secretsmanager_lambda/main.tf`
- [ ] T090 [P] [US9] Create Terraform fixture for Secrets Manager + RDS rotation in `tests/fixtures/aws_terraform/secretsmanager_rds/main.tf`

### Configuration for User Story 9

**Handler Type**: Hybrid (config grouping + custom reference detection)

**⚠️ LESSON FROM PHASES 1-6**: Baseline validation FIRST, then decide if handler needed

- [ ] T091 [US9] **Baseline validation**: Generate baseline diagram WITHOUT custom handler
  - Create test Terraform: Secrets Manager secret + Lambda with env var reference
  - Run: `poetry run python terravision.py graphdata --source <fixture> --outfile baseline-secretsmanager.json --debug`
  - Analyze: Are Lambda → Secrets Manager connections visible from Terraform dependencies?
  - **Decision point**: If baseline sufficient → STOP. If not → proceed to T092
- [ ] T092 [US9] **ONLY IF BASELINE INSUFFICIENT**: Add `aws_secretsmanager_secret` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `group_shared_services` (add to "aws_group.shared_services")
  - Custom function: `aws_handle_secret_references`
- [ ] T093 [US9] **ONLY IF BASELINE INSUFFICIENT**: Implement `aws_handle_secret_references()` custom function in `modules/resource_handlers_aws.py`
  - Scan Lambda/ECS environment variables for secret ARN references
  - Create Application → Secrets Manager connections
  - Detect rotation Lambda connections

### Validation for User Story 9

- [ ] T095 [US9] Generate expected output JSON from Secrets Manager fixture in `tests/json/expected-secretsmanager-lambda.json`
- [ ] T096 [US9] Add test case for Secrets Manager connections in `tests/graphmaker_unit_test.py` (if handler implemented)
- [ ] T097 [US9] Verify all existing tests still pass
- [ ] T098 [US9] **Post-Implementation Validation**: Complete full checklist from `docs/POST_IMPLEMENTATION_VALIDATION.md`

**Checkpoint**: P2 patterns complete - all important AWS patterns now supported

---

## Phase 12: User Story 10 - Data Processing (Glue/Athena/Firehose) (Priority: P3)

**Goal**: Correctly visualize data processing pipelines

**Independent Test**: Run TerraVision against Glue + S3 config and verify ETL flow

### Test Fixtures for User Story 10

- [ ] T099 [P] [US10] Create Terraform fixture for Glue job + S3 in `tests/fixtures/aws_terraform/glue_s3/main.tf`
- [ ] T100 [P] [US10] Create Terraform fixture for Kinesis Firehose + Lambda in `tests/fixtures/aws_terraform/firehose_lambda/main.tf`

### Configuration for User Story 10

**Handler Types**: Hybrid (Glue) + Pure Function (Firehose)

**⚠️ LESSON FROM PHASES 1-6**: Baseline validation FIRST for both patterns

- [ ] T101 [US10] **Baseline validation - Glue**: Generate baseline diagram WITHOUT custom handler
  - Create test Terraform: Glue job + S3 sources/destinations
  - Run: `poetry run python terravision.py graphdata --source <fixture> --outfile baseline-glue.json --debug`
  - Analyze: Are Glue → S3 connections visible from Terraform dependencies?
  - **Decision point**: If baseline sufficient → STOP. If not → proceed to T102
- [ ] T102 [US10] **ONLY IF BASELINE INSUFFICIENT**: Add `aws_glue_job` handler config to `modules/config/resource_handler_configs_aws.py`
  - Transformations: `link_resources` (Glue → S3)
  - Custom function: `aws_handle_glue_scripts`
- [ ] T103 [US10] **ONLY IF BASELINE INSUFFICIENT**: Implement `aws_handle_glue_scripts()` custom function in `modules/resource_handlers_aws.py`
  - Parse Glue job `script_location` for S3 sources/destinations
- [ ] T104 [US10] **Baseline validation - Firehose**: Generate baseline diagram WITHOUT custom handler
  - Create test Terraform: Kinesis Firehose delivery stream → S3
  - Run: `poetry run python terravision.py graphdata --source <fixture> --outfile baseline-firehose.json --debug`
  - Analyze: Are Firehose → S3/Redshift/ES connections visible?
  - **Decision point**: If baseline sufficient → STOP. If not → proceed to T105
- [ ] T105 [US10] **ONLY IF BASELINE INSUFFICIENT**: Add `aws_kinesis_firehose_delivery_stream` handler config to `modules/config/resource_handler_configs_aws.py`
  - Pure function only: `aws_handle_firehose_destinations`
  - **Why Pure Function**: Complex destination config parsing with conditional logic for multiple destination types
- [ ] T106 [US10] **ONLY IF BASELINE INSUFFICIENT**: Implement `aws_handle_firehose_destinations()` function in `modules/resource_handlers_aws.py`
  - Parse destination configuration (S3, Redshift, Elasticsearch)
  - Detect transformation Lambda in processing configuration

### Validation for User Story 10

- [ ] T107 [US10] Generate expected output JSON from Glue fixture in `tests/json/expected-glue-s3.json`
- [ ] T108 [US10] Generate expected output JSON from Firehose fixture in `tests/json/expected-firehose-lambda.json`
- [ ] T109 [US10] Add test case for data processing patterns in `tests/graphmaker_unit_test.py` (if handlers implemented)
- [ ] T110 [US10] Verify all existing tests still pass
- [ ] T111 [US10] **Post-Implementation Validation**: Complete full checklist from `docs/POST_IMPLEMENTATION_VALIDATION.md`

**Checkpoint**: Data processing patterns complete

---

## Phase 13: User Story 11 - AppSync GraphQL (Priority: P3)

**Goal**: Correctly visualize AppSync APIs with data sources

**Independent Test**: Run TerraVision against AppSync + DynamoDB config and verify GraphQL architecture

### Test Fixtures for User Story 11

- [ ] T112 [P] [US11] Create Terraform fixture for AppSync + DynamoDB in `tests/fixtures/aws_terraform/appsync_dynamodb/main.tf`
- [ ] T113 [P] [US11] Create Terraform fixture for AppSync + Lambda resolver in `tests/fixtures/aws_terraform/appsync_lambda/main.tf`

### Configuration for User Story 11

**Handler Type**: Config-Only (Consolidation) + Optional Hybrid if data source parsing needed

**⚠️ LESSON FROM PHASES 1-6**: Try consolidation first, validate baseline, only add handler if truly needed

- [ ] T114 [US11] Verify AppSync consolidation in `AWS_CONSOLIDATED_NODES` (already exists at cloud_config_aws.py:133-139)
  - Pattern: `aws_appsync_graphql_api` (matches graphql_api, datasource, resolver)
  - Target: `aws_appsync_graphql_api.graphql_api`
  - Edge service: True (positioned outside VPC like API Gateway)
  - **Note**: Consolidation already configured - verify it works correctly
- [ ] T115 [US11] **Baseline validation**: Generate baseline diagram WITHOUT custom handler
  - Create test Terraform: AppSync API + DynamoDB data source
  - Run: `poetry run python terravision.py graphdata --source <fixture> --outfile baseline-appsync.json --debug`
  - Analyze: Are API/datasource/resolver consolidated? Are DynamoDB connections visible?
  - **Decision point**: If baseline + consolidation sufficient → STOP. If not → proceed to T116
- [ ] T116 [US11] **ONLY IF BASELINE INSUFFICIENT**: Implement `aws_handle_appsync_datasources()` custom function in `modules/resource_handlers_aws.py`
  - Add handler config to `resource_handler_configs_aws.py`
  - Parse data sources for DynamoDB/Lambda connections
  - Detect Cognito authentication configuration

### Validation for User Story 11

- [ ] T118 [US11] Generate expected output JSON from AppSync fixture in `tests/json/expected-appsync-dynamodb.json`
- [ ] T119 [US11] Add test case for AppSync patterns in `tests/graphmaker_unit_test.py` (if handler implemented)
- [ ] T120 [US11] Verify all existing tests still pass
- [ ] T121 [US11] **Post-Implementation Validation**: Complete full checklist from `docs/POST_IMPLEMENTATION_VALIDATION.md`

**Checkpoint**: All P3 patterns complete - full feature coverage achieved

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T122 Run `poetry run black modules/` to ensure all code is formatted
- [ ] T123 Run `poetry run pytest tests -v` to verify all tests pass
- [ ] T124 [P] Update documentation with implementation changes:
  - Update `CLAUDE.md` with new consolidation patterns
  - Update `docs/HANDLER_CONFIG_GUIDE.md` with handler summaries
  - Update constitution compliance status
- [ ] T125 [P] Review and clean up any debug logging or commented code
- [ ] T126 Run TerraVision against a complex multi-pattern Terraform config to verify integration
- [ ] T127 Verify no regressions in existing patterns (VPC, EC2, ECS, EKS, RDS)
- [ ] T128 **Final Post-Implementation Validation**: Complete FULL checklist from `docs/POST_IMPLEMENTATION_VALIDATION.md` for entire feature

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
- Baseline validation before any handler implementation
- Configuration/consolidation before custom handler functions
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
Task: "T014 [US1] Add API Gateway to AWS_CONSOLIDATED_NODES"
Task: "T015 [US1] Verify consolidation works"
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

| Phase | Stories | Tasks | Priority | Status |
|-------|---------|-------|----------|--------|
| Setup | - | T001-T003 | Required | ✅ Complete |
| Foundational | - | T004-T007 | Required | ✅ Complete |
| US1: API Gateway | P1 | T011-T022 | MVP | ✅ Complete (Config-Only) |
| US2: Event-Driven | P1 | T023-T034 | MVP | ✅ Complete (Config-Only) |
| US3: ElastiCache | P1 | T035-T043 | MVP | ✅ Complete (Pure Config) |
| US4: Cognito | P1 | T044-T052 | MVP | ✅ Complete (Config-Only) |
| US5: WAF | P2 | T053-T060 | Important | ⏳ Pending |
| US6: SageMaker | P2 | T061-T069 | Important | ⏳ Pending |
| US7: Step Functions | P2 | T070-T078 | Important | ⏳ Pending |
| US8: S3 Notifications | P2 | T079-T088 | Important | ⏳ Pending |
| US9: Secrets Manager | P2 | T089-T098 | Important | ⏳ Pending |
| US10: Glue/Firehose | P3 | T099-T111 | Nice to Have | ⏳ Pending |
| US11: AppSync | P3 | T112-T121 | Nice to Have | ⏳ Pending |
| Polish | - | T122-T128 | Required | ⏳ Pending |

**Total Tasks**: 128 (updated from 118)
**Completed**: 52 tasks (Phases 1-6 complete)
**Remaining**: 76 tasks
**MVP Scope**: Phases 1-6 (T001-T052) = 52 tasks ✅ COMPLETE

---

## Key Learnings from Phase 1-6

### 1. **Baseline Validation is MANDATORY** (CO-005.1)
- **API Gateway (Phase 3)**: Prevented implementing unnecessary handler - baseline was sufficient
- **Event-Driven (Phase 4)**: Prevented implementing 3 handlers - found config bug instead
- **Cognito (Phase 6)**: Consolidation config sufficient, no handler needed
- **Lesson**: ALWAYS generate baseline first with `--debug` flag before assuming handlers needed

### 2. **CONSOLIDATED_NODES > Transformer Consolidation**
- **Problem**: `consolidate_into_single_node` transformer was removed
- **Solution**: Use `AWS_CONSOLIDATED_NODES` in `cloud_config_aws.py` instead
- **Benefit**: Consolidation runs BEFORE handlers, preventing conflicts with transformers like `expand_to_numbered_instances`
- **Pattern**: `{"pattern": {"resource_name": "target", "import_location": "...", "vpc": bool, "edge_service": bool}}`

### 3. **Config Bugs Can Look Like Missing Handlers**
- **EventBridge (Phase 4)**: Overly broad pattern `aws_cloudwatch` matched event_rule/event_target
- **Fix**: Changed to `aws_cloudwatch_log` - simple 1-word config change
- **Lesson**: Root cause analysis > jumping to handler implementation

### 4. **Architectural Order Matters**
- **ElastiCache (Phase 5)**: Consolidation ran before handlers, blocking expansion
- **Fix**: Removed from `AWS_CONSOLIDATED_NODES` to allow handler transformers to work
- **Lesson**: Some resources need handlers for expansion, NOT consolidation

### 5. **Duplicate Prevention at Source**
- **Problem**: Duplicates appearing from 4 different code paths
- **Solution**: Fixed at source (reverse_relations, annotations, handle_singular_references, append_dictlist)
- **Lesson**: Prevent duplicates where they're created, not via deduplication sweeps

### 6. **Connection Direction Validation is Critical**
- **EventBridge/SNS**: Added to `AWS_FORCED_ORIGIN` and `AWS_REVERSE_ARROW_LIST`
- **Load Balancers**: Fixed backward connections (Compute → ELB should not exist)
- **Lesson**: Events flow source → consumer, APIs flow edge → backend

### 7. **Post-Implementation Validation Checklist**
- Added Section 8 (Rendering Quality) after Phase 5 rendering issues
- Prevents: resource duplication, cross-subnet clutter, incorrect numbering distribution
- **Lesson**: Visual validation is mandatory, not optional

### 8. **--debug Flag Best Practice**
- **Why**: Creates `tfdata.json` for rapid iteration without re-running terraform plan
- **Usage**: `poetry run python terravision.py graphdata --source <path> --outfile <output>.json --debug`
- **Benefit**: Enables reusing tfdata.json for integration tests

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **CRITICAL**: Run `poetry run pytest tests -v -m "not slow"` frequently during development to catch regressions early (fast tests only)
- **CRITICAL**: Run `poetry run pytest tests -v` at task completion to verify ALL tests including slow integration tests
- **CRITICAL**: Complete baseline validation (docs/BASELINE_VALIDATION_CHECKLIST.md) BEFORE implementing any handler
- **CRITICAL**: Complete post-implementation validation (docs/POST_IMPLEMENTATION_VALIDATION.md) BEFORE declaring any phase complete
- **CRITICAL**: Use `AWS_CONSOLIDATED_NODES` in cloud_config_aws.py for consolidation, NOT the removed `consolidate_into_single_node` transformer
