# E Commerce Flow Full Stack 

A full-stack e-commerce platform built with **FastAPI, PostgreSQL, Redis, SQLAlchemy, and JavaScript**. CommerceFlow provides JWT authentication, product and category management, shopping carts, concurrency-safe checkout, order management, inventory tracking, Redis/in-memory caching, and purchase-based product recommendations through a REST API and responsive web interface.

## Features

* JWT-based authentication
* User registration and login
* Product and category management
* Product search and filtering
* Shopping cart management
* Concurrency-safe transactional checkout
* Order management and order history
* Inventory tracking and audit logs
* Redis caching with in-memory fallback
* Purchase-based recommendations
* Responsive web interface
* REST API with Swagger/OpenAPI documentation
* SQLite for local development
* PostgreSQL and Redis with Docker
* Automated tests for authentication, checkout, and recommendations

## Tech Stack

**Backend**

* Python
* FastAPI
* SQLAlchemy
* Pydantic
* JWT

**Database**

* SQLite
* PostgreSQL

**Caching**

* Redis
* In-memory fallback

**Frontend**

* HTML
* CSS
* JavaScript

**Deployment**

* Docker
* Docker Compose
* Nginx

## Architecture


                    Browser
                       │
                       ▼
              Responsive Web UI
                       │
                       ▼
                FastAPI REST API
                       │
          ┌────────────┼────────────┐
          ▼            ▼               ▼
     SQLAlchemy      Redis       Business Logic
          │         Cache             │
          ▼                           ▼
   SQLite / PostgreSQL       Cart / Orders / Inventory
                                      │
                                      ▼
                              Recommendations


For local development, SQLite is used by default and Redis is optional. If Redis is unavailable, CommerceFlow automatically falls back to an in-memory cache.

When running with Docker Compose, the application uses **PostgreSQL 16** and **Redis 7**.

## Project Structure

E Commerce Flow Full Stack/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── cache.py
│   │   │   ├── deps.py
│   │   │   ├── recommendations.py
│   │   │   └── security.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── cart.py
│   │   │   ├── orders.py
│   │   │   ├── products.py
│   │   │   └── recommendations.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── seed.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_checkout.py
│   │   └── test_recommendations.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── Dockerfile
│   └── nginx.conf
│
├── docker-compose.yml
└── README.md
```

# Running Locally on Windows

## 1. Open the project

Open PowerShell and move into the backend directory:

   powershell
cd CommerceFlow\backend

## 2. Create a virtual environment

python -m venv .venv

Activate it:

.venv\Scripts\Activate.ps1


If PowerShell blocks activation, run:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Then activate again:

.venv\Scripts\Activate.ps1


## 3. Install dependencies

pip install -r requirements.txt

## 4. Create the environment file

From the `backend` directory:

copy .env.example .env

The provided development configuration uses SQLite, so no PostgreSQL setup is required for local development.

Redis is optional because CommerceFlow automatically uses an in-memory cache if Redis is unavailable.

## 5. Start the application

uvicorn app.main:app --reload

The application automatically initializes the database and seeds the required data when it starts.

## 6. Open the application

Open:

http://127.0.0.1:8000/

The FastAPI server serves the frontend directly, so you do not need to start a separate frontend server for local development.

## API Documentation

Swagger UI:

http://127.0.0.1:8000/docs

API information:

http://127.0.0.1:8000/api

Health check:

http://127.0.0.1:8000/health

## Demo Accounts

### User

Email: demo@commerceflow.dev
Password: demopassword123

### Admin

Email: admin@commerceflow.dev
Password: adminpassword123

# Running with Docker

Docker Compose starts the complete application stack:

PostgreSQL → Database
Redis      → Cache
FastAPI    → Backend/API
Nginx      → Frontend

## 1. Open the project root

cd E Commerce Flow Full Stack


## 2. Create the backend environment file

copy backend\.env.example backend\.env

## 3. Start all services

docker compose up --build


Wait until the services are running.

## 4. Open the application

Frontend:

http://localhost:8080

Backend/API:

http://localhost:8000

Swagger documentation:

http://localhost:8000/docs

Health check:

http://localhost:8000/health

## Stop the application

Press:

Ctrl + C

Or run:

docker compose down

To remove the PostgreSQL Docker volume as well:

docker compose down -v

## API Routes

The main API modules are:

/auth
/products
/cart
/orders
/recommendations


Full interactive API documentation is available at:

http://localhost:8000/docs


## Running Tests

From the project root:

cd backend

Activate the virtual environment if necessary:

.venv\Scripts\Activate.ps1

Run:

pytest

The test suite includes coverage for:

* Authentication
* Checkout
* Product recommendations

## Environment Configuration

The main environment variables are:

APP_NAME= E Commerce Flow Full Stack
ENVIRONMENT=development

DATABASE_URL=sqlite+aiosqlite:///./E Commerce Flow Full Stack.db
REDIS_URL=redis://localhost:6379/0

CACHE_TTL_SECONDS=60

JWT_SECRET=change-me-to-a-long-random-string-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=1440

CORS_ORIGINS=["*"]

For Docker, `docker-compose.yml` automatically configures PostgreSQL and Redis for the backend.


