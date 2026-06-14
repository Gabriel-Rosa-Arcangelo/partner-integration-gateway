COMPOSE ?= docker compose

.PHONY: up down logs migrate test check

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

migrate:
	$(COMPOSE) exec web python manage.py migrate

test:
	$(COMPOSE) exec web python manage.py test

check:
	$(COMPOSE) exec web python manage.py check
