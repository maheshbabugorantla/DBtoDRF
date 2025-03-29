# File: tests/test_generation.py
# Contains end-to-end integration tests for the drf-auto-generator tool.

import pytest
from pathlib import Path
import yaml
import requests
from datetime import date, datetime

# === Helper Functions (Updated create_test_post) ===

def create_test_author(api_client: requests.Session, name: str, email: str, bio: str = None) -> dict:
    """Creates an author via API and returns the response JSON, failing test on error."""
    url = f"{api_client.base_url}/api/author/"
    payload = {"name": name, "email": email}
    if bio is not None:
        payload["bio"] = bio
    payload["created_at"] = f"{datetime.now().isoformat()}Z"
    try:
        response = api_client.post(url, json=payload)
        if response.status_code != 201:
             pytest.fail(f"Setup failed: POST to {url} returned {response.status_code}. Response: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Setup failed: POST request to {url} failed: {e}")
    except Exception as e:
        pytest.fail(f"Setup failed: Error processing create author response: {e}")


def create_test_post(api_client: requests.Session, title: str, slug: str, author_id: int, content: str = "", status: str = "draft", published_date: str = None, read_count: int = 0) -> dict:
    """Creates a post via API and returns the response JSON."""
    url = f"{api_client.base_url}/api/post/"
    payload = {
        "title": title,
        "slug": slug,
        # --- FIX: Use serializer field name 'author_rel' ---
        "author_rel": author_id,
        # --- End Fix ---
        "content": content,
        "status": status,
        "read_count": read_count,
    }
    if published_date:
        payload["published_date"] = published_date
    else:
        payload["published_date"] = f"{datetime.now().isoformat()}Z"

    try:
        response = api_client.post(url, json=payload)
        if response.status_code != 201:
            pytest.fail(f"Setup failed: POST to {url} returned {response.status_code}. Response: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Setup failed: POST request to {url} failed: {e}")
    except Exception as e:
        pytest.fail(f"Setup failed: Error processing create post response: {e}")


# === Generator Execution and File Structure Tests ===

def test_generator_runs_successfully(run_generator):
    # ... (remains the same) ...
    assert run_generator is not None and run_generator.exists()


def test_generated_project_structure(run_generator: Path):
    """Check if essential files and directories exist."""
    # --- FIX: project_root IS the generated_dir ---
    project_root = run_generator
    # --- End Fix ---
    project_name = "testapi"
    app_name = "blog"

    # Root level files (relative to project_root)
    assert (project_root / "manage.py").is_file(), "manage.py not found in root"
    assert (project_root / "requirements.txt").is_file(), "requirements.txt not found in root"
    assert (project_root / ".env").is_file(), ".env not found in root"
    assert (project_root / ".gitignore").is_file(), ".gitignore not found in root"
    assert (project_root / "openapi.yaml").is_file(), "openapi.yaml not found in root"

    # Project Configuration Directory (relative to project_root)
    project_config_dir = project_root / project_name
    assert project_config_dir.is_dir(), f"Project config directory '{project_name}' not found"
    assert (project_config_dir / "settings.py").is_file(), "settings.py not found"
    assert (project_config_dir / "urls.py").is_file(), "urls.py not found"
    assert (project_config_dir / "wsgi.py").is_file()
    assert (project_config_dir / "asgi.py").is_file()

    # App Directory (relative to project_root)
    app_dir = project_root / app_name
    assert app_dir.is_dir(), f"App directory '{app_name}' not found"
    assert (app_dir / "models.py").is_file(), "models.py not found"
    assert (app_dir / "views.py").is_file(), "views.py not found"
    assert (app_dir / "serializers.py").is_file(), "serializers.py not found"
    assert (app_dir / "urls.py").is_file(), "urls.py not found"
    assert (app_dir / "admin.py").is_file()
    assert (app_dir / "apps.py").is_file()


