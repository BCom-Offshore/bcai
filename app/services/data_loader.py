"""
Data Loader Module for BCom Offshore Data Management

This module provides comprehensive data loading capabilities for:
- Entities.csv (Customer, Network, Site, Link, Device hierarchy)
- site_grades.csv (Daily link performance grades)
- KPI JSON files (Device-level metrics: avg, min, max, standard deviation)

Data Structure:
- 1 Customer -> N Networks
- 1 Network -> N Sites (but Site can belong to multiple Networks)
- 1 Site -> N Links (but Link can belong to multiple Sites)
- 1 Link -> N Devices (Antennas/Sensors)
- 1 Device -> N KPI Records (Time-series KPI data)

Files:
- data/Entities.csv: Entity hierarchy (1460 rows of customer/network/site/link/device relationships)
- data/site_grades.csv: Daily performance grades (1379 rows of link grades 1-10)
- data/kpis/{deviceId}.json: KPI metrics for each device (avg, min, max, std dev, count)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple, Set
import pandas as pd
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)


class DataLoader:
    """
    Loads and manages BCom Offshore data from CSV and JSON files.
    
    Provides access to:
    - Entity hierarchy (customers, networks, sites, links, devices)
    - Site grades (link performance scores 1-10)
    - KPI metrics (device-level statistics)
    """

    def __init__(self, data_dir: str = "data"):
        """
        Initialize DataLoader with path to data directory.
        
        Args:
            data_dir: Path to data folder containing Entities.csv, site_grades.csv, and kpis/ subfolder
        
        Raises:
            FileNotFoundError: If required data files don't exist
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        
        self.entities_file = self.data_dir / "Entities.csv"
        self.site_grades_file = self.data_dir / "site_grades.csv"
        self.kpis_dir = self.data_dir / "kpis"
        
        # Verify required files exist
        if not self.entities_file.exists():
            raise FileNotFoundError(f"Entities.csv not found: {self.entities_file}")
        if not self.site_grades_file.exists():
            raise FileNotFoundError(f"site_grades.csv not found: {self.site_grades_file}")
        if not self.kpis_dir.exists():
            raise FileNotFoundError(f"kpis directory not found: {self.kpis_dir}")
        
        # Lazy-loaded cache
        self._entities_df: Optional[pd.DataFrame] = None
        self._site_grades_df: Optional[pd.DataFrame] = None
        self._kpi_cache: Dict[int, List[Dict[str, Any]]] = {}
        
        # Indexed caches for fast lookups
        self._customer_index: Optional[Dict[int, Dict[str, Any]]] = None
        self._network_index: Optional[Dict[int, Dict[str, Any]]] = None
        self._site_index: Optional[Dict[int, Dict[str, Any]]] = None
        self._link_index: Optional[Dict[int, Dict[str, Any]]] = None
        self._device_index: Optional[Dict[int, Dict[str, Any]]] = None
        
        logger.info(f"DataLoader initialized with data directory: {self.data_dir}")

    # ==================== Lazy Loaders ====================

    def _load_entities(self) -> pd.DataFrame:
        """Load Entities.csv (lazy loading)."""
        if self._entities_df is None:
            logger.info("Loading Entities.csv...")
            self._entities_df = pd.read_csv(self.entities_file)
            logger.info(f"Loaded {len(self._entities_df)} entity records")
        return self._entities_df

    def _load_site_grades(self) -> pd.DataFrame:
        """Load site_grades.csv (lazy loading)."""
        if self._site_grades_df is None:
            logger.info("Loading site_grades.csv...")
            self._site_grades_df = pd.read_csv(self.site_grades_file)
            # Parse timestamp column
            self._site_grades_df['timestamp'] = pd.to_datetime(self._site_grades_df['timestamp'])
            logger.info(f"Loaded {len(self._site_grades_df)} site grade records")
        return self._site_grades_df

    # ==================== Customer Data ====================

    def get_all_customers(self) -> List[Dict[str, Any]]:
        """
        Get all unique customers.
        
        Returns:
            List of customer dicts with keys: customerid, customername
        """
        df = self._load_entities()
        customers = df[['customerid', 'customername']].drop_duplicates().to_dict('records')
        return customers

    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get customer details by ID.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Dict with customer info or None if not found
        """
        df = self._load_entities()
        customer_rows = df[df['customerid'] == customer_id][['customerid', 'customername']].drop_duplicates()
        if len(customer_rows) > 0:
            return customer_rows.iloc[0].to_dict()
        return None

    # ==================== Network Data ====================

    def get_networks_by_customer(self, customer_id: int) -> List[Dict[str, Any]]:
        """
        Get all networks for a customer.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            List of network dicts with keys: networkid, networkname, networktype, customerid
        """
        df = self._load_entities()
        networks = df[df['customerid'] == customer_id][
            ['customerid', 'networkid', 'networkname', 'networktype']
        ].drop_duplicates().to_dict('records')
        return networks

    def get_network(self, network_id: int) -> Optional[Dict[str, Any]]:
        """
        Get network details by ID.
        
        Args:
            network_id: Network ID
            
        Returns:
            Dict with network info or None if not found
        """
        df = self._load_entities()
        network_rows = df[df['networkid'] == network_id][
            ['customerid', 'networkid', 'networkname', 'networktype']
        ].drop_duplicates()
        if len(network_rows) > 0:
            return network_rows.iloc[0].to_dict()
        return None

    # ==================== Site Data ====================

    def get_sites_by_network(self, network_id: int) -> List[Dict[str, Any]]:
        """
        Get all sites for a network.
        
        Args:
            network_id: Network ID
            
        Returns:
            List of site dicts with keys: siteid, sitename, sitetype, sitecountry, sitecity, sitelatitude, sitelongitude
        """
        df = self._load_entities()
        sites = df[df['networkid'] == network_id][
            ['siteid', 'sitename', 'sitetype', 'sitecountry', 'sitecity', 'sitelatitude', 'sitelongitude']
        ].drop_duplicates().to_dict('records')
        return sites

    def get_site(self, site_id: int) -> Optional[Dict[str, Any]]:
        """
        Get site details by ID.
        
        Args:
            site_id: Site ID
            
        Returns:
            Dict with site info or None if not found
        """
        df = self._load_entities()
        site_rows = df[df['siteid'] == site_id][
            ['siteid', 'sitename', 'sitetype', 'sitecountry', 'sitecity', 'sitelatitude', 'sitelongitude']
        ].drop_duplicates()
        if len(site_rows) > 0:
            return site_rows.iloc[0].to_dict()
        return None

    def get_sites_by_customer(self, customer_id: int) -> List[Dict[str, Any]]:
        """
        Get all sites for a customer (across all networks).
        
        Args:
            customer_id: Customer ID
            
        Returns:
            List of site dicts
        """
        df = self._load_entities()
        sites = df[df['customerid'] == customer_id][
            ['siteid', 'sitename', 'sitetype', 'sitecountry', 'sitecity', 'sitelatitude', 'sitelongitude']
        ].drop_duplicates().to_dict('records')
        return sites

    # ==================== Link Data ====================

    def get_links_by_site(self, site_id: int) -> List[Dict[str, Any]]:
        """
        Get all links for a site.
        
        Args:
            site_id: Site ID
            
        Returns:
            List of link dicts with keys: linkid, linkname, linktype
        """
        df = self._load_entities()
        links = df[df['siteid'] == site_id][
            ['linkid', 'linkname', 'linktype']
        ].drop_duplicates().to_dict('records')
        return links

    def get_link(self, link_id: int) -> Optional[Dict[str, Any]]:
        """
        Get link details by ID.
        
        Args:
            link_id: Link ID
            
        Returns:
            Dict with link info or None if not found
        """
        df = self._load_entities()
        link_rows = df[df['linkid'] == link_id][
            ['linkid', 'linkname', 'linktype']
        ].drop_duplicates()
        if len(link_rows) > 0:
            return link_rows.iloc[0].to_dict()
        return None

    def get_links_by_customer(self, customer_id: int) -> List[Dict[str, Any]]:
        """
        Get all links for a customer (across all networks/sites).
        
        Args:
            customer_id: Customer ID
            
        Returns:
            List of link dicts
        """
        df = self._load_entities()
        links = df[df['customerid'] == customer_id][
            ['linkid', 'linkname', 'linktype']
        ].drop_duplicates().to_dict('records')
        return links

    # ==================== Device Data ====================

    def get_devices_by_link(self, link_id: int) -> List[Dict[str, Any]]:
        """
        Get all devices (antennas/sensors) for a link.
        
        Args:
            link_id: Link ID
            
        Returns:
            List of device dicts with keys: deviceid, deviceapi, deviceapiid, devicesource
        """
        df = self._load_entities()
        devices = df[df['linkid'] == link_id][
            ['deviceid', 'deviceapi', 'deviceapiid', 'devicesource']
        ].drop_duplicates().to_dict('records')
        return devices

    def get_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get device details by ID.
        
        Args:
            device_id: Device ID
            
        Returns:
            Dict with device info or None if not found
        """
        df = self._load_entities()
        device_rows = df[df['deviceid'] == device_id][
            ['deviceid', 'deviceapi', 'deviceapiid', 'devicesource']
        ].drop_duplicates()
        if len(device_rows) > 0:
            return device_rows.iloc[0].to_dict()
        return None

    def get_devices_by_customer(self, customer_id: int) -> List[Dict[str, Any]]:
        """
        Get all devices for a customer.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            List of device dicts
        """
        df = self._load_entities()
        devices = df[df['customerid'] == customer_id][
            ['deviceid', 'deviceapi', 'deviceapiid', 'devicesource']
        ].drop_duplicates().to_dict('records')
        return devices

    # ==================== Site Grades (Link Performance) ====================

    def get_link_grades(self, link_id: int, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all grades for a link.
        
        Args:
            link_id: Link ID
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            
        Returns:
            List of grade records with keys: id, link_id, timestamp, availability, 
            ib_degradation, ob_degradation, ib_instability, ob_instability, 
            up_time, status, performance, congestion, latency, grade (1-10)
        """
        df = self._load_site_grades()
        grades = df[df['link_id'] == link_id].copy()
        
        if start_date:
            start = pd.to_datetime(start_date)
            grades = grades[grades['timestamp'] >= start]
        
        if end_date:
            end = pd.to_datetime(end_date)
            grades = grades[grades['timestamp'] <= end]
        
        return grades.to_dict('records')

    def get_latest_grade(self, link_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the most recent grade for a link.
        
        Args:
            link_id: Link ID
            
        Returns:
            Latest grade record or None if not found
        """
        df = self._load_site_grades()
        grades = df[df['link_id'] == link_id].sort_values('timestamp', ascending=False)
        if len(grades) > 0:
            return grades.iloc[0].to_dict()
        return None

    def get_site_grades_by_customer(self, customer_id: int) -> pd.DataFrame:
        """
        Get all grades for a customer's links.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            DataFrame of grade records
        """
        # Get all links for customer
        links = self.get_links_by_customer(customer_id)
        link_ids = [link['linkid'] for link in links]
        
        # Get grades for those links
        df = self._load_site_grades()
        return df[df['link_id'].isin(link_ids)]

    # ==================== KPI Data (Device Metrics) ====================

    def get_device_kpis(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Load KPI metrics for a device from JSON file.
        
        Each KPI record contains:
        - apiConnectionChannelId: Channel ID
        - timestamp: ISO format timestamp
        - max, min, avg, StandardDeviation: For numeric metrics
        - data: Dict for categorical metrics (e.g., error counts)
        - totalRawEntries: Number of raw data points
        
        Args:
            device_id: Device ID (matches JSON filename)
            
        Returns:
            List of KPI records or empty list if file not found
        """
        if device_id in self._kpi_cache:
            return self._kpi_cache[device_id]
        
        kpi_file = self.kpis_dir / f"{device_id}.json"
        if not kpi_file.exists():
            logger.warning(f"KPI file not found for device {device_id}")
            return []
        
        try:
            with open(kpi_file, 'r') as f:
                kpis = json.load(f)
            self._kpi_cache[device_id] = kpis
            logger.debug(f"Loaded {len(kpis)} KPI records for device {device_id}")
            return kpis
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading KPI file for device {device_id}: {e}")
            return []

    def get_device_kpi_by_timestamp(self, device_id: int, timestamp: str) -> Optional[Dict[str, Any]]:
        """
        Get KPI record for a device at a specific timestamp.
        
        Args:
            device_id: Device ID
            timestamp: ISO format timestamp (e.g., '2025-09-22T09:00:00.000+00:00')
            
        Returns:
            KPI record or None if not found
        """
        kpis = self.get_device_kpis(device_id)
        for kpi in kpis:
            if kpi.get('timestamp') == timestamp:
                return kpi
        return None

    def get_available_devices_with_kpis(self) -> List[int]:
        """
        Get list of device IDs that have KPI JSON files.
        
        Returns:
            List of device IDs
        """
        json_files = list(self.kpis_dir.glob("*.json"))
        device_ids = [int(f.stem) for f in json_files]
        return sorted(device_ids)

    # ==================== Aggregated Views ====================

    def get_customer_summary(self, customer_id: int) -> Dict[str, Any]:
        """
        Get comprehensive summary of customer data.
        
        Returns:
            Dict with customer info, network count, site count, link count, device count
        """
        customer = self.get_customer(customer_id)
        networks = self.get_networks_by_customer(customer_id)
        sites = self.get_sites_by_customer(customer_id)
        links = self.get_links_by_customer(customer_id)
        devices = self.get_devices_by_customer(customer_id)
        
        return {
            'customer': customer,
            'network_count': len(networks),
            'site_count': len(sites),
            'link_count': len(links),
            'device_count': len(devices),
            'networks': networks,
            'sites': sites,
            'links': links,
            'devices': devices
        }

    def get_link_full_context(self, link_id: int) -> Dict[str, Any]:
        """
        Get full context for a link (hierarchy + grades + device KPIs).
        
        Args:
            link_id: Link ID
            
        Returns:
            Dict with link info, parent site/network, devices, grades, and KPI data
        """
        df = self._load_entities()
        link_rows = df[df['linkid'] == link_id]
        
        if len(link_rows) == 0:
            return {'error': f'Link {link_id} not found'}
        
        # Get hierarchy context from first row
        row = link_rows.iloc[0]
        
        return {
            'link': self.get_link(link_id),
            'site': self.get_site(row['siteid']),
            'network': self.get_network(row['networkid']),
            'customer': self.get_customer(row['customerid']),
            'devices': self.get_devices_by_link(link_id),
            'latest_grade': self.get_latest_grade(link_id),
            'grades_30days': self.get_link_grades(link_id, 
                                                  start_date=(datetime.now() - pd.Timedelta(days=30)).strftime('%Y-%m-%d'))
        }

    def get_network_performance_summary(self, network_id: int) -> Dict[str, Any]:
        """
        Get performance summary for a network.
        
        Args:
            network_id: Network ID
            
        Returns:
            Dict with network info and aggregated performance metrics
        """
        sites = self.get_sites_by_network(network_id)
        site_ids = [site['siteid'] for site in sites]
        
        df = self._load_entities()
        links_in_network = df[df['siteid'].isin(site_ids)][['linkid']].drop_duplicates()
        link_ids = links_in_network['linkid'].tolist()
        
        # Get all grades for links in network
        grades_df = self._load_site_grades()
        network_grades = grades_df[grades_df['link_id'].isin(link_ids)]
        
        return {
            'network': self.get_network(network_id),
            'site_count': len(sites),
            'link_count': len(link_ids),
            'avg_grade': network_grades['grade'].mean() if len(network_grades) > 0 else None,
            'min_grade': network_grades['grade'].min() if len(network_grades) > 0 else None,
            'max_grade': network_grades['grade'].max() if len(network_grades) > 0 else None,
            'latest_timestamp': network_grades['timestamp'].max() if len(network_grades) > 0 else None,
            'record_count': len(network_grades)
        }

    # ==================== Bulk Operations ====================

    def export_customer_data_for_ml(self, customer_id: int) -> pd.DataFrame:
        """
        Export all data for a customer ready for ML processing.
        
        Combines grades with device info for anomaly detection training.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            DataFrame with link grades + device info for ML
        """
        # Get all links for customer
        links = self.get_links_by_customer(customer_id)
        link_ids = [link['linkid'] for link in links]
        
        # Get all grades for those links
        df = self._load_site_grades()
        customer_grades = df[df['link_id'].isin(link_ids)].copy()
        
        # Add link info
        link_dict = {link['linkid']: link for link in links}
        customer_grades['linkinfo'] = customer_grades['link_id'].map(link_dict)
        
        # Add device count per link
        df_entities = self._load_entities()
        device_counts = df_entities[df_entities['linkid'].isin(link_ids)].groupby('linkid')['deviceid'].nunique()
        customer_grades['device_count'] = customer_grades['link_id'].map(device_counts)
        
        return customer_grades

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall dataset statistics.
        
        Returns:
            Dict with counts of entities, grades, and available KPI files
        """
        df_entities = self._load_entities()
        df_grades = self._load_site_grades()
        available_kpis = self.get_available_devices_with_kpis()
        
        return {
            'unique_customers': df_entities['customerid'].nunique(),
            'unique_networks': df_entities['networkid'].nunique(),
            'unique_sites': df_entities['siteid'].nunique(),
            'unique_links': df_entities['linkid'].nunique(),
            'unique_devices': df_entities['deviceid'].nunique(),
            'total_entity_rows': len(df_entities),
            'total_grade_records': len(df_grades),
            'devices_with_kpi_data': len(available_kpis),
            'grade_date_range': {
                'start': df_grades['timestamp'].min().isoformat(),
                'end': df_grades['timestamp'].max().isoformat()
            }
        }


# Singleton instance for easy import
_data_loader_instance: Optional[DataLoader] = None

def get_data_loader(data_dir: str = "data") -> DataLoader:
    """
    Get or create the global DataLoader instance.
    
    Args:
        data_dir: Path to data directory
        
    Returns:
        DataLoader instance
    """
    global _data_loader_instance
    if _data_loader_instance is None:
        _data_loader_instance = DataLoader(data_dir)
    return _data_loader_instance
