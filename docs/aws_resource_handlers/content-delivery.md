# Content Delivery

## Table of Contents

1. [CloudFront Distributions](#cloudfront-distributions)
   - [CloudFront to Load Balancer Linking](#cloudfront-to-load-balancer-linking)
   - [CloudFront Origin Resolution](#cloudfront-origin-resolution)
   - [CloudFront to ACM Certificate](#cloudfront-to-acm-certificate)

---

## CloudFront Distributions

### CloudFront to Load Balancer Linking

**What Happens**: When CloudFront distributions front load balancers, the connection is made direct.

**Transformation**:
```
Before:
Node → CloudFront Distribution
Node → Load Balancer

After:
CloudFront Distribution → Load Balancer
```

**Connections**:
- **Removed**: CloudFront from intermediate node
- **Removed**: Load balancer from non-group parent nodes
- **Added**: Direct CloudFront → Load Balancer connection

**Why**: CloudFront is the edge layer, load balancer is the origin. This shows the CDN → origin relationship.

### Implementation

```
FUNCTION link_cloudfront_to_load_balancers(tfdata):

    // Step 1: Find CloudFront distributions and load balancers
    cf_distros = FIND_RESOURCES_CONTAINING(graphdict, "aws_cloudfront")
    lbs = FIND_RESOURCES_CONTAINING(graphdict, "aws_lb.")

    // Step 2: Find nodes that connect to both CF and LB
    FOR EACH node IN graphdict:
        connections = graphdict[node]

        FOR EACH cf IN cf_distros:
            IF cf IN connections:
                // Node connects to CloudFront

                FOR EACH lb IN lbs:
                    IF node IN graphdict[lb]:
                        // Node also connects to LB
                        // Create direct CF → LB connection

                        lb_parents = GET_PARENTS(graphdict, lb)
                        ADD lb TO graphdict[cf]
                        REMOVE cf FROM graphdict[node]

                        // Remove LB from non-group parents
                        FOR EACH parent IN lb_parents:
                            parent_type = EXTRACT_TYPE(parent)
                            IF parent_type NOT IN GROUP_NODES:
                                REMOVE lb FROM graphdict[parent]

    RETURN tfdata
```

---

### CloudFront Origin Resolution

**What Happens**: CloudFront origin domain names are resolved to actual AWS resources.

**Process**:
1. Extract the `domain_name` from the origin configuration
2. Search all resource metadata for references to this domain
3. Replace the domain name with the Terraform resource reference

**Example**:
```
Origin domain: my-bucket.s3.amazonaws.com

Becomes: aws_s3_bucket.my_bucket
```

**Connections**:
- **Modified**: Origin metadata updated to reference resource instead of domain string

### Implementation

```
FUNCTION resolve_cloudfront_origins(tfdata):

    // Step 1: Find all CloudFront resources
    cf_resources = FIND_RESOURCES_CONTAINING(meta_data, "aws_cloudfront")

    FOR EACH cf_resource IN cf_resources:
        IF "origin" IN meta_data[cf_resource]:
            origin_config = meta_data[cf_resource]["origin"]

            // Parse origin (handle string, dict, or list formats)
            IF origin_config is string starting with "{" or "[":
                origin_config = PARSE_JSON(origin_config)
            IF origin_config is list:
                origin_config = origin_config[0]

            IF origin_config is dict:
                domain_name = origin_config["domain_name"]

                // Search all resources for this domain
                FOR EACH resource IN meta_data:
                    FOR EACH attribute IN meta_data[resource]:
                        IF domain_name IN attribute
                           AND domain_name does NOT start with "aws_"
                           AND resource does NOT start with "aws_cloudfront"
                           AND resource does NOT start with "aws_route53":
                            // Replace domain with resource reference
                            meta_data[cf_resource]["origin"] =
                                REPLACE(origin_config, domain_name, resource)

    RETURN tfdata
```

---

### CloudFront to ACM Certificate

**What Happens**: If a CloudFront distribution uses an ACM certificate, it's explicitly connected.

**Detection**: Checks `viewer_certificate.acm_certificate_arn` attribute

**Connections**:
- **Added**: CloudFront → ACM Certificate

**Why**: Shows SSL/TLS termination dependency.

### Implementation

```
FUNCTION link_cloudfront_to_acm(tfdata):

    // Find all CloudFront distributions
    cf_resources = FIND_RESOURCES_CONTAINING(meta_data, "aws_cloudfront")

    FOR EACH cf_resource IN cf_resources:
        // Check for ACM certificate in viewer_certificate
        IF "viewer_certificate" IN meta_data[cf_resource]:
            viewer_cert = meta_data[cf_resource]["viewer_certificate"]

            IF "acm_certificate_arn" IN viewer_cert:
                // Add connection to ACM certificate
                ADD "aws_acm_certificate.acm" TO graphdict[cf_resource]

    RETURN tfdata
```
