# OpenAPI Specification

This document provides information about the OpenAPI specification for the DICOM Gateway API.

## Specification File

The OpenAPI 3.0 specification is available in YAML format:

- **Location**: `docs/openapi.yaml`
- **Version**: OpenAPI 3.0.3
- **API Version**: 0.1.0

## Viewing the Specification

### Using Swagger UI

FastAPI automatically generates interactive API documentation using Swagger UI:

1. **Development**: http://localhost:8000/api/docs
2. **Production**: https://gateway.example.com/api/docs (if debug mode enabled)

### Using ReDoc

FastAPI also provides ReDoc documentation:

1. **Development**: http://localhost:8000/api/redoc
2. **Production**: https://gateway.example.com/api/redoc (if debug mode enabled)

### Using External Tools

You can use the OpenAPI YAML file with various tools:

#### Swagger Editor
1. Open https://editor.swagger.io/
2. Load `docs/openapi.yaml`
3. View and edit the specification

#### Postman
1. Import the OpenAPI specification
2. Generate a collection automatically
3. Test all endpoints

#### Insomnia
1. Import the OpenAPI specification
2. Generate requests for all endpoints
3. Test with authentication

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login and get access token
- `GET /api/v1/auth/me` - Get current user
- `GET /api/v1/auth/users` - List users (admin)
- `POST /api/v1/auth/users` - Create user (admin)
- `GET /api/v1/auth/users/{user_id}` - Get user (admin)
- `PUT /api/v1/auth/users/{user_id}` - Update user (admin/self)
- `DELETE /api/v1/auth/users/{user_id}` - Delete user (admin)
- `POST /api/v1/auth/password` - Change password

### Health
- `GET /api/v1/health` - Health check
- `GET /api/v1/health/live` - Liveness probe
- `GET /api/v1/health/ready` - Readiness probe

### Metrics
- `GET /api/v1/metrics` - Get system metrics
- `GET /api/v1/metrics/prometheus` - Prometheus metrics
- `GET /api/v1/metrics/queue` - Queue statistics
- `GET /api/v1/metrics/workers` - Worker statistics
- `GET /api/v1/metrics/scp` - SCP statistics
- `GET /api/v1/metrics/scu` - SCU statistics
- `GET /api/v1/metrics/studies` - Studies statistics
- `GET /api/v1/metrics/destinations` - Destinations statistics

### Studies
- `GET /api/v1/studies` - List studies
- `GET /api/v1/studies/{study_id}` - Get study by ID
- `GET /api/v1/studies/uid/{study_instance_uid}` - Get study by UID
- `POST /api/v1/studies/{study_id}/forward` - Forward study

### Destinations
- `GET /api/v1/destinations` - List destinations
- `POST /api/v1/destinations` - Create destination
- `GET /api/v1/destinations/{destination_id}` - Get destination
- `PUT /api/v1/destinations/{destination_id}` - Update destination
- `DELETE /api/v1/destinations/{destination_id}` - Delete destination

### Queues
- `GET /api/v1/queues/stats` - Get queue statistics
- `POST /api/v1/queues/retry` - Retry jobs
- `POST /api/v1/queues/replay/{study_instance_uid}` - Replay study

### Configuration
- `GET /api/v1/config` - Get configuration (admin)
- `POST /api/v1/config/reload` - Reload configuration (admin)
- `POST /api/v1/config/upload` - Upload configuration file (admin)
- `POST /api/v1/config/certificates/upload` - Upload certificate (admin)
- `POST /api/v1/config/certificates/letsencrypt/provision` - Provision Let's Encrypt (admin)
- `POST /api/v1/config/certificates/letsencrypt/renew` - Renew Let's Encrypt (admin)

### Audit
- `GET /api/v1/audit` - List audit logs
- `GET /api/v1/audit/{audit_id}` - Get audit log
- `GET /api/v1/audit/stats` - Get audit statistics

## Authentication

The API uses JWT Bearer token authentication:

1. Login using `POST /api/v1/auth/login` with username and password
2. Receive an access token in the response
3. Include the token in subsequent requests:
   ```
   Authorization: Bearer <access_token>
   ```

## Rate Limiting

The API implements rate limiting to prevent abuse:
- Default: 100 requests per minute per IP
- Authenticated users: 1000 requests per minute
- Admin users: 5000 requests per minute

## Error Responses

All errors follow a consistent format:

```json
{
  "error": "Error type",
  "detail": "Detailed error message"
}
```

Common HTTP status codes:
- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error
- `503` - Service Unavailable

## Code Generation

You can generate client code from the OpenAPI specification using various tools:

### OpenAPI Generator

```bash
# Generate Python client
openapi-generator generate -i docs/openapi.yaml -g python -o ./clients/python

# Generate JavaScript/TypeScript client
openapi-generator generate -i docs/openapi.yaml -g typescript-axios -o ./clients/typescript

# Generate Go client
openapi-generator generate -i docs/openapi.yaml -g go -o ./clients/go
```

### Swagger Codegen

```bash
# Generate Python client
swagger-codegen generate -i docs/openapi.yaml -l python -o ./clients/python

# Generate JavaScript client
swagger-codegen generate -i docs/openapi.yaml -l javascript -o ./clients/javascript
```

## Validation

The OpenAPI specification can be validated using:

```bash
# Using swagger-cli
swagger-cli validate docs/openapi.yaml

# Using openapi-spec-validator
openapi-spec-validator docs/openapi.yaml

# Using spectral (linting)
spectral lint docs/openapi.yaml
```

## Updating the Specification

When adding new endpoints or modifying existing ones:

1. Update the OpenAPI YAML file
2. Ensure FastAPI routes match the specification
3. Validate the specification
4. Update this documentation if needed
5. Regenerate client code if applicable

## Additional Resources

- [OpenAPI Specification](https://swagger.io/specification/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Swagger UI](https://swagger.io/tools/swagger-ui/)
- [ReDoc](https://github.com/Redocly/redoc)

