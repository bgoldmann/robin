"""
Tor Controller Module for Circuit Rotation and Management.

This module provides functionality to interact with Tor's control port
for circuit rotation, health checking, and circuit information retrieval.
"""
import time
from typing import Optional, Dict, List, Tuple
from stem import Signal
from stem.control import Controller, CircStatus
from utils import logger, log_tor_circuit_rotation, log_tor_exit_node


class TorController:
    """
    Controller for managing Tor circuits via control port.
    """
    
    def __init__(self, control_port: int = 9051, control_password: Optional[str] = None):
        """
        Initialize Tor controller connection.
        
        Args:
            control_port: Tor control port (default: 9051)
            control_password: Optional password for control port authentication
        """
        self.control_port = control_port
        self.control_password = control_password
        self.controller: Optional[Controller] = None
        self._last_rotation_time = 0
        self._rotation_count = 0
        
    def connect(self) -> bool:
        """
        Connect to Tor control port.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.controller = Controller.from_port(port=self.control_port)
            
            if self.control_password:
                self.controller.authenticate(password=self.control_password)
            else:
                # Try cookie authentication (default)
                self.controller.authenticate()
            
            logger.info(f"Successfully connected to Tor control port {self.control_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Tor control port {self.control_port}: {e}")
            self.controller = None
            return False
    
    def is_connected(self) -> bool:
        """
        Check if controller is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.controller is not None
    
    def rotate_circuit(self) -> bool:
        """
        Rotate Tor circuit by sending NEWNYM signal.
        
        Returns:
            True if rotation successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Cannot rotate circuit: controller not connected")
            return False
        
        try:
            self.controller.signal(Signal.NEWNYM)
            self._last_rotation_time = time.time()
            self._rotation_count += 1
            
            # Get exit node info for logging
            exit_node_info = self.get_exit_node_info()
            exit_node_name = exit_node_info.get("nickname") if exit_node_info else None
            
            log_tor_circuit_rotation(self._rotation_count, exit_node_name)
            
            # Wait a moment for circuit to be established
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"[TOR] Failed to rotate circuit: {e}")
            return False
    
    def get_circuit_info(self) -> List[Dict[str, any]]:
        """
        Get information about current circuits.
        
        Returns:
            List of circuit information dictionaries
        """
        if not self.is_connected():
            return []
        
        try:
            circuits = self.controller.get_circuits()
            circuit_info = []
            
            for circ in circuits:
                if circ.status == CircStatus.BUILT:
                    info = {
                        "id": circ.id,
                        "status": str(circ.status),
                        "path": circ.path,
                        "purpose": circ.purpose,
                    }
                    
                    # Get exit node information if available
                    if circ.path:
                        exit_fingerprint = circ.path[-1][0] if circ.path else None
                        if exit_fingerprint:
                            try:
                                node = self.controller.get_network_status(exit_fingerprint)
                                if node:
                                    exit_node_info = {
                                        "fingerprint": exit_fingerprint,
                                        "nickname": node.nickname,
                                        "address": node.address,
                                        "country": getattr(node, 'country', 'Unknown')
                                    }
                                    info["exit_node"] = exit_node_info
                                    log_tor_exit_node(exit_node_info)
                            except Exception:
                                pass
                    
                    circuit_info.append(info)
            
            return circuit_info
        except Exception as e:
            logger.error(f"Failed to get circuit info: {e}")
            return []
    
    def verify_circuit_health(self) -> bool:
        """
        Verify that at least one healthy circuit exists.
        
        Returns:
            True if healthy circuit exists, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            circuits = self.controller.get_circuits()
            built_circuits = [c for c in circuits if c.status == CircStatus.BUILT]
            
            if built_circuits:
                logger.debug(f"Found {len(built_circuits)} healthy circuit(s)")
                return True
            else:
                logger.warning("No healthy circuits found")
                return False
        except Exception as e:
            logger.error(f"Failed to verify circuit health: {e}")
            return False
    
    def get_exit_node_info(self) -> Optional[Dict[str, str]]:
        """
        Get information about the current exit node.
        
        Returns:
            Dictionary with exit node information or None
        """
        circuits = self.get_circuit_info()
        if circuits and "exit_node" in circuits[0]:
            return circuits[0]["exit_node"]
        return None
    
    def close(self):
        """
        Close the controller connection.
        """
        if self.controller:
            try:
                self.controller.close()
                logger.debug("Tor controller connection closed")
            except Exception as e:
                logger.warning(f"Error closing controller: {e}")
            finally:
                self.controller = None


def init_tor_controller(control_port: int = 9051, control_password: Optional[str] = None) -> Optional[TorController]:
    """
    Initialize and connect to Tor control port.
    
    Args:
        control_port: Tor control port (default: 9051)
        control_password: Optional password for control port authentication
        
    Returns:
        TorController instance if successful, None otherwise
    """
    controller = TorController(control_port=control_port, control_password=control_password)
    if controller.connect():
        return controller
    return None


def rotate_circuit(controller: TorController) -> bool:
    """
    Rotate circuit using provided controller.
    
    Args:
        controller: TorController instance
        
    Returns:
        True if rotation successful, False otherwise
    """
    if controller:
        return controller.rotate_circuit()
    return False


def get_circuit_info(controller: TorController) -> List[Dict[str, any]]:
    """
    Get circuit information from controller.
    
    Args:
        controller: TorController instance
        
    Returns:
        List of circuit information dictionaries
    """
    if controller:
        return controller.get_circuit_info()
    return []


def verify_circuit_health(controller: TorController) -> bool:
    """
    Verify circuit health using controller.
    
    Args:
        controller: TorController instance
        
    Returns:
        True if healthy, False otherwise
    """
    if controller:
        return controller.verify_circuit_health()
    return False
