#!/usr/bin/env python3
"""
Simple Data Ingestion - Load entities and KPI data into PostgreSQL
Uses savepoints for robust error handling

Note: This script is located in the scripts/ folder, so data paths are relative to the root directory.
"""
import os
import sys
import json
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
from app.models.bcom_models import (
    Customer, Network, Site, Link, Device, KPIData
)

def ingest_entities():
    """Ingest Entities.csv"""
    logger.info("Loading Entities.csv...")
    # Adjust path since script is in scripts/ folder
    data_file = Path(__file__).parent.parent / 'data' / 'Entities.csv'
    df = pd.read_csv(data_file)
    logger.info(f"Loaded {len(df)} rows")
    
    session = Session()
    
    try:
        # Get unique customers, networks, sites, links
        customers_df = df[['customerid', 'customername']].drop_duplicates()
        networks_df = df[['networkid', 'networkname', 'networktype', 'customerid']].drop_duplicates()
        sites_df = df[['siteid', 'sitename', 'sitetype', 'sitecountry', 'sitecity', 'sitelatitude', 'sitelongitude']].drop_duplicates()
        links_df = df[['linkid', 'linkname', 'linktype', 'siteid', 'networkid']].drop_duplicates()
        devices_df = df[['deviceid', 'deviceapi', 'deviceapiid', 'devicesource', 'linkid']].drop_duplicates()
        
        logger.info(f"  Customers: {len(customers_df)}")
        logger.info(f"  Networks: {len(networks_df)}")
        logger.info(f"  Sites: {len(sites_df)}")
        logger.info(f"  Links: {len(links_df)}")
        logger.info(f"  Devices: {len(devices_df)}")
        
        # Insert customers (skip if exists)
        for _, row in customers_df.iterrows():
            existing = session.query(Customer).filter(
                Customer.customer_id == int(row['customerid'])
            ).first()
            if not existing:
                customer = Customer(
                    customer_id=int(row['customerid']),
                    customer_name=row['customername']
                )
                session.add(customer)
        logger.info("✓ Customers inserted")
        session.commit()
        
        # Insert networks
        for _, row in networks_df.iterrows():
            existing = session.query(Network).filter(
                Network.network_id == int(row['networkid'])
            ).first()
            if not existing:
                network = Network(
                    network_id=int(row['networkid']),
                    customer_id=int(row['customerid']),
                    network_name=row['networkname'],
                    network_type=row['networktype']
                )
                session.add(network)
        logger.info("✓ Networks inserted")
        session.commit()
        
        # Insert sites
        for _, row in sites_df.iterrows():
            existing = session.query(Site).filter(
                Site.site_id == int(row['siteid'])
            ).first()
            if not existing:
                site = Site(
                    site_id=int(row['siteid']),
                    site_name=row['sitename'],
                    site_type=row['sitetype'],
                    country=row['sitecountry'],
                    city=row['sitecity'],
                    latitude=float(row['sitelatitude']) if pd.notna(row['sitelatitude']) else None,
                    longitude=float(row['sitelongitude']) if pd.notna(row['sitelongitude']) else None
                )
                session.add(site)
        logger.info("✓ Sites inserted")
        session.commit()
        
        # Insert links
        for _, row in links_df.iterrows():
            existing = session.query(Link).filter(
                Link.link_id == int(row['linkid'])
            ).first()
            if not existing:
                link = Link(
                    link_id=int(row['linkid']),
                    site_id=int(row['siteid']),
                    network_id=int(row['networkid']),
                    link_name=row['linkname'],
                    link_type=row['linktype']
                )
                session.add(link)
        logger.info("✓ Links inserted")
        session.commit()
        
        # Insert devices
        count = 0
        for _, row in devices_df.iterrows():
            existing = session.query(Device).filter(
                Device.device_id == int(row['deviceid'])
            ).first()
            if not existing:
                device = Device(
                    device_id=int(row['deviceid']),
                    link_id=int(row['linkid']),
                    device_api=row['deviceapi'],
                    device_api_id=int(row['deviceapiid']) if pd.notna(row['deviceapiid']) else None,
                    device_source=row['devicesource']
                )
                session.add(device)
                count += 1
                if count % 100 == 0:
                    session.commit()
        session.commit()
        logger.info(f"✓ {count} new Devices inserted")
        
        logger.info("✓ ENTITIES ingestion completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        session.rollback()
        return False
    finally:
        session.close()


def ingest_kpi_data():
    """Ingest KPI JSON files - keyed by link_id, containing data for all devices on that link"""
    # Adjust path since script is in scripts/ folder
    kpis_dir = Path(__file__).parent.parent / 'data' / 'kpis'
    json_files = sorted(kpis_dir.glob('*.json'))
    logger.info(f"Found {len(json_files)} KPI files")
    
    session = Session()
    total_records = 0
    skipped_files = 0
    
    try:
        for json_file in json_files:
            link_id = int(json_file.stem)
            
            # Check if link exists and get all devices on this link
            link = session.query(Link).filter(Link.link_id == link_id).first()
            if not link:
                logger.warning(f"Skipping {json_file.name} - link {link_id} not found")
                skipped_files += 1
                continue
            
            # Get all devices on this link
            devices_on_link = session.query(Device).filter(Device.link_id == link.link_id).all()
            if not devices_on_link:
                logger.warning(f"Skipping {json_file.name} - no devices found for link {link_id}")
                skipped_files += 1
                continue
            
            logger.info(f"Processing {json_file.name} (link_id={link_id}) with {len(devices_on_link)} devices...")
            
            with open(json_file, 'r') as f:
                kpi_records = json.load(f)
            
            logger.info(f"  Loaded {len(kpi_records)} KPI records")
            
            # Insert KPI records for each device on the link
            # The KPI data is shared across all devices on the link
            records_count = 0
            for i, kpi in enumerate(kpi_records):
                timestamp = pd.to_datetime(kpi.get('timestamp'))
                is_numeric = 'avg' in kpi and kpi.get('avg') is not None
                metric_type = 'numeric' if is_numeric else 'categorical'
                
                # Create a KPI record for each device on the link
                for device in devices_on_link:
                    kpi_data = KPIData(
                        device_id=device.device_id,
                        api_connection_channel_id=kpi.get('apiConnectionChannelId'),
                        timestamp=timestamp,
                        metric_type=metric_type,
                        max_value=kpi.get('max'),
                        min_value=kpi.get('min'),
                        avg_value=kpi.get('avg'),
                        std_deviation=kpi.get('StandardDeviation'),
                        total_raw_entries=kpi.get('totalRawEntries'),
                        metric_data=kpi.get('data')
                    )
                    session.add(kpi_data)
                    records_count += 1
                
                # Commit every 1000 KPI records
                if records_count % 1000 == 0:
                    session.commit()
            
            session.commit()
            total_records += records_count
            logger.info(f"✓ Link {link_id}: {len(kpi_records)} timestamps × {len(devices_on_link)} devices = {records_count:,} KPI records")
        
        logger.info(f"✓ KPI ingestion completed: {total_records:,} total records ({skipped_files} skipped files)")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == '__main__':
    logger.info("Starting data ingestion...")
    
    # Ingest entities
    if ingest_entities():
        logger.info("")
        # Ingest KPI data
        if ingest_kpi_data():
            logger.info("")
            logger.info("=" * 60)
            logger.info("✓ ALL INGESTION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
        else:
            logger.error("KPI ingestion failed")
    else:
        logger.error("Entities ingestion failed")