def test_openapi_spec_generated(run_generator: Path):
    """
    Checks if the openapi.yaml specification file was generated,
    is valid YAML, and contains essential top-level OpenAPI keys.
    """
    # 1. Construct the expected path to the openapi.yaml file
    # Assumes it's generated in the root directory provided by run_generator
    openapi_file = run_generator / "openapi.yaml"

    # 2. Assert that the file exists
    assert openapi_file.is_file(), f"openapi.yaml was not found at expected location: {openapi_file}"

    # 3. Try to load and perform basic validation on the YAML content
    try:
        with open(openapi_file, 'r', encoding='utf-8') as f:
            # Use safe_load to parse the YAML securely
            spec = yaml.safe_load(f)

        # Assert basic structure and required keys
        assert isinstance(spec, dict), "Parsed openapi.yaml content is not a dictionary."
        assert 'openapi' in spec, "Generated spec missing required 'openapi' version key."
        assert isinstance(spec['openapi'], str), "'openapi' key value should be a string."
        assert 'info' in spec, "Generated spec missing required 'info' object."
        assert isinstance(spec['info'], dict), "'info' key value should be a dictionary."
        assert 'paths' in spec, "Generated spec missing required 'paths' object."
        assert isinstance(spec['paths'], dict), "'paths' key value should be a dictionary."
        assert 'components' in spec, "Generated spec missing required 'components' object."
        assert isinstance(spec['components'], dict), "'components' key value should be a dictionary."

        # Optional: Add a check for at least one path if tables were expected
        # if expected_tables_processed: # A hypothetical flag indicating success earlier
        #    assert len(spec.get('paths', {})) > 0, "No paths were generated in the OpenAPI spec."

    except yaml.YAMLError as e:
        # Fail specifically for YAML parsing errors
        pytest.fail(f"Failed to load generated openapi.yaml as valid YAML: {e}")
    except FileNotFoundError:
        # Should be caught by the initial assert, but handle defensively
        pytest.fail(f"openapi.yaml file disappeared after initial check at: {openapi_file}")
    except Exception as e:
        # Catch any other unexpected errors during file reading or basic checks
        pytest.fail(f"Failed to parse or perform basic validation on generated openapi.yaml: {e}")


# === Generated API Endpoint Tests ===

def test_api_schema_get_endpoint(api_client: requests.Session):
    """Test if the Swagger UI endpoint is reachable."""
    schema_url = f"{api_client.base_url}/api/schema/"
    response = api_client.get(schema_url)
    response.raise_for_status()
    assert response.status_code == 200
    # TODO: Check if the response is valid OpenAPI schema in JSON format
    # assert "openapi" in response.text.lower()


def test_api_schema_swagger_ui_is_accessible(api_client: requests.Session):
    """Test if the Swagger UI endpoint is reachable."""
    schema_url = f"{api_client.base_url}/api/schema/swagger-ui/"
    try:
        # --- FIX: Remove default Accept header for HTML endpoint ---
        headers = api_client.headers.copy()
        headers.pop('Accept', None)
        headers['Accept'] = 'text/html; charset=utf-8'
        response = api_client.get(schema_url, headers=headers)
        # --- End Fix ---
        response.raise_for_status() # Check for 4xx/5xx
        assert response.status_code == 200
        assert "swagger-ui" in response.text.lower()
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Request to {schema_url} failed: {e}")


# === Author Model Tests ===
test_authors_data = {} # Module level storage for created data

@pytest.mark.parametrize("payload", [
    {"name": "Author A", "email": "a@example.com", "bio": "Bio A"},
    {"name": "Author B", "email": "b@example.com"},
])
def test_create_author_and_verify(api_client: requests.Session, payload: dict):
    """Test creating a new author using authenticated client."""
    created_data = create_test_author(api_client, payload['name'], payload['email'], payload.get('bio'))
    assert created_data['name'] == payload['name']
    test_authors_data[payload['email']] = created_data


def test_list_authors(api_client: requests.Session):
    # ... (remains the same - GET works with IsAuthOrReadOnly) ...
    url = f"{api_client.base_url}/api/author/"
    response = api_client.get(url)
    response.raise_for_status()
    data = response.json()
    assert response.status_code == 200
    assert "results" in data
    assert data.get("count", 0) >= 2
    emails = {a['email'] for a in data['results']}
    assert "alice@example.com" in emails


def test_retrieve_author_alice(api_client: requests.Session):
    # ... (remains the same) ...
    author_id = 1
    url = f"{api_client.base_url}/api/author/{author_id}/"
    response = api_client.get(url)
    response.raise_for_status()
    data = response.json()
    assert response.status_code == 200
    assert data.get("id") == author_id
    assert data.get("name") == "Alice Author"


def test_update_author_bob(api_client: requests.Session):
    """Test full update (PUT) on Bob (ID 2) using authenticated client."""
    author_id = 2
    url = f"{api_client.base_url}/api/author/{author_id}/"
    payload = {"name": "Robert Blogger III", "email": "bob_v3@example.com", "bio": "Even newer bio!"}
    try:
        response = api_client.put(url, json=payload)
        response.raise_for_status() # Expect 200 OK
        data = response.json()
        assert response.status_code == 200
        assert data['name'] == payload['name']
        assert data['email'] == payload['email']
    except requests.exceptions.RequestException as e:
        pytest.fail(f"PUT {url} failed: {e}")


