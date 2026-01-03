# CI/CD Integration Guide

## Overview

Integrate TerraVision into your CI/CD pipeline to automatically generate and update architecture diagrams whenever infrastructure code changes.

---

## Quick Start

### GitHub Actions

```yaml
# .github/workflows/architecture-diagrams.yml
name: Update Architecture Diagrams

on:
  push:
    branches: [main]
    paths: ['**.tf', '**.tfvars']

jobs:
  generate-diagrams:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install Dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y graphviz
          pip install -r requirements.txt
      
      - name: Generate Diagrams
        run: |
          python terravision.py draw --source ./terraform --format svg
          python terravision.py draw --source ./terraform --format png
      
      - name: Commit Diagrams
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add docs/images/*.{svg,png}
          git commit -m "Update architecture diagrams [skip ci]" || exit 0
          git push
```

---

## Platform-Specific Examples

### GitHub Actions

#### Basic Workflow

```yaml
name: Generate Architecture Diagrams

on:
  push:
    branches: [main, develop]
    paths:
      - '**.tf'
      - '**.tfvars'
  pull_request:
    paths:
      - '**.tf'
      - '**.tfvars'

jobs:
  diagrams:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install System Dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y graphviz
      
      - name: Install TerraVision
        run: |
          git clone https://github.com/patrickchugh/terravision.git
          cd terravision
          pip install -r requirements.txt
      
      - name: Generate Diagrams
        run: |
          cd terravision
          python terravision.py draw --source ../terraform --format svg --outfile ../docs/architecture
          python terravision.py draw --source ../terraform --format png --outfile ../docs/architecture
      
      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: architecture-diagrams
          path: docs/architecture.*
```

#### Multi-Environment Workflow

```yaml
name: Generate Multi-Environment Diagrams

on:
  push:
    branches: [main]

jobs:
  diagrams:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [dev, staging, prod]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install Dependencies
        run: |
          sudo apt-get install -y graphviz
          pip install -r requirements.txt
      
      - name: Generate Diagram for ${{ matrix.environment }}
        run: |
          python terravision.py draw \
            --source ./terraform \
            --varfile ./environments/${{ matrix.environment }}.tfvars \
            --format svg \
            --outfile docs/architecture-${{ matrix.environment }}
      
      - name: Upload Diagram
        uses: actions/upload-artifact@v3
        with:
          name: diagrams-${{ matrix.environment }}
          path: docs/architecture-${{ matrix.environment }}.svg
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - diagram

generate_diagrams:
  stage: diagram
  image: python:3.10
  
  before_script:
    - apt-get update
    - apt-get install -y graphviz git
    - pip install -r requirements.txt
  
  script:
    - python terravision.py draw --source ./terraform --format svg --outfile architecture
    - python terravision.py draw --source ./terraform --format png --outfile architecture
  
  artifacts:
    paths:
      - architecture.svg
      - architecture.png
    expire_in: 30 days
  
  only:
    changes:
      - "**/*.tf"
      - "**/*.tfvars"
```

### Jenkins

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    triggers {
        pollSCM('H/5 * * * *')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh '''
                    apt-get update
                    apt-get install -y graphviz python3-pip
                    pip3 install -r requirements.txt
                '''
            }
        }
        
        stage('Generate Diagrams') {
            steps {
                sh '''
                    python3 terravision.py draw \
                        --source ./terraform \
                        --format svg \
                        --outfile architecture-${BUILD_NUMBER}
                    
                    python3 terravision.py draw \
                        --source ./terraform \
                        --format png \
                        --outfile architecture-${BUILD_NUMBER}
                '''
            }
        }
        
        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'architecture-*.{svg,png}', fingerprint: true
            }
        }
        
        stage('Publish to Confluence') {
            steps {
                sh '''
                    curl -X PUT "https://your-domain.atlassian.net/wiki/rest/api/content/${CONFLUENCE_PAGE_ID}" \
                        -H "Authorization: Bearer ${CONFLUENCE_TOKEN}" \
                        -H "Content-Type: application/json" \
                        --data @confluence-update.json
                '''
            }
        }
    }
}
```

### Azure DevOps

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

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.10'
  displayName: 'Use Python 3.10'

- script: |
    sudo apt-get update
    sudo apt-get install -y graphviz
    pip install -r requirements.txt
  displayName: 'Install Dependencies'

- script: |
    python terravision.py draw --source ./terraform --format svg --outfile $(Build.ArtifactStagingDirectory)/architecture
    python terravision.py draw --source ./terraform --format png --outfile $(Build.ArtifactStagingDirectory)/architecture
  displayName: 'Generate Diagrams'

- task: PublishBuildArtifacts@1
  inputs:
    PathtoPublish: '$(Build.ArtifactStagingDirectory)'
    ArtifactName: 'architecture-diagrams'
  displayName: 'Publish Diagrams'
```

---

## Integration Patterns

### Pattern 1: Commit Diagrams to Repository

**Use when**: Diagrams should be version-controlled alongside code

