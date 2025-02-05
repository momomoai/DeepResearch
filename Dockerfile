# Use Python 3.12 as the base image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy Poetry configuration
COPY pyproject.toml poetry.lock ./

# Copy the application code
COPY . .

# Install dependencies
RUN poetry install --no-dev

# Set environment variables
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV OPENAI_BASE_URL=${OPENAI_BASE_URL}
ENV OPENAI_MODEL=gpt-4o
ENV JINA_API_KEY=${JINA_API_KEY}

# Expose the port the app runs on
EXPOSE 3000

# Set the default command to run the application
CMD ["poetry", "run", "uvicorn", "deepresearch.main:app", "--host", "0.0.0.0", "--port", "3000"]