def test_partial_update_author_alice(api_client: requests.Session):
    """Test partial update (PATCH) on Alice (ID 1) using authenticated client."""
    # ... (remains the same, PATCH should now work) ...
    author_id = 1
    url = f"{api_client.base_url}/api/author/{author_id}/"
    payload = {"bio": "Bio via authenticated PATCH."}
    original_data = api_client.get(url).json()
    response = api_client.patch(url, json=payload)
    response.raise_for_status()
    data = response.json()
    assert response.status_code == 200
    assert data['bio'] == payload['bio']
    assert data['name'] == original_data['name']


def test_delete_author(api_client: requests.Session):
    """Test deleting an author using authenticated client."""
    temp_author = create_test_author(api_client, "ToDelete", "todelete@example.com")
    author_id = temp_author['id']
    url = f"{api_client.base_url}/api/author/{author_id}/"
    try:
        del_response = api_client.delete(url)
        assert del_response.status_code == 204
        get_response = api_client.get(url) # Verify deletion
        assert get_response.status_code == 404
    except requests.exceptions.RequestException as e:
        pytest.fail(f"DELETE/GET sequence failed: {e}")

# --- Author Constraint/Validation Tests ---

def test_create_author_duplicate_email_fail(api_client: requests.Session):
    """Test creating author with existing email fails (400)."""
    payload = {"name": "Duplicate Bob", "email": "bob@example.com"} # Use original Bob's email
    url = f"{api_client.base_url}/api/author/"
    response = api_client.post(url, json=payload)
    assert response.status_code == 400 # Expect 400 now
    data = response.json()
    assert "email" in data
    assert "unique" in str(data['email']).lower() or "already exists" in str(data['email']).lower()


def test_create_author_missing_name_fail(api_client: requests.Session):
    """Test creating author without required 'name' fails (400)."""
    payload = {"email": "noname@example.com"}
    url = f"{api_client.base_url}/api/author/"
    response = api_client.post(url, json=payload)
    assert response.status_code == 400 # Expect 400 now
    data = response.json()
    assert "name" in data
    assert "required" in str(data["name"]).lower()


# === Post Model Tests ===
test_posts_data = {}

def test_create_post_and_verify(api_client: requests.Session):
    """Test creating a new post using authenticated client."""
    author_id_bob = 2
    payload = {
        "title": "Bob Authenticated Post", "slug": "bob-auth-post", "author_id": author_id_bob,
        "status": "published", "published_date": date.today().isoformat()
    }
    created_data = create_test_post(api_client, **payload) # Helper uses 'author_rel' now
    assert created_data['title'] == payload['title']
    # --- FIX: Check 'author_rel' in response ---
    assert created_data.get('author_rel') == payload['author_id']
    # --- End Fix ---
    test_posts_data[created_data["slug"]] = created_data


def test_list_posts(api_client: requests.Session):
    # ... (remains the same - GET works) ...
    url = f"{api_client.base_url}/api/post/"
    response = api_client.get(url)
    response.raise_for_status()
    data = response.json()
    assert response.status_code == 200
    assert "results" in data
    assert data.get("count", 0) >= 2
    slugs = {p['slug'] for p in data['results']}
    assert "first-post-by-alice" in slugs
    assert "draft-by-bob" in slugs


def test_retrieve_post_one(api_client: requests.Session):
    """Test retrieving a specific pre-loaded post (ID 1)."""
    post_id = 1
    url = f"{api_client.base_url}/api/post/{post_id}/"
    response = api_client.get(url)
    response.raise_for_status()
    data = response.json()
    assert response.status_code == 200
    assert data.get("id") == post_id
    assert data.get("title") == "First Post by Alice"
    # --- FIX: Check 'author_rel' in response ---
    assert data.get("author_rel") == 1 # Alice's ID
    # --- End Fix ---
    assert data.get("status") == "published"


