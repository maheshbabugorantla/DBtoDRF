# File: tests/conftest.py
# Contains pytest fixtures for setting up the integration test environment.

import pytest
import subprocess
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Generator

# Database connector (needed here for schema loading and connection check)
import psycopg2
# HTTP client for checking server status and API calls
import requests
from requests.adapters import HTTPAdapter, Retry
# Jinja for rendering test config
from jinja2 import Environment, FileSystemLoader
from testcontainers.postgres import PostgresContainer


# --- Constants ---
# Assumes conftest.py is in tests/ subdirectory relative to project root
GENERATOR_PROJECT_ROOT = Path(__file__).parent.parent
TEST_SCHEMAS_DIR = GENERATOR_PROJECT_ROOT / "tests" / "schemas"
TEST_CONFIG_TEMPLATES_DIR = GENERATOR_PROJECT_ROOT / "tests" / "config_templates"


# --- Fixture for Database Container (using Testcontainers) ---
@pytest.fixture(scope="session")
def pg_service() -> Generator[Dict[str, Any], Any, None]:
    """
    Starts/stops a PostgreSQL container for the test session using testcontainers.
    Maps the container's internal port 5432 to an available port on the host.
    Yields a dictionary with database connection details.
    """

    test_db_user = "testuser"
    test_db_password = "testpassword"
    test_db_name = "testdb"

    try:
        pg_container = PostgresContainer(
            image="postgres:15-alpine",
            username=test_db_user,
            password=test_db_password,
            dbname=test_db_name
        )
        # --- Explicitly request mapping for the internal container port ---
        # We tell testcontainers we care about port 5432 INSIDE the container.
        pg_container.with_exposed_ports(5432) # <<< This line is key

        print("\nStarting PostgreSQL container via testcontainers...")
        with pg_container as pg:
            print("PostgreSQL container started and ready.")

            host = pg.get_container_host_ip()
            # --- Retrieve the HOST port mapped to the CONTAINER's 5432 port ---
            port = pg.get_exposed_port(5432) # <<< Retrieves the dynamically assigned HOST port
            # --- End Port Retrieval ---

            user = pg.username
            password = pg.password
            db_name = pg.dbname
            # get_connection_url automatically uses the correct mapped host port
            db_url = pg.get_connection_url()

            # The printed port will be the random host port assigned by Docker/Testcontainers
            # (e.g., 32768, 49153, etc.), NOT 5432 (unless by chance it was free).
            # It will NOT conflict with your local service running on host port 5432.
            print(f"  Container Port 5432 mapped to Host Port: {port}")
            print(f"  Host: {host}")
            print(f"  User: {user}")
            print(f"  Database: {db_name}")
            print(f"  URL: {db_url}")

            # Yield the details including the dynamically assigned HOST port
            yield {
                "url": db_url,
                "host": host,
                "port": int(port), # The dynamic host port
                "user": user,
                "password": password,
                "db_name": db_name,
            }
            print("Stopping PostgreSQL container...")
        print("PostgreSQL container stopped.")

    except Exception as e:
        pytest.fail(f"Failed to start or manage PostgreSQL testcontainer: {e}", pytrace=False)


# --- Fixture for Database Connection ---
@pytest.fixture(scope="session")
def db_connection(pg_service: Dict[str, Any]) -> Generator[psycopg2.extensions.connection, Any, None]:
    """
    Provides a psycopg2 connection object to the test database container.
    Connects using keyword arguments derived from pg_service fixture.
    """
    try:
        print(
            f"Connecting to test DB using keyword args: "
            f"dbname='{pg_service['db_name']}', "
            f"user='{pg_service['user']}', "
            f"host='{pg_service['host']}', "
            f"port={pg_service['port']}..."
        )
        conn = psycopg2.connect(
            dbname=pg_service['db_name'],
            user=pg_service['user'],
            password=pg_service['password'],
            host=pg_service['host'],
            port=pg_service['port'],
            connect_timeout=5
        )
        print("Database connection established.")
        yield conn # Provide connection to fixtures/tests that need it
        conn.close()
        print("Database connection closed.")
    except psycopg2.OperationalError as e:
        pytest.fail(f"Failed to connect to the test PostgreSQL database: {e}")
    except Exception as e:
         pytest.fail(f"Unexpected error connecting to database: {e}")


# --- Fixture to Load Database Schema ---
@pytest.fixture(scope="session", autouse=True) # autouse=True runs this automatically for the session
def load_test_schema(db_connection):
    """
    Loads the test database schema from .sql file(s).
    Ensure the SQL file path is correct.
    """
    # --- Using SQL file(s) ---
    schema_file = TEST_SCHEMAS_DIR / "simple_blog.sql" # Adjust filename if needed

    if not schema_file.is_file():
        pytest.fail(f"Test schema file not found: {schema_file}")

    try:
        print(f"\nLoading schema and data from {schema_file}...")
        with db_connection.cursor() as cursor:
            # Read the whole file which includes schema and potentially INSERTs
            cursor.execute(schema_file.read_text(encoding='utf-8'))
        db_connection.commit() # Commit changes after execution
        print("Schema and data loaded successfully.")

    except psycopg2.Error as e:
        # Rollback might be needed if partial execution occurred before error
        db_connection.rollback()
        pytest.fail(f"Database error loading schema/data: {e}")
    except Exception as e:
        pytest.fail(f"Failed to load test schema/data: {e}")


# --- Fixture for Temporary Output Directory ---
@pytest.fixture(scope="module")
def test_output_dir(tmp_path_factory) -> Generator[Path, Any, Any]:
    """
    Provides a unique temporary directory path for each test function's output,
    managed by pytest's tmp_path fixture.
    """
    # Create a base temporary directory for the module
    base_temp_dir = tmp_path_factory.mktemp("generated_module_")
    # Create the specific output dir within the module temp dir
    output_path = base_temp_dir / "generated_project"
    output_path.mkdir()
    print(f"Using module-scoped temporary output directory: {output_path}")
    # tmp_path_factory handles cleanup automatically after test module finishes
    yield output_path
    # Cleanup handled automatically by pytest


# --- Fixture to Create Test Configuration File ---
@pytest.fixture(scope="module")
def generator_config_file(pg_service: Dict[str, Any], test_output_dir: Path) -> Generator[Path, Any, Any]:
    """
    Creates a temporary config.yaml file using a Jinja2 template,
    injecting database details and the temporary output directory path.
    """
    if not TEST_CONFIG_TEMPLATES_DIR.is_dir():
        pytest.fail(f"Test config templates directory not found: {TEST_CONFIG_TEMPLATES_DIR}")

    try:
        env = Environment(loader=FileSystemLoader(TEST_CONFIG_TEMPLATES_DIR), autoescape=False)
        template = env.get_template("test_config.yaml.j2")
        context = {
            "db_host": pg_service["host"],
            "db_port": pg_service["port"],
            "db_user": pg_service["user"],
            "db_password": pg_service["password"],
            "db_name": pg_service["db_name"],
            "output_dir": str(test_output_dir), # Use module-scoped output dir
        }
        rendered_config = template.render(context)
    except Exception as e:
         pytest.fail(f"Failed to render test config template: {e}")

    # Write config file in the module's base temp dir (parent of output dir)
    config_file = test_output_dir.parent / "test_run_config.yaml"
    try:
        config_file.write_text(rendered_config, encoding='utf-8')
        print(f"Generated module-scoped test config file: {config_file}")
        yield config_file
    except Exception as e:
         pytest.fail(f"Failed to write test config file: {e}")


# --- Fixture to Run the Code Generator ---
@pytest.fixture(scope="module")
def run_generator(generator_config_file: Path, test_output_dir: Path) -> Generator[Path, Any, Any]:
    """
    Executes the drf-auto-generator CLI command as a subprocess.
    Fails the test if the command returns a non-zero exit code.
    Yields the path to the directory containing the generated project.
    """
    cmd = [
        sys.executable, # Use the active Python interpreter
        "-m", "drf_auto_generator.cli", # Execute the cli module
        "-c", str(generator_config_file), # Pass path to test config
        "-v", # Enable verbose output for debugging tests
    ]
    print(f"\nRunning generator command (module scope): {' '.join(cmd)}")
    try:
        # Run from the root of the generator project so relative imports work
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=GENERATOR_PROJECT_ROOT, # Crucial: run from project root
            timeout=90
        )
        print("--- Generator STDOUT ---")
        print(result.stdout)
        print("--- Generator STDERR ---")
        print(result.stderr)
        print("--- Generator finished successfully ---")
        yield test_output_dir # Return path to generated code
    except FileNotFoundError:
         pytest.fail(f"Could not find Python executable '{sys.executable}' or drf_auto_generator module.")
    except subprocess.CalledProcessError as e:
        print("--- Generator FAILED ---")
        print(f"Exit Code: {e.returncode}")
        print("--- STDOUT ---")
        print(e.stdout)
        print("--- STDERR ---")
        print(e.stderr)
        pytest.fail(f"drf-generate command failed with exit code {e.returncode}")
    except subprocess.TimeoutExpired as e:
        print("--- Generator TIMEOUT ---")
        print("--- STDOUT ---")
        print(e.stdout if e.stdout else "N/A")
        print("--- STDERR ---")
        print(e.stderr if e.stderr else "N/A")
        pytest.fail("drf-generate command timed out.")
    except Exception as e:
         pytest.fail(f"Unexpected error running generator subprocess: {e}")


def run_manage_py_command(command: list, cwd: Path, python_exe: Path, env: Dict[str, Any] = None):
    """Runs a manage.py command in the generated project's venv."""
    manage_py = cwd / "manage.py"
    if not manage_py.is_file():
        pytest.fail(f"manage.py not found in {cwd}")

    cmd = [str(python_exe), str(manage_py)] + command
    print(f"\nRunning manage.py command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True, encoding='utf-8',
            cwd=cwd, timeout=60, env=env
        )
        print(f"manage.py {command[0]} STDOUT:", result.stdout)
        print(f"manage.py {command[0]} STDERR:", result.stderr)
        return result
    except subprocess.CalledProcessError as e:
        print(f"manage.py {command[0]} FAILED!")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        pytest.fail(f"manage.py {command[0]} failed with exit code {e.returncode}")
    except Exception as e:
        pytest.fail(f"Unexpected error running manage.py {command[0]}: {e}")


# --- Fixture to Set Up and Run the Generated API Server ---
@pytest.fixture(scope="module") # Run server once per test module
def running_generated_api(run_generator: Path):
    """
    Sets up the generated Django project (venv, install, migrate)
    and runs its development server in a background process.
    Yields the base URL of the running server.
    Handles server shutdown during teardown.
    """
    generated_project_path = run_generator
    api_port = 8001 # Use a non-default port
    api_host = "127.0.0.1"
    api_base_url = f"http://{api_host}:{api_port}"
    manage_py = generated_project_path / "manage.py"
    requirements_txt = generated_project_path / "requirements.txt"
    venv_path = generated_project_path / ".venv_generated_test"
    server_process = None

    # --- Environment setup for manage.py ---
    # We need DJANGO_SETTINGS_MODULE and potentially PYTHONPATH
    project_name = "testapi" # Get this dynamically if possible
    manage_py_env = os.environ.copy()
    manage_py_env["DJANGO_SETTINGS_MODULE"] = f"{project_name}.settings"
    # Add project root to pythonpath if needed, though running from cwd should work
    # manage_py_env["PYTHONPATH"] = str(generated_project_path) + os.pathsep + manage_py_env.get("PYTHONPATH", "")
    # Load .env for the generated project if manage.py commands need it
    dotenv_path = generated_project_path / ".env"
    if dotenv_path.exists():
         # Need a way to load these into the dict easily, or assume manage.py handles it via load_dotenv()
         pass # Assuming manage.py loads .env

    # --- Pre-checks ---
    if not manage_py.is_file():
        pytest.fail(f"Generated manage.py not found at {manage_py}")
    if not requirements_txt.is_file():
        pytest.fail(f"Generated requirements.txt not found at {requirements_txt}")

    try:
        # 1. Create Virtual Environment
        print(f"\nCreating virtualenv for generated project at {venv_path}")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True, timeout=30)

        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        pip_executable = venv_path / bin_dir / "pip"
        python_executable = venv_path / bin_dir / "python"

        # 2. Install Requirements (ensure driver was correctly added by template!)
        print(f"Installing requirements from {requirements_txt} into {venv_path}...")
        install_cmd = [str(pip_executable), "install", "--no-cache-dir", "-r", str(requirements_txt)]
        subprocess.run(install_cmd, check=True, capture_output=True, timeout=240) # Longer timeout for pip

        # 3. Run Migrations (for Django's own apps)
        print("Running migrations for generated project...")
        run_manage_py_command(
            ["migrate", "--noinput"],
            generated_project_path,
            python_executable,
            env=manage_py_env,
        )

        # 4. Create Superuser
        print("Creating test superuser...")
        # Use manage.py shell to execute user creation command
        test_user_create_cmd = (
            "from django.contrib.auth import get_user_model; "
            "User = get_user_model(); "
            "User.objects.filter(username='testuser').delete(); " # Delete if exists from previous run
            "User.objects.create_superuser('testuser', 'test@example.com', 'testpassword')"
        )
        run_manage_py_command(
            ["shell", "-c", test_user_create_cmd],
            cwd=generated_project_path,
            python_exe=python_executable,
            env=manage_py_env,
        )
        print("Test superuser 'testuser' successfully created")

        # 5. Run Server in Background
        print(f"Starting generated Django server on {api_host}:{api_port}...")
        runserver_cmd = [str(python_executable), str(manage_py), "runserver", f"{api_host}:{api_port}", "--noreload"]
        # Use Popen to run in background
        server_process = subprocess.Popen(
            runserver_cmd,
            cwd=generated_project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )

        # 6. Wait for Server Readiness
        print("Waiting for generated server to become ready...")
        retries = 25 # Give it ~30-40 seconds total
        ready = False
        # Check a lightweight endpoint like the schema URL
        schema_url_path = "/api/schema/" # Adjust if your root urls change
        health_check_url = f"{api_base_url}{schema_url_path}"
        last_error = "Timeout"
        while retries > 0:
            if server_process.poll() is not None:
                 stdout, stderr = server_process.communicate()
                 print("! Server process terminated prematurely during startup check.")
                 print("--- Server STDOUT ---:\n", stdout)
                 print("--- Server STDERR ---:\n", stderr)
                 pytest.fail("Generated Django server process died during startup.")

            try:
                response = requests.get(health_check_url, timeout=1.5)
                if response.status_code == 200:
                    print("Generated server is ready.")
                    ready = True
                    break
                else:
                    last_error = f"Server responded {response.status_code}"
                    print(f"{last_error}, waiting...")
            except requests.exceptions.ConnectionError:
                last_error = "ConnectionError"
                print("Server not connectable yet, waiting...")
            except Exception as e:
                 last_error = str(e)
                 print(f"Error checking server status: {e}, waiting...")

            time.sleep(1.5)
            retries -= 1

        if not ready:
            # If server didn't start, terminate and show logs
            server_process.terminate()
            stdout, stderr = server_process.communicate(timeout=5)
            print("--- Server STDOUT (Startup Failure) ---:\n", stdout)
            print("--- Server STDERR (Startup Failure) ---:\n", stderr)
            pytest.fail(f"Generated Django server did not become ready at {health_check_url}. Last error: {last_error}")

        # 6. Yield Control (Base URL) to Tests
        yield api_base_url

    # --- Teardown ---
    finally:
        if server_process and server_process.poll() is None:
            print("\nStopping generated Django server...")
            server_process.terminate()
            try:
                stdout, stderr = server_process.communicate(timeout=10)
                print("--- Server STDOUT (Shutdown) ---:\n", stdout)
                print("--- Server STDERR (Shutdown) ---:\n", stderr)
            except subprocess.TimeoutExpired:
                print("Server did not terminate gracefully, killing.")
                server_process.kill()
                server_process.communicate() # Consume output after kill
        elif server_process:
             print("\nGenerated Django server already terminated.")
        # venv cleanup handled by tmp_path parent fixture


# --- Fixture for API HTTP Client ---
@pytest.fixture(scope="module")
def api_client(running_generated_api: str) -> requests.Session:
    """
    Provides a pre-configured requests.Session object for making API calls
    to the running generated API server. Includes basic retries.
    """
    base_url = running_generated_api
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.headers.update({
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    })
    session.base_url = base_url # Store base URL for convenience

    # --- Authenticate ---
    print("\nAuthenticating API client...")
    auth_url = f"{base_url}/api/auth-token/"
    auth_payload = {"username": "testuser", "password": "testpassword"}
    try:
        # Use standard requests post, not the session initially, to avoid potential loops
        auth_response = requests.post(auth_url, data=auth_payload, timeout=10) # Use data for form encoding
        auth_response.raise_for_status()
        token_data = auth_response.json()
        auth_token = token_data.get('token')
        if not auth_token:
            pytest.fail("Failed to retrieve auth token from API.")

        # Set the Authorization header for the session
        session.headers.update({'Authorization': f'Token {auth_token}'})
        print("API client authenticated successfully.")

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Failed to authenticate API client at {auth_url}: {e}")
    except Exception as e:
         pytest.fail(f"Error processing authentication response: {e}")
    # --- End Authenticate ---

    return session