```yaml
- name: Generate and Commit Diagrams
  run: |
    python terravision.py draw --source ./terraform --format svg --outfile docs/architecture
    git config user.name "CI Bot"
    git config user.email "ci@example.com"
    git add docs/architecture.svg
    git commit -m "Update architecture diagram [skip ci]" || exit 0
    git push
```

### Pattern 2: Upload as Artifacts

**Use when**: Diagrams are build artifacts, not source code

```yaml
- name: Upload Diagrams
  uses: actions/upload-artifact@v3
  with:
    name: architecture-diagrams
    path: |
      architecture.svg
      architecture.png
    retention-days: 90
```

### Pattern 3: Publish to Documentation Site

**Use when**: Diagrams are part of external documentation

```yaml
- name: Publish to ReadTheDocs
  run: |
    python terravision.py draw --source ./terraform --format svg --outfile docs/source/_static/architecture
    cd docs
    make html
    # Deploy to ReadTheDocs
```

### Pattern 4: Publish to Confluence

**Use when**: Using Confluence for documentation

```yaml
- name: Publish to Confluence
  env:
    CONFLUENCE_TOKEN: ${{ secrets.CONFLUENCE_TOKEN }}
  run: |
    python terravision.py draw --source ./terraform --format png --outfile architecture
    
    # Upload to Confluence
    curl -X POST \
      "https://your-domain.atlassian.net/wiki/rest/api/content/${PAGE_ID}/child/attachment" \
      -H "Authorization: Bearer ${CONFLUENCE_TOKEN}" \
      -H "X-Atlassian-Token: nocheck" \
      -F "file=@architecture.png"
```

---

## Advanced Configurations

### Multi-Region Diagrams

```yaml
- name: Generate Multi-Region Diagrams
  run: |
    for region in us-east-1 us-west-2 eu-west-1; do
      python terravision.py draw \
        --source ./terraform/${region} \
        --format svg \
        --outfile docs/architecture-${region}
    done
```

### Pull Request Comments

```yaml
name: PR Architecture Preview

on:
  pull_request:
    paths: ['**.tf']

jobs:
  preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup
        run: |
          sudo apt-get install -y graphviz
          pip install -r requirements.txt
      
      - name: Generate Diagram
        run: |
          python terravision.py draw --source ./terraform --format svg --outfile pr-diagram
      
      - name: Upload to Imgur
        id: imgur
        run: |
          RESPONSE=$(curl -X POST \
            -H "Authorization: Client-ID ${{ secrets.IMGUR_CLIENT_ID }}" \
            -F "image=@pr-diagram.svg" \
            https://api.imgur.com/3/image)
          echo "url=$(echo $RESPONSE | jq -r '.data.link')" >> $GITHUB_OUTPUT
      
      - name: Comment on PR
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Architecture Diagram Preview\n\n![Architecture](${{ steps.imgur.outputs.url }})`
            })
```

### Scheduled Updates

```yaml
name: Weekly Diagram Update

on:
  schedule:
    - cron: '0 0 * * 0'  # Every Sunday at midnight
  workflow_dispatch:  # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup
        run: |
          sudo apt-get install -y graphviz
          pip install -r requirements.txt
      
      - name: Generate Diagrams
        run: |
          python terravision.py draw --source ./terraform --format svg
          python terravision.py draw --source ./terraform --format png
      
      - name: Commit and Push
        run: |
          git config user.name "Weekly Update Bot"
          git add docs/architecture.*
          git commit -m "Weekly architecture diagram update" || exit 0
          git push
```

---

## Best Practices

### 1. Cache Dependencies

```yaml
- name: Cache Python Dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### 2. Only Run on Infrastructure Changes

```yaml
on:
  push:
    paths:
      - '**.tf'
      - '**.tfvars'
      - 'terravision.yml'  # Annotations file
```

### 3. Use Matrix for Multiple Environments

```yaml
strategy:
  matrix:
    environment: [dev, staging, prod]
    format: [svg, png, pdf]
```

### 4. Add Skip CI Tag

Prevent infinite loops when committing diagrams:

```bash
git commit -m "Update diagrams [skip ci]"
```

### 5. Use Secrets for Credentials

```yaml
env:
  CONFLUENCE_TOKEN: ${{ secrets.CONFLUENCE_TOKEN }}
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
```

---

## Troubleshooting

### Graphviz Not Found

```yaml
- name: Install Graphviz
  run: |
    sudo apt-get update
    sudo apt-get install -y graphviz
```

### Python Version Issues

```yaml
- name: Setup Python
  uses: actions/setup-python@v4
  with:
    python-version: '3.10'  # Specify exact version
```

### Git Push Failures

```yaml
- name: Configure Git
  run: |
    git config user.name "CI Bot"
    git config user.email "ci@example.com"
    git pull --rebase  # Avoid conflicts
```

---

## Next Steps

- **[Usage Guide](USAGE_GUIDE.md)** - Learn more TerraVision commands
- **[Annotations Guide](ANNOTATIONS.md)** - Customize diagrams in CI/CD
- **[Performance Tips](PERFORMANCE.md)** - Optimize for large projects