def test_update_post_draft(api_client: requests.Session):
    """Test full update (PUT) on Bob's draft post (ID 2)."""
    post_id = 2
    author_id = 2
    url = f"{api_client.base_url}/api/post/{post_id}/"
    payload = {
        "title": "Bob Updated Draft (Auth PUT)", "slug": "draft-by-bob",
        "content": "Updated PUT (Auth).", "published_date": None,
        "status": "draft", "read_count": 12,
        # --- FIX: Use 'author_rel' in payload ---
        "author_rel": author_id,
        # --- End Fix ---
    }
    try:
        response = api_client.put(url, json=payload)
        response.raise_for_status()
        data = response.json()
        assert response.status_code == 200
        assert data['title'] == payload['title']
        assert data['content'] == payload['content']
    except requests.exceptions.RequestException as e:
        pytest.fail(f"PUT {url} failed: {e}")


def test_partial_update_post_status(api_client: requests.Session):
    """Test partial update (PATCH) on Alice's post (ID 1)."""
    # ... (remains the same, PATCH should now work) ...
    post_id = 1
    url = f"{api_client.base_url}/api/post/{post_id}/"
    payload = {"status": "archived_auth"}
    response = api_client.patch(url, json=payload)
    response.raise_for_status()
    data = response.json()
    assert response.status_code == 200
    assert data['status'] == payload['status']


def test_delete_post(api_client: requests.Session):
    """Test deleting a post using authenticated client."""
    temp_post = create_test_post(api_client, "Temp Auth Del", "temp-auth-del", 1)
    post_id = temp_post['id']
    url = f"{api_client.base_url}/api/post/{post_id}/"
    try:
        del_response = api_client.delete(url)
        assert del_response.status_code == 204
        get_response = api_client.get(url)
        assert get_response.status_code == 404
    except requests.exceptions.RequestException as e:
        pytest.fail(f"DELETE/GET sequence failed: {e}")

# --- Post Constraint/Validation Tests ---

def test_create_post_invalid_author_fail(api_client: requests.Session):
    """Test creating post with non-existent author_id fails (400)."""
    non_existent_author_id = 999999
    url = f"{api_client.base_url}/api/post/"
    payload = {
        "title": "Bad Author Post", "slug": "bad-author-post",
        # --- FIX: Use 'author_rel' in payload ---
        "author_rel": non_existent_author_id
        # --- End Fix ---
        }
    response = api_client.post(url, json=payload)
    assert response.status_code == 400 # Expect 400 now
    data = response.json()
    # --- FIX: Check 'author_rel' in error response ---
    assert "author_rel" in data, "Error response should mention 'author_rel'"
    # --- End Fix ---


def test_create_post_missing_required_fields_fail(api_client: requests.Session):
    """Test creating post missing title, slug, author fails (400)."""
    url = f"{api_client.base_url}/api/post/"
    payload = {"content": "Incomplete post"}
    response = api_client.post(url, json=payload)
    assert response.status_code == 400 # Expect 400 now
    data = response.json()
    assert "title" in data and "required" in str(data["title"]).lower()
    assert "slug" in data and "required" in str(data["slug"]).lower()
    # --- FIX: Check 'author_rel' in error response ---
    assert "author_rel" in data and "required" in str(data["author_rel"]).lower()
    # --- End Fix ---


def test_create_post_duplicate_slug_fail(api_client: requests.Session):
    """Test creating post with existing slug fails (400)."""
    existing_slug = "first-post-by-alice"
    author_id = 2 # Bob
    url = f"{api_client.base_url}/api/post/"
    payload = {
        "title": "Duplicate Slug", "slug": existing_slug,
        # --- FIX: Use 'author_rel' in payload ---
        "author_rel": author_id
        # --- End Fix ---
        }
    response = api_client.post(url, json=payload)
    assert response.status_code == 400 # Expect 400 now
    data = response.json()
    assert "slug" in data
    assert "unique" in str(data['slug']).lower() or "already exists" in str(data['slug']).lower()


def test_create_post_duplicate_author_title_fail(api_client: requests.Session):
    """Test creating post with existing (author, title) combination fails (400)."""
    author_id = 1 # Alice
    existing_title = "First Post by Alice"
    url = f"{api_client.base_url}/api/post/"
    payload = {
        "title": existing_title, "slug": "another-slug-different-this-time", # New unique slug
        # --- FIX: Use 'author_rel' in payload ---
        "author_rel": author_id
        # --- End Fix ---
        }
    response = api_client.post(url, json=payload)
    assert response.status_code == 400 # Expect 400 now
    data = response.json()
    assert "non_field_errors" in data, "Expected 'non_field_errors' for multi-column unique constraint violation."
    error_msg = str(data['non_field_errors']).lower()
    assert "unique" in error_msg or "already exists" in error_msg, f"Unexpected error message: {data['non_field_errors']}"
