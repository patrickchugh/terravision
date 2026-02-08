# CI/CD Integration Guide

Integrate TerraVision into your CI/CD pipeline to automatically generate and update architecture diagrams whenever infrastructure code changes.

---

## Installation Methods

TerraVision can be integrated into any CI/CD system using one of these methods:

| Method | Best For | Prerequisites |
|--------|----------|---------------|
| **GitHub Action** | GitHub workflows | Terraform on PATH |
| **Docker image** | GitLab, Jenkins, any container-based CI | None (self-contained) |
| **pip install** | Any CI with Python available | Python 3.10+, Graphviz, Terraform |
| **pip install + `--planfile`** | Diagram step without Terraform | Python 3.10+, Graphviz (no Terraform needed) |

---

## GitHub Actions

### Using the TerraVision Action (Recommended)

The [TerraVision Action](https://github.com/patrickchugh/terravision-action) handles installation of TerraVision and Graphviz automatically. You only need to provide Terraform.

```yaml
name: Update Architecture Diagrams

on:
  push:
    branches: [main]
    paths: ['**.tf', '**.tfvars']

jobs:
  generate-diagrams:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3

      - uses: patrickchugh/terravision-action@v1
        with:
          source: ./infrastructure
          outfile: docs/architecture
          format: both
```

#### Action Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `source` | Path to Terraform source directory | Yes | `.` |
| `outfile` | Output file path (without extension) | No | `architecture` |
| `format` | Output format: `png`, `svg`, or `both` | No | `png` |
| `varfile` | Path to `.tfvars` file | No | |
| `annotate` | Path to `terravision.yml` annotation file | No | |
| `planfile` | Pre-generated plan JSON from `terraform show -json` (skips Terraform requirement) | No | |
| `graphfile` | Pre-generated graph DOT from `terraform graph` (required with `planfile`) | No | |
| `extra-args` | Additional arguments for `terravision draw` | No | |

#### With Cloud Credentials

If Terraform needs to download remote modules or run `init` with backend access:

```yaml
steps:
  - uses: actions/checkout@v4

  - uses: hashicorp/setup-terraform@v3

  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/diagram-role
      aws-region: us-east-1

  - uses: patrickchugh/terravision-action@v1
    with:
      source: ./infrastructure
      format: svg
```

#### With Pre-Generated Plan (No Terraform in Diagram Step)

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: hashicorp/setup-terraform@v3

  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/terraform-role
      aws-region: us-east-1

  - name: Terraform Plan
    run: |
      cd infrastructure
      terraform init
      terraform plan -out=tfplan.bin
      terraform show -json tfplan.bin > plan.json
      terraform graph > graph.dot

  - uses: patrickchugh/terravision-action@v1
    with:
      source: ./infrastructure
      planfile: infrastructure/plan.json
      graphfile: infrastructure/graph.dot
      format: svg
```

#### Multi-Environment Matrix

```yaml
jobs:
  diagrams:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [dev, staging, prod]
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3

      - uses: patrickchugh/terravision-action@v1
        with:
          source: ./terraform
          outfile: docs/architecture-${{ matrix.environment }}
          varfile: environments/${{ matrix.environment }}.tfvars
          format: svg
```

#### Commit Diagrams Back to Repository

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: hashicorp/setup-terraform@v3

  - uses: patrickchugh/terravision-action@v1
    with:
      source: ./infrastructure
      outfile: docs/architecture
      format: both

  - name: Commit Diagrams
    run: |
      git config user.name "github-actions[bot]"
      git config user.email "github-actions[bot]@users.noreply.github.com"
      git add docs/architecture.*
      git commit -m "Update architecture diagrams [skip ci]" || exit 0
      git push
```

#### Pull Request Diagram Preview

```yaml
name: PR Architecture Preview

on:
  pull_request:
    paths: ['**.tf']

jobs:
  preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3

      - uses: patrickchugh/terravision-action@v1
        with:
          source: ./infrastructure
          outfile: pr-architecture
          format: png

      - name: Upload Diagram
        uses: actions/upload-artifact@v4
        with:
          name: architecture-diagram
          path: pr-architecture.png

      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '## Architecture Diagram\nSee the uploaded artifact for the updated diagram.'
            })
```

#### Using Docker Image Directly (No Prerequisites)

Alternatively, use the Docker image for a fully self-contained step:

```yaml
- name: Generate Diagram
  uses: docker://patrickchugh/terravision:latest
  with:
    args: draw --source ./infrastructure --outfile architecture --format png
```

---

## GitLab CI

### Using the Docker Image (Recommended)

The `patrickchugh/terravision` Docker image includes Terraform, Graphviz, and TerraVision — no additional setup required.

```yaml
# .gitlab-ci.yml
stages:
  - diagram

generate-diagram:
  stage: diagram
  image: patrickchugh/terravision:latest
  script:
    - terravision draw --source ./infrastructure --outfile architecture --format png
    - terravision draw --source ./infrastructure --outfile architecture --format svg
  artifacts:
    paths:
      - architecture.png
      - architecture.svg
    expire_in: 30 days
  rules:
    - changes:
        - "**/*.tf"
        - "**/*.tfvars"
```

### Multi-Environment

```yaml
generate-diagram:
  stage: diagram
  image: patrickchugh/terravision:latest
  parallel:
    matrix:
      - ENVIRONMENT: [dev, staging, prod]
  script:
    - terravision draw
        --source ./terraform
        --varfile environments/${ENVIRONMENT}.tfvars
        --outfile architecture-${ENVIRONMENT}
        --format svg
  artifacts:
    paths:
      - architecture-*.svg
```

### With Cloud Credentials

```yaml
generate-diagram:
  stage: diagram
  image: patrickchugh/terravision:latest
  variables:
    AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION: us-east-1
  script:
    - terravision draw --source ./infrastructure --outfile architecture --format png
  artifacts:
    paths:
      - architecture.png
```

### Commit Diagrams Back

```yaml
generate-diagram:
  stage: diagram
  image: patrickchugh/terravision:latest
  script:
    - terravision draw --source ./infrastructure --outfile docs/architecture --format png
    - git config user.name "GitLab CI"
    - git config user.email "ci@gitlab.com"
    - git add docs/architecture.png
    - git commit -m "Update architecture diagram [skip ci]" || true
    - git push "https://oauth2:${CI_JOB_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git" HEAD:${CI_COMMIT_BRANCH}
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      changes:
        - "**/*.tf"
```

### As a CI/CD Component

If you host on GitLab, you can create a reusable [CI/CD Component](https://docs.gitlab.com/ee/ci/components/):

```yaml
# In your component repo: templates/generate-diagram.yml
spec:
  inputs:
    source:
      default: '.'
    output:
      default: 'architecture'
    format:
      default: 'png'
    stage:
      default: 'build'

---

"generate-diagram":
  image: patrickchugh/terravision:latest
  stage: $[[ inputs.stage ]]
  script:
    - terravision draw --source $[[ inputs.source ]] --outfile $[[ inputs.output ]] --format $[[ inputs.format ]]
  artifacts:
    paths:
      - $[[ inputs.output ]].$[[ inputs.format ]]
```

Consumers include it as:

```yaml
include:
  - component: gitlab.com/your-org/terravision-component/generate-diagram@v1
    inputs:
      source: ./infrastructure
      format: svg
```

---

## Jenkins

### Docker Agent (Recommended)

```groovy
// Jenkinsfile
pipeline {
    agent {
        docker {
            image 'patrickchugh/terravision:latest'
        }
    }

    triggers {
        pollSCM('H/15 * * * *')
    }

    stages {
        stage('Generate Diagrams') {
            steps {
                sh '''
                    terravision draw \
                        --source ./infrastructure \
                        --outfile architecture \
                        --format png

                    terravision draw \
                        --source ./infrastructure \
                        --outfile architecture \
                        --format svg
                '''
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'architecture.*', fingerprint: true
            }
        }
    }
}
```

### Multi-Environment with Parameters

```groovy
pipeline {
    agent {
        docker {
            image 'patrickchugh/terravision:latest'
        }
    }

    parameters {
        choice(name: 'ENVIRONMENT', choices: ['dev', 'staging', 'prod'], description: 'Target environment')
    }

    stages {
        stage('Generate Diagram') {
            steps {
                sh """
                    terravision draw \
                        --source ./terraform \
                        --varfile environments/${params.ENVIRONMENT}.tfvars \
                        --outfile architecture-${params.ENVIRONMENT} \
                        --format png
                """
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: "architecture-${params.ENVIRONMENT}.png", fingerprint: true
            }
        }
    }
}
```

### Without Docker (pip install)

```groovy
pipeline {
    agent any

    stages {
        stage('Setup') {
            steps {
                sh '''
                    pip install terravision
                '''
            }
        }

        stage('Generate Diagrams') {
            steps {
                sh '''
                    terravision draw \
                        --source ./infrastructure \
                        --outfile architecture \
                        --format png
                '''
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'architecture.*', fingerprint: true
            }
        }
    }
}
```

**Note**: The non-Docker approach requires Python 3.10+, Graphviz, and Terraform pre-installed on the Jenkins agent.

---

## Azure DevOps

### Using Docker

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main
  paths:
    include:
      - '**/*.tf'
      - '**/*.tfvars'

pool:
  vmImage: 'ubuntu-latest'

container: patrickchugh/terravision:latest

steps:
- script: |
    terravision draw --source ./infrastructure --outfile $(Build.ArtifactStagingDirectory)/architecture --format png
    terravision draw --source ./infrastructure --outfile $(Build.ArtifactStagingDirectory)/architecture --format svg
  displayName: 'Generate Diagrams'

- task: PublishBuildArtifacts@1
  inputs:
    PathtoPublish: '$(Build.ArtifactStagingDirectory)'
    ArtifactName: 'architecture-diagrams'
  displayName: 'Publish Diagrams'
```

### Using pip install

```yaml
trigger:
  branches:
    include:
      - main
  paths:
    include:
      - '**/*.tf'

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.10'
  displayName: 'Use Python 3.10'

- task: TerraformInstaller@1
  inputs:
    terraformVersion: 'latest'
  displayName: 'Install Terraform'

- script: |
    sudo apt-get update -qq && sudo apt-get install -y -qq graphviz
    pip install terravision
  displayName: 'Install TerraVision'

- script: |
    terravision draw --source ./infrastructure --outfile $(Build.ArtifactStagingDirectory)/architecture --format png
  displayName: 'Generate Diagram'

- task: PublishBuildArtifacts@1
  inputs:
    PathtoPublish: '$(Build.ArtifactStagingDirectory)'
    ArtifactName: 'architecture-diagrams'
```

---

## Generic CI/CD (Any Platform)

For any CI/CD system, you have two options:

### Option 1: Docker (Recommended)

Run the Docker image with your source mounted:

```bash
docker run --rm \
  -v $(pwd):/project \
  patrickchugh/terravision:latest \
  draw --source ./infrastructure --outfile architecture --format png
```

This works in any CI system that supports Docker (CircleCI, Bitbucket Pipelines, Drone, etc.).

### Option 2: pip install

```bash
# Prerequisites: Python 3.10+, Graphviz, Terraform
pip install terravision
terravision draw --source ./infrastructure --outfile architecture --format png
```

### CircleCI Example

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  generate-diagram:
    docker:
      - image: patrickchugh/terravision:latest
    steps:
      - checkout
      - run:
          name: Generate Diagram
          command: terravision draw --source ./infrastructure --outfile architecture --format png
      - store_artifacts:
          path: architecture.png

workflows:
  diagram:
    jobs:
      - generate-diagram:
          filters:
            branches:
              only: main
```

### Bitbucket Pipelines Example

```yaml
# bitbucket-pipelines.yml
image: patrickchugh/terravision:latest

pipelines:
  branches:
    main:
      - step:
          name: Generate Architecture Diagram
          script:
            - terravision draw --source ./infrastructure --outfile architecture --format png
          artifacts:
            - architecture.png
```

---

## Pre-Generated Plan Mode (No Credentials in Diagram Step)

In many CI/CD setups, Terraform runs in a secured step with cloud credentials, while diagram generation should happen separately without credential access. The `--planfile` and `--graphfile` options enable this separation.

### How It Works

1. **Terraform step** (with credentials): Run `terraform plan`, export plan JSON and graph DOT
2. **Diagram step** (no credentials): Run `terravision` with the exported files

### GitHub Actions — Separate Jobs

```yaml
name: Infrastructure Diagrams

on:
  push:
    branches: [main]
    paths: ['**.tf', '**.tfvars']

jobs:
  terraform-plan:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/terraform-role
          aws-region: us-east-1

      - name: Terraform Plan
        run: |
          cd infrastructure
          terraform init
          terraform plan -out=tfplan.bin
          terraform show -json tfplan.bin > plan.json
          terraform graph > graph.dot

      - uses: actions/upload-artifact@v4
        with:
          name: terraform-outputs
          path: |
            infrastructure/plan.json
            infrastructure/graph.dot

  generate-diagram:
    runs-on: ubuntu-latest
    needs: terraform-plan
    steps:
      - uses: actions/checkout@v4

      - uses: actions/download-artifact@v4
        with:
          name: terraform-outputs
          path: infrastructure

      - name: Install Dependencies
        run: |
          sudo apt-get install -y graphviz
          pip install terravision

      - name: Generate Diagram
        run: |
          terravision draw \
            --planfile infrastructure/plan.json \
            --graphfile infrastructure/graph.dot \
            --source ./infrastructure \
            --format png

      - name: Commit Diagram
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add architecture.*
          git commit -m "Update architecture diagram [skip ci]" || exit 0
          git push
```

### GitLab CI — Separate Stages

```yaml
stages:
  - plan
  - diagram

terraform-plan:
  stage: plan
  image: hashicorp/terraform:latest
  variables:
    AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
  script:
    - cd infrastructure
    - terraform init
    - terraform plan -out=tfplan.bin
    - terraform show -json tfplan.bin > plan.json
    - terraform graph > graph.dot
  artifacts:
    paths:
      - infrastructure/plan.json
      - infrastructure/graph.dot
    expire_in: 1 hour

generate-diagram:
  stage: diagram
  image: patrickchugh/terravision:latest
  needs: [terraform-plan]
  script:
    - terravision draw
        --planfile infrastructure/plan.json
        --graphfile infrastructure/graph.dot
        --source ./infrastructure
        --outfile architecture
        --format png
  artifacts:
    paths:
      - architecture.png
    expire_in: 30 days
```

### Jenkins — Separate Stages

```groovy
pipeline {
    agent any

    stages {
        stage('Terraform Plan') {
            agent {
                docker { image 'hashicorp/terraform:latest' }
            }
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                  credentialsId: 'aws-creds']]) {
                    sh '''
                        cd infrastructure
                        terraform init
                        terraform plan -out=tfplan.bin
                        terraform show -json tfplan.bin > plan.json
                        terraform graph > graph.dot
                    '''
                }
                stash includes: 'infrastructure/plan.json,infrastructure/graph.dot', name: 'tf-outputs'
            }
        }

        stage('Generate Diagram') {
            agent {
                docker { image 'patrickchugh/terravision:latest' }
            }
            steps {
                unstash 'tf-outputs'
                sh '''
                    terravision draw \
                        --planfile infrastructure/plan.json \
                        --graphfile infrastructure/graph.dot \
                        --source ./infrastructure \
                        --format png
                '''
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'architecture.*', fingerprint: true
            }
        }
    }
}
```

### Azure DevOps — Separate Jobs

```yaml
trigger:
  branches:
    include: [main]
  paths:
    include: ['**/*.tf']

stages:
- stage: Plan
  jobs:
  - job: TerraformPlan
    pool:
      vmImage: 'ubuntu-latest'
    steps:
    - task: TerraformInstaller@1
      inputs:
        terraformVersion: 'latest'

    - script: |
        cd infrastructure
        terraform init
        terraform plan -out=tfplan.bin
        terraform show -json tfplan.bin > plan.json
        terraform graph > graph.dot
      displayName: 'Terraform Plan'

    - publish: infrastructure/plan.json
      artifact: plan-json
    - publish: infrastructure/graph.dot
      artifact: graph-dot

- stage: Diagram
  dependsOn: Plan
  jobs:
  - job: GenerateDiagram
    pool:
      vmImage: 'ubuntu-latest'
    container: patrickchugh/terravision:latest
    steps:
    - download: current
      artifact: plan-json
    - download: current
      artifact: graph-dot

    - script: |
        terravision draw \
          --planfile $(Pipeline.Workspace)/plan-json/plan.json \
          --graphfile $(Pipeline.Workspace)/graph-dot/graph.dot \
          --source ./infrastructure \
          --format png
      displayName: 'Generate Diagram'

    - publish: architecture.png
      artifact: architecture-diagram
```

---

## Integration Patterns

### Pattern 1: Commit Diagrams to Repository

Diagrams are version-controlled alongside code. Use `[skip ci]` to prevent infinite loops.

```bash
terravision draw --source ./infrastructure --outfile docs/architecture --format png
git add docs/architecture.png
git commit -m "Update architecture diagram [skip ci]" || exit 0
git push
```

### Pattern 2: Upload as Build Artifacts

Diagrams are ephemeral build outputs, not source code.

```bash
terravision draw --source ./infrastructure --outfile architecture --format png
# Use your CI's artifact upload mechanism
```

### Pattern 3: Publish to Documentation Site

```bash
terravision draw --source ./infrastructure --outfile docs/source/_static/architecture --format svg
# Trigger documentation build/deploy
```

### Pattern 4: Pre-Generated Plan Files

Separate Terraform execution from diagram generation for better security and flexibility:

```bash
# Step 1: In Terraform environment (with credentials)
terraform plan -out=tfplan.bin
terraform show -json tfplan.bin > plan.json
terraform graph > graph.dot

# Step 2: In diagram environment (no credentials needed)
terravision draw \
  --planfile plan.json \
  --graphfile graph.dot \
  --source ./infrastructure \
  --format png
```

This pattern is ideal when:
- Cloud credentials should not be shared with the diagram generation step
- Terraform runs in a different CI job, stage, or pipeline
- You want to archive plan files and regenerate diagrams later
- Diagram generation runs on a machine without Terraform installed

### Pattern 5: Multi-Region/Multi-Environment

```bash
for env in dev staging prod; do
  terravision draw \
    --source ./terraform \
    --varfile environments/${env}.tfvars \
    --outfile docs/architecture-${env} \
    --format svg
done
```

---

## Best Practices

### 1. Only Trigger on Infrastructure Changes

```yaml
# GitHub Actions
paths: ['**.tf', '**.tfvars', 'terravision.yml']

# GitLab CI
rules:
  - changes: ["**/*.tf", "**/*.tfvars"]
```

### 2. Use `[skip ci]` When Committing Diagrams

Prevent infinite CI loops when diagram commits trigger the pipeline:

```bash
git commit -m "Update architecture diagrams [skip ci]"
```

### 3. Cache pip Dependencies

```yaml
# GitHub Actions
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-terravision
```

### 4. Pin Versions

```yaml
# Pin TerraVision version
pip install terravision==X.Y.Z

# Pin Docker image tag
image: patrickchugh/terravision:1.0.0
```

### 5. Use Annotations for Customization

Add a `terravision.yml` file to customize diagrams without changing Terraform code:

```bash
terravision draw --source ./infrastructure --annotate terravision.yml --format png
```

See [Annotations Guide](ANNOTATIONS.md) for details.

---

## Troubleshooting

### Terraform init fails

The CI environment may not have access to remote module sources or backends. Ensure cloud credentials are configured before running TerraVision.

### Graphviz not found

If using `pip install` (not Docker), install Graphviz:

```bash
# Ubuntu/Debian
sudo apt-get install -y graphviz

# macOS
brew install graphviz

# Alpine
apk add graphviz
```

### Permission denied on git push

Configure the CI bot with appropriate permissions:

```yaml
# GitHub Actions - grant write permission
permissions:
  contents: write
```

### Large repositories timeout

For large Terraform codebases, increase timeout or generate diagrams for specific subdirectories:

```bash
terravision draw --source ./terraform/networking --outfile network-diagram --format png
terravision draw --source ./terraform/compute --outfile compute-diagram --format png
```

---

## Next Steps

- **[Usage Guide](USAGE_GUIDE.md)** - Learn more TerraVision commands and options
- **[Annotations Guide](ANNOTATIONS.md)** - Customize diagrams with YAML annotations
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
