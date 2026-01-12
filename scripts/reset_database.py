#!/usr/bin/env python3
"""
Complete Database Reset Script
Drops all tables and recreates fresh schema
"""
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')

def reset_database():
    """Drop all tables and recreate schema"""
    logger.info("=" * 60)
    logger.info("STARTING DATABASE RESET")
    logger.info("=" * 60)
    logger.info(f"Target Database: {DATABASE_URL.split('@')[-1].split('/')[0]}")
    
    # Create engine without ORM first to get raw connection
    engine = create_engine(DATABASE_URL, echo=False)
    
    try:
        # Connect and get list of all tables
        with engine.connect() as connection:
            # Get all table names
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            logger.info(f"Found {len(tables)} tables to drop")
            
            if not tables:
                logger.info("✓ Database is already empty")
            else:
                # Disable foreign key constraints temporarily
                logger.info("Disabling foreign key constraints...")
                connection.execute(text("SET session_replication_role = 'replica'"))
                connection.commit()
                
                # Drop all tables
                for table in tables:
                    logger.info(f"  Dropping table: {table}")
                    connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    connection.commit()
                
                # Re-enable foreign key constraints
                logger.info("Re-enabling foreign key constraints...")
                connection.execute(text("SET session_replication_role = 'origin'"))
                connection.commit()
                
                logger.info("✓ All tables dropped successfully")
        
        # Now recreate schema using SQLAlchemy models
        logger.info("\nRecreating schema from models...")
        
        # Import all models to ensure they're registered with Base
        from app.core.database import Base
        from app.models import models
        from app.models import bcom_models
        
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Schema recreated successfully")
        
        # Verify tables were created
        with engine.connect() as connection:
            inspector = inspect(engine)
            new_tables = inspector.get_table_names()
            logger.info(f"✓ Created {len(new_tables)} tables:")
            for table in sorted(new_tables):
                logger.info(f"  - {table}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ DATABASE RESET COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info("\nDatabase is ready for fresh data ingestion!")
        logger.info("Next step: Run 'python ingest_simple.py'")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error during reset: {e}", exc_info=True)
        return False
    finally:
        engine.dispose()


if __name__ == '__main__':
    success = reset_database()
    exit(0 if success else 1)
