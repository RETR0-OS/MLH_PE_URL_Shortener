# Deploy Guide

## Prerequisites

- Docker Engine 24+
- Docker Compose v2 or Docker Swarm

## Docker Compose (Development / Single Node)

```bash
# Build and start all services
docker compose up -d --build

# Verify health
curl http://localhost:5000/health
curl http://localhost:5000/health/ready

# Seed the database
docker compose exec app python scripts/seed.py

# View logs
docker compose logs -f app

# Scale app replicas
docker compose up -d --scale app=3

# Tear down
docker compose down -v
```

## Docker Swarm (Production)

### Initialize Swarm

```bash
docker swarm init
```

### Deploy the Stack

```bash
docker stack deploy -c docker-compose.yml urlshort
```

### Verify Deployment

```bash
docker service ls
docker service ps urlshort_app
curl http://localhost:80/health
```

### Scale Replicas

```bash
docker service scale urlshort_app=3
```

### Rolling Update

```bash
# Build and push new image
docker build -t app:v2 .

# Update the service (zero-downtime, start-first)
docker service update --image app:v2 urlshort_app
```

### Rollback

```bash
docker service update --rollback urlshort_app
```

### Secrets Management

```bash
# Create secrets
echo "postgres_password" | docker secret create db_password -
echo "redis_password" | docker secret create redis_password -

# Secrets are read from /run/secrets/ inside containers
```

### View Replica History

```bash
docker service ps urlshort_app --no-trunc
```

### Remove the Stack

```bash
docker stack rm urlshort
docker swarm leave --force
```

## Monitoring Access

After deployment:

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093
