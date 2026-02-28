# AWS Architecture Diagram

```mermaid
flowchart LR
    user[User / Browser]
    cf[CloudFront Distribution]
    oac[Origin Access Control]
    s3[S3 WebContentBucket]
    policy[S3 BucketPolicy]

    user -->|HTTPS| cf
    cf -->|SigV4 via OAC| oac
    oac --> s3
    policy -. allows s3:GetObject only .-> cf
```

## Components

- `CloudFrontDistribution`: Delivers web content over HTTPS and redirects HTTP to HTTPS.
- `OriginAccessControl`: Signs requests from CloudFront to S3 with SigV4.
- `WebContentBucket`: Private S3 bucket with encryption, versioning, and public access blocked.
- `BucketPolicy`: Allows read access only from the CloudFront distribution.

## Notes

- `index.html` is used as the default root object.
- `403` and `404` responses are mapped to `/index.html`.
- The template represents a private S3 origin behind CloudFront, not a public S3 website endpoint.
