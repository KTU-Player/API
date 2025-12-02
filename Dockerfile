# Stage 1: Build the virtual environment
FROM python:3.13.9-alpine3.22 AS builder

# Install poetry
RUN pip install poetry

# Set working directory
WORKDIR /app

# Configure poetry to create the virtual env in the project's root
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

# Copy the files required by poetry
COPY pyproject.toml poetry.lock ./

# Install dependencies, without dev dependencies
RUN poetry install --no-root --without dev

# Stage 2: Final image
FROM python:3.13.9-alpine3.22

# Set working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv .venv

# Copy the application code
COPY src/ ./src
COPY alembic.ini .
COPY alembic/ ./alembic

# Set the PATH to include the virtual environment's binaries
ENV PATH="/app/.venv/bin:$PATH"

# The command to run the application will be specified in the compose.yaml