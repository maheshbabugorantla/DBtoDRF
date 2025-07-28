# Simple Blog Example

This example demonstrates how to use DRF Auto Generator with a simple blog database schema.

## Schema Overview

The simple blog schema includes:

- **Author Table**: Authors with name, email, bio, and creation timestamp
- **Post Table**: Blog posts with title, slug, content, publication date, and author relationship

## Quick Start

### 1. Start the Database

```bash
# Start PostgreSQL with sample data
docker-compose up -d

# Verify the database is running
docker-compose ps
```

The database will be available at:
- **Host**: localhost
- **Port**: 5432
- **Database**: simple_blog
- **User**: blog_user
- **Password**: blog_password

### 2. Browse the Database (Optional)

Adminer web interface is available at: http://localhost:8080

- **System**: PostgreSQL
- **Server**: postgres
- **Username**: blog_user
- **Password**: blog_password
- **Database**: simple_blog

### 3. Generate the API

```bash
# From the project root directory
cd examples/simple_blog

# Generate the Django REST API
drf-generate -c simple_blog_db_config.yaml
```

### 4. Run the Generated API

```bash
# Navigate to generated project
cd simple_blog_api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (optional, tables already exist)
python manage.py makemigrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

### 5. Explore the API

- **API Root**: http://127.0.0.1:8000/api/
- **Swagger Documentation**: http://127.0.0.1:8000/api/schema/swagger-ui/
- **Admin Interface**: http://127.0.0.1:8000/admin/

### 6. Test the API

```bash
# Run generated tests
python -m pytest blog/tests/ -v

# Run schemathesis property-based tests
python blog/tests/test_schemathesis_integration.py
```

## API Endpoints

The generated API includes:

### Authors
- `GET /api/authors/` - List all authors
- `POST /api/authors/` - Create new author
- `GET /api/authors/{id}/` - Get author details
- `PUT /api/authors/{id}/` - Update author
- `DELETE /api/authors/{id}/` - Delete author

### Posts
- `GET /api/posts/` - List all posts
- `POST /api/posts/` - Create new post
- `GET /api/posts/{id}/` - Get post details
- `PUT /api/posts/{id}/` - Update post
- `DELETE /api/posts/{id}/` - Delete post

## Sample Data

The database includes comprehensive test data:

**Authors:** 10 diverse authors with detailed profiles
- Alice Johnson (Python/Django expert) - 4 posts
- Bob Martinez (Full-stack developer) - 4 posts  
- Carol Chen (AI/ML researcher) - 4 posts
- David Kumar (DevOps engineer) - 4 posts
- Emma Thompson (UI/UX designer) - 4 posts
- Frank Wilson (Startup founder) - 4 posts
- Grace Liu (Cloud architect) - 4 posts
- Henry Adams (Security specialist) - 4 posts
- Isabel Rodriguez (Mobile developer) - 4 posts
- Jack Thompson (Game developer) - 4 posts

**Posts:** 40 total posts across different topics
- 30 published posts with realistic read counts (500-2000+ reads)
- 10 draft posts for testing different states
- Topics include: Web Development, AI/ML, DevOps, Security, Mobile, Gaming, UX/UI

## Cleanup

```bash
# Stop and remove containers
docker-compose down

# Remove volumes (optional, will delete all data)
docker-compose down -v
```

## Notes

- The schema demonstrates foreign key relationships between authors and posts
- Includes various PostgreSQL features like indexes, constraints, and default values
- Shows how the generator handles different data types and constraints
- Perfect for testing and demonstrating the tool's capabilities