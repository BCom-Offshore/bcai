#!/usr/bin/env python3
"""
PostgreSQL Local Setup Script

This script automates the initial setup of a local PostgreSQL database
for the BCom AI Services API.

Usage:
    python scripts/setup_local_postgres.py

Or with custom parameters:
    python scripts/setup_local_postgres.py --host localhost --port 5432 --user postgres --password P@ssw0rd --db bcai
"""

import sys
import argparse
#import subprocess
from pathlib import Path
#from typing import Optional
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def print_header(message: str) -> None:
    """Print a formatted header message."""
    print("\n" + "=" * 70)
    print(f"  {message}")
    print("=" * 70)


def print_step(step: int, message: str) -> None:
    """Print a formatted step message."""
    print(f"\n[Step {step}] {message}")
    print("-" * 70)


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"✓ {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"✗ {message}")


def test_postgres_connection(
    host: str, port: int, user: str, password: str, db: str = "postgres"
) -> bool:
    """Test if PostgreSQL is accessible."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db
        )
        conn.close()
        return True
    except (psycopg2.OperationalError, psycopg2.Error) as e:
        print_error(f"Cannot connect to PostgreSQL: {e}")
        return False


def create_database(
    host: str,
    port: int,
    user: str,
    password: str,
    db: str,
    owner: str
) -> bool:
    """Create a database with the specified owner."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(
            f"SELECT 1 FROM pg_database WHERE datname = '{db}'"
        )
        if cursor.fetchone():
            print_success(f"Database '{db}' already exists")
            cursor.close()
            conn.close()
            return True

        # Create database
        cursor.execute(f"CREATE DATABASE {db} OWNER {owner}")
        print_success(f"Created database '{db}'")

        cursor.close()
        conn.close()
        return True

    except (psycopg2.OperationalError, psycopg2.Error) as e:
        print_error(f"Failed to create database: {e}")
        return False


def create_user(
    host: str,
    port: int,
    user: str,
    password: str,
    new_user: str,
    new_password: str
) -> bool:
    """Create a new database user."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute(f"SELECT 1 FROM pg_user WHERE usename = '{new_user}'")
        if cursor.fetchone():
            print_success(f"User '{new_user}' already exists")
            cursor.close()
            conn.close()
            return True

        # Create user
        cursor.execute(
            f"CREATE ROLE {new_user} WITH LOGIN PASSWORD %s",
            (new_password,)
        )
        cursor.execute(f"ALTER ROLE {new_user} CREATEDB")
        print_success(f"Created user '{new_user}'")

        cursor.close()
        conn.close()
        return True

    except (psycopg2.OperationalError, psycopg2.Error) as e:
        print_error(f"Failed to create user: {e}")
        return False


def run_migrations(
    host: str,
    port: int,
    user: str,
    password: str,
    db: str,
    migrations_dir: Path
) -> bool:
    """Run SQL migration files."""
    try:
        if not migrations_dir.exists():
            print(f"Migrations directory not found: {migrations_dir}")
            return False

        migration_files = sorted(migrations_dir.glob("*.sql"))
        if not migration_files:
            print("No migration files found")
            return True

        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        for migration_file in migration_files:
            print(f"Running migration: {migration_file.name}")
            with open(migration_file, 'r') as f:
                sql = f.read()
                cursor.execute(sql)
            print_success(f"Completed: {migration_file.name}")

        cursor.close()
        conn.close()
        return True

    except (psycopg2.OperationalError, psycopg2.Error) as e:
        print_error(f"Failed to run migrations: {e}")
        return False


def verify_tables(
    host: str,
    port: int,
    user: str,
    password: str,
    db: str
) -> bool:
    """Verify that tables were created."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db
        )
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()

        if tables:
            print_success(f"Found {len(tables)} table(s):")
            for table in tables:
                print(f"  • {table[0]}")
        else:
            print("No tables found (this is OK if migrations haven't run)")

        cursor.close()
        conn.close()
        return True

    except (psycopg2.OperationalError, psycopg2.Error) as e:
        print_error(f"Failed to verify tables: {e}")
        return False


def create_env_file(
    env_file: Path,
    host: str,
    port: int,
    user: str,
    password: str,
    db: str
) -> bool:
    """Create or update .env file with database configuration."""
    try:
        # Read .env.example if it exists
        example_file = env_file.parent / ".env.example"
        if example_file.exists():
            with open(example_file, 'r') as f:
                content = f.read()
        else:
            content = ""

        # Update DATABASE_URL
        database_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"
        
        # If .env exists, update it; otherwise create from example
        if env_file.exists():
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            updated = False
            new_lines = []
            for line in lines:
                if line.startswith("DATABASE_URL="):
                    new_lines.append(f"DATABASE_URL={database_url}\n")
                    updated = True
                else:
                    new_lines.append(line)
            
            # If DATABASE_URL wasn't in file, add it
            if not updated:
                new_lines.append(f"DATABASE_URL={database_url}\n")
            
            with open(env_file, 'w') as f:
                f.writelines(new_lines)
        else:
            # Create new .env from example
            if example_file.exists():
                content = example_file.read_text()
                # Replace DATABASE_URL if it exists
                if "DATABASE_URL=" in content:
                    lines = content.split('\n')
                    new_lines = []
                    for line in lines:
                        if line.startswith("DATABASE_URL="):
                            new_lines.append(f"DATABASE_URL={database_url}")
                        else:
                            new_lines.append(line)
                    content = '\n'.join(new_lines)
                else:
                    content = f"DATABASE_URL={database_url}\n" + content
            else:
                content = f"DATABASE_URL={database_url}\n"

            with open(env_file, 'w') as f:
                f.write(content)

        print_success(f"Created/updated .env file")
        print(f"  DATABASE_URL=postgresql+psycopg://{user}:***@{host}:{port}/{db}")
        return True

    except Exception as e:
        print_error(f"Failed to create .env file: {e}")
        return False


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(
        description="Set up local PostgreSQL for BCom AI Services API"
    )
    parser.add_argument("--host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--user", default="postgres", help="PostgreSQL admin user")
    parser.add_argument("--password", default="P@ssw0rd", help="PostgreSQL admin password")
    parser.add_argument("--db", default="bcai", help="Database name to create")
    parser.add_argument("--app-user", default="postgres", help="Application user name")
    parser.add_argument("--app-password", default="P@ssw0rd", help="Application user password")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip running migrations")
    parser.add_argument("--verify-only", action="store_true", help="Only verify connection, don't create")

    args = parser.parse_args()

    print_header("BCom AI Services API - Local PostgreSQL Setup")

    # Step 1: Test connection
    print_step(1, "Testing PostgreSQL Connection")
    if not test_postgres_connection(args.host, args.port, args.user, args.password):
        print_error("Cannot connect to PostgreSQL")
        print("\nPlease ensure:")
        print("  1. PostgreSQL is installed")
        print("  2. PostgreSQL service is running")
        print("  3. Host and port are correct")
        print("  4. Credentials are correct")
        sys.exit(1)
    
    print_success(f"Connected to PostgreSQL at {args.host}:{args.port}")

    if args.verify_only:
        print_header("Verification Complete")
        sys.exit(0)

    # Step 2: Create database user
    print_step(2, "Creating Database User")
    if not create_user(
        args.host,
        args.port,
        args.user,
        args.password,
        args.app_user,
        args.app_password
    ):
        print_error("Failed to create user")
        sys.exit(1)

    # Step 3: Create database
    print_step(3, "Creating Database")
    if not create_database(
        args.host,
        args.port,
        args.user,
        args.password,
        args.db,
        args.app_user
    ):
        print_error("Failed to create database")
        sys.exit(1)

    # Step 4: Run migrations
    if not args.skip_migrations:
        print_step(4, "Running Migrations")
        migrations_dir = Path(__file__).parent.parent / "db" / "migrations"
        if not run_migrations(
            args.host,
            args.port,
            args.app_user,
            args.app_password,
            args.db,
            migrations_dir
        ):
            print_error("Failed to run migrations (continuing...)")

    # Step 5: Verify tables
    print_step(5, "Verifying Database Tables")
    verify_tables(
        args.host,
        args.port,
        args.app_user,
        args.app_password,
        args.db
    )

    # Step 6: Create/update .env file
    print_step(6, "Configuring Environment Variables")
    env_file = Path(__file__).parent.parent / ".env"
    if not create_env_file(
        env_file,
        args.host,
        args.port,
        args.app_user,
        args.app_password,
        args.db
    ):
        print_error("Failed to create .env file")
        sys.exit(1)

    # Success!
    print_header("✓ Setup Complete!")
    print(f"""
You're all set! Here's what was configured:

Database Configuration:
  • Host: {args.host}
  • Port: {args.port}
  • Database: {args.db}
  • User: {args.app_user}

Configuration File:
  • Created/updated: .env
  • Contains: DATABASE_URL and other settings

Next Steps:
  1. Verify PostgreSQL is still running
  2. Start the application: python run.py
  3. Access API documentation: http://localhost:8010/docs
  4. Check health: http://localhost:8010/health

For more information, see LOCAL_POSTGRES_SETUP.md
    """)


if __name__ == "__main__":
    main()
