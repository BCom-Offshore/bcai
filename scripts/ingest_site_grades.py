#!/usr/bin/env python3
"""
Site Grades Data Ingestion
Loads site performance grades from CSV into site_grades table

Note: This script is located in the scripts/ folder, so data paths are relative to the root directory.
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from root directory
load_dotenv(Path(__file__).parent.parent / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

# Import models
from app.models.bcom_models import SiteGrade, Link

def ingest_site_grades():
    """Ingest site_grades.csv"""
    logger.info("Loading site_grades.csv...")
    
    # Adjust path since script is in scripts/ folder
    csv_file = Path(__file__).parent.parent / 'data' / 'site_grades.csv'
    if not csv_file.exists():
        logger.error(f"✗ File not found: {csv_file}")
        return False
    
    session = Session()
    total_inserted = 0
    total_skipped = 0
    batch_size = 1000
    
    try:
        # Get all valid link_ids upfront
        valid_links = set(link.link_id for link in session.query(Link.link_id).all())
        logger.info(f"Found {len(valid_links)} valid links in database")
        
        # Read and process CSV in chunks
        chunk_count = 0
        for chunk in pd.read_csv(csv_file, chunksize=batch_size):
            chunk_count += 1
            logger.info(f"Processing chunk {chunk_count}...")
            
            for _, row in chunk.iterrows():
                try:
                    # Validate link_id exists
                    link_id = int(row['link_id'])
                    if link_id not in valid_links:
                        total_skipped += 1
                        continue
                    
                    # Convert timestamp
                    timestamp = pd.to_datetime(row['timestamp'])
                    
                    # Create record
                    grade = SiteGrade(
                        id=int(row['id']) if pd.notna(row['id']) else None,
                        link_id=link_id,
                        timestamp=timestamp,
                        availability=float(row['availability']) if pd.notna(row['availability']) else None,
                        ib_degradation=float(row['ib_degradation']) if pd.notna(row['ib_degradation']) else None,
                        ob_degradation=float(row['ob_degradation']) if pd.notna(row['ob_degradation']) else None,
                        ib_instability=float(row['ib_instability']) if pd.notna(row['ib_instability']) else None,
                        ob_instability=float(row['ob_instability']) if pd.notna(row['ob_instability']) else None,
                        up_time=float(row['up_time']) if pd.notna(row['up_time']) else None,
                        status=bool(row['status']) if pd.notna(row['status']) else None,
                        performance=float(row['performance']) if pd.notna(row['performance']) else None,
                        congestion=float(row['congestion']) if pd.notna(row['congestion']) else None,
                        latency=float(row['latency']) if pd.notna(row['latency']) else None,
                        grade=float(row['grade'])
                    )
                    session.add(grade)
                    total_inserted += 1
                    
                except Exception as e:
                    logger.warning(f"  Skipping row: {e}")
                    total_skipped += 1
                    continue
            
            # Commit chunk
            try:
                session.commit()
                logger.info(f"  ✓ Chunk {chunk_count}: {total_inserted:,} inserted, {total_skipped:,} skipped")
            except Exception as e:
                logger.error(f"  ✗ Error committing chunk: {e}")
                session.rollback()
                return False
        
        logger.info("")
        logger.info(f"✓ Site Grades ingestion completed successfully")
        logger.info(f"  Total inserted: {total_inserted:,}")
        logger.info(f"  Total skipped: {total_skipped:,}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("STARTING SITE GRADES INGESTION")
    logger.info("=" * 60)
    
    success = ingest_site_grades()
    
    if success:
        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ SITE GRADES INGESTION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
    else:
        logger.error("Site grades ingestion failed")
        exit(1)
