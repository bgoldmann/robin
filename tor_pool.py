"""
Tor Pool Module for Managing Multiple Tor Instances.

This module provides functionality to manage multiple Tor instances
running on different ports for improved performance and load distribution.
"""
import time
import threading
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import requests
from utils import logger
from config import (
    TOR_SOCKS_PORT,
    TOR_MULTI_INSTANCE,
    TOR_INSTANCE_COUNT,
    TOR_INSTANCE_START_PORT
)


class TorPool:
    """
    Manages a pool of Tor instances for load distribution.
    """
    
    def __init__(
        self,
        start_port: int = 9050,
        instance_count: int = 3,
        enabled: bool = False
    ):
        """
        Initialize Tor pool.
        
        Args:
            start_port: Starting port number for Tor instances
            instance_count: Number of Tor instances to manage
            enabled: Whether multi-instance mode is enabled
        """
        self.start_port = start_port
        self.instance_count = instance_count if enabled else 1
        self.enabled = enabled
        self.ports = list(range(start_port, start_port + self.instance_count))
        self.current_index = 0
        self.port_lock = threading.Lock()
        
        # Statistics tracking
        self.port_stats = defaultdict(lambda: {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "last_used": 0,
            "health_status": "unknown"
        })
        
        # Health check results
        self.health_cache = {}
        self.health_cache_timeout = 60  # Cache health for 60 seconds
        self.last_health_check = 0
        
        logger.info(f"TorPool initialized: {self.instance_count} instance(s) on ports {self.ports}")
    
    def get_available_port(self) -> int:
        """
        Get next available Tor port using round-robin.
        
        Returns:
            Port number
        """
        if not self.enabled or self.instance_count == 1:
            return self.start_port
        
        with self.port_lock:
            port = self.ports[self.current_index]
            self.current_index = (self.current_index + 1) % self.instance_count
            self.port_stats[port]["last_used"] = time.time()
            self.port_stats[port]["requests"] += 1
            return port
    
    def get_proxy_for_request(self, prefer_port: Optional[int] = None) -> Dict[str, str]:
        """
        Get proxy configuration for a request.
        
        Args:
            prefer_port: Preferred port (if None, uses round-robin)
            
        Returns:
            Dictionary with proxy settings
        """
        if prefer_port and prefer_port in self.ports:
            port = prefer_port
        else:
            port = self.get_available_port()
        
        return {
            "http": f"socks5h://127.0.0.1:{port}",
            "https": f"socks5h://127.0.0.1:{port}"
        }
    
    def record_success(self, port: int):
        """
        Record successful request for a port.
        
        Args:
            port: Port number
        """
        if port in self.port_stats:
            self.port_stats[port]["successes"] += 1
            self.port_stats[port]["health_status"] = "healthy"
    
    def record_failure(self, port: int):
        """
        Record failed request for a port.
        
        Args:
            port: Port number
        """
        if port in self.port_stats:
            self.port_stats[port]["failures"] += 1
            # Mark as unhealthy if failure rate is high
            total = self.port_stats[port]["requests"]
            if total > 0:
                failure_rate = self.port_stats[port]["failures"] / total
                if failure_rate > 0.5:  # More than 50% failures
                    self.port_stats[port]["health_status"] = "unhealthy"
    
    def health_check_port(self, port: int, timeout: int = 10) -> bool:
        """
        Check health of a specific Tor port.
        
        Args:
            port: Port number to check
            timeout: Timeout for health check
            
        Returns:
            True if port is healthy, False otherwise
        """
        # Check cache first
        cache_key = f"port_{port}"
        if cache_key in self.health_cache:
            cached_time, cached_result = self.health_cache[cache_key]
            if time.time() - cached_time < self.health_cache_timeout:
                return cached_result
        
        try:
            proxies = {
                "http": f"socks5h://127.0.0.1:{port}",
                "https": f"socks5h://127.0.0.1:{port}"
            }
            # Try to connect to a test endpoint through Tor
            response = requests.get(
                "http://check.torproject.org/",
                proxies=proxies,
                timeout=timeout
            )
            is_healthy = response.status_code == 200
            
            # Cache result
            self.health_cache[cache_key] = (time.time(), is_healthy)
            
            if is_healthy:
                self.port_stats[port]["health_status"] = "healthy"
            else:
                self.port_stats[port]["health_status"] = "unhealthy"
            
            return is_healthy
        except Exception as e:
            logger.debug(f"Health check failed for port {port}: {e}")
            self.health_cache[cache_key] = (time.time(), False)
            self.port_stats[port]["health_status"] = "unhealthy"
            return False
    
    def health_check_all(self) -> Dict[int, bool]:
        """
        Check health of all Tor instances.
        
        Returns:
            Dictionary mapping port to health status
        """
        results = {}
        for port in self.ports:
            results[port] = self.health_check_port(port)
        
        self.last_health_check = time.time()
        healthy_count = sum(1 for v in results.values() if v)
        logger.info(f"Health check complete: {healthy_count}/{len(self.ports)} instances healthy")
        
        return results
    
    def get_healthy_ports(self) -> List[int]:
        """
        Get list of currently healthy ports.
        
        Returns:
            List of healthy port numbers
        """
        healthy = []
        for port in self.ports:
            if self.port_stats[port]["health_status"] == "healthy":
                healthy.append(port)
            elif self.port_stats[port]["health_status"] == "unknown":
                # Check if unknown
                if self.health_check_port(port):
                    healthy.append(port)
        
        return healthy if healthy else self.ports  # Fallback to all ports if none healthy
    
    def get_statistics(self) -> Dict[int, Dict[str, any]]:
        """
        Get statistics for all ports.
        
        Returns:
            Dictionary mapping port to statistics
        """
        return dict(self.port_stats)
    
    def rotate_all_circuits(self, controllers: Optional[Dict[int, any]] = None):
        """
        Rotate circuits on all Tor instances (requires controllers).
        
        Args:
            controllers: Dictionary mapping port to TorController instances
        """
        if not controllers:
            logger.warning("No controllers provided for circuit rotation")
            return
        
        rotated = 0
        for port in self.ports:
            if port in controllers:
                controller = controllers[port]
                if controller and controller.rotate_circuit():
                    rotated += 1
        
        logger.info(f"Rotated circuits on {rotated}/{len(self.ports)} instances")


# Global Tor pool instance
_tor_pool: Optional[TorPool] = None


def get_tor_pool() -> TorPool:
    """
    Get or create global Tor pool instance.
    
    Returns:
        TorPool instance
    """
    global _tor_pool
    if _tor_pool is None:
        _tor_pool = TorPool(
            start_port=TOR_INSTANCE_START_PORT,
            instance_count=TOR_INSTANCE_COUNT,
            enabled=TOR_MULTI_INSTANCE
        )
    return _tor_pool


def reset_tor_pool():
    """
    Reset global Tor pool (useful for testing).
    """
    global _tor_pool
    _tor_pool = None
