# Makefile for Music Text Converter Project

.PHONY: up down logs clean build run-api run-media run-tts restart status

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
help:
	@echo "$(GREEN)Music Text Converter - Available Commands:$(NC)"
	@echo "$(YELLOW)make up$(NC)          - Build and start all services"
	@echo "$(YELLOW)make down$(NC)        - Stop all services"
	@echo "$(YELLOW)make restart$(NC)     - Restart all services"
	@echo "$(YELLOW)make logs$(NC)        - Show logs from all services"
	@echo "$(YELLOW)make clean$(NC)       - Clean up containers and volumes"
	@echo "$(YELLOW)make build$(NC)       - Build all Docker images"
	@echo "$(YELLOW)make run-api$(NC)     - Run only API Gateway"
	@echo "$(YELLOW)make run-media$(NC)   - Run only Media Processor"
	@echo "$(YELLOW)make run-tts$(NC)     - Run only Text-to-Speech"
	@echo "$(YELLOW)make status$(NC)      - Show service status"
	@echo "$(YELLOW)make test$(NC)        - Run tests"

# Build and start all services
up:
	@echo "$(GREEN)Starting all services...$(NC)"
	docker-compose up --build -d
	@echo "$(GREEN)All services started!$(NC)"
	@echo "$(YELLOW)API Gateway: http://localhost:8000$(NC)"
	@echo "$(YELLOW)Media Processor: http://localhost:8001$(NC)"
	@echo "$(YELLOW)Text-to-Speech: http://localhost:8002$(NC)"
	@echo "$(YELLOW)MinIO Console: http://localhost:9001$(NC)"

# Stop all services
down:
	@echo "$(RED)Stopping all services...$(NC)"
	docker-compose down
	@echo "$(RED)All services stopped!$(NC)"

# Restart all services
restart: down up

# Build all Docker images
build:
	@echo "$(GREEN)Building all Docker images...$(NC)"
	docker-compose build

# Show logs from all services
logs:
	@echo "$(GREEN)Showing logs from all services...$(NC)"
	docker-compose logs -f

# Show logs from specific service
logs-api:
	docker-compose logs -f api-gateway

logs-media:
	docker-compose logs -f media-processor

logs-tts:
	docker-compose logs -f text-to-speech

logs-db:
	docker-compose logs -f postgres

# Run only API Gateway
run-api:
	@echo "$(GREEN)Starting API Gateway...$(NC)"
	docker-compose up --build api-gateway

# Run only Media Processor
run-media:
	@echo "$(GREEN)Starting Media Processor...$(NC)"
	docker-compose up --build media-processor

# Run only Text-to-Speech service
run-tts:
	@echo "$(GREEN)Starting Text-to-Speech service...$(NC)"
	docker-compose up --build text-to-speech

# Show service status
status:
	@echo "$(GREEN)Service Status:$(NC)"
	docker-compose ps

# Clean up containers and volumes
clean:
	@echo "$(RED)Cleaning up containers and volumes...$(NC)"
	docker-compose down -v
	docker system prune -f
	@echo "$(RED)Cleanup completed!$(NC)"

# Clean up everything including images
clean-all:
	@echo "$(RED)Cleaning up everything...$(NC)"
	docker-compose down -v
	docker system prune -af
	@echo "$(RED)Full cleanup completed!$(NC)"

# Create temp directories
setup-dirs:
	@echo "$(GREEN)Creating necessary directories...$(NC)"
	mkdir -p temp_files
	mkdir -p logs
	@echo "$(GREEN)Directories created!$(NC)"

# Run development mode (with auto-reload)
dev:
	@echo "$(GREEN)Starting development mode...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Run tests
test:
	@echo "$(GREEN)Running tests...$(NC)"
	docker-compose exec api-gateway python -m pytest tests/ -v

# Database operations
db-migrate:
	@echo "$(GREEN)Running database migrations...$(NC)"
	docker-compose exec api-gateway python -c "from database import create_tables; create_tables()"

db-reset:
	@echo "$(RED)Resetting database...$(NC)"
	docker-compose exec postgres psql -U postgres -d music_txt_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Health check all services
health:
	@echo "$(GREEN)Checking service health...$(NC)"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "$(RED)API Gateway not responding$(NC)"
	@curl -s http://localhost:8001/health | python -m json.tool || echo "$(RED)Media Processor not responding$(NC)"
	@curl -s http://localhost:8002/health | python -m json.tool || echo "$(RED)Text-to-Speech not responding$(NC)"

# Monitor resources
monitor:
	@echo "$(GREEN)Monitoring container resources...$(NC)"
	docker stats

# Backup data
backup:
	@echo "$(GREEN)Creating backup...$(NC)"
	docker-compose exec postgres pg_dump -U postgres music_txt_db > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup completed!$(NC)"

# Interactive shell into services
shell-api:
	docker-compose exec api-gateway bash

shell-media:
	docker-compose exec media-processor bash

shell-tts:
	docker-compose exec text-to-speech bash

shell-db:
	docker-compose exec postgres psql -U postgres -d music_txt_db
