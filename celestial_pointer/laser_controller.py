"""
Laser controller for turning laser on/off and managing range limits.
"""

import time
import threading
import RPi.GPIO as GPIO
from .config import (
    RELAY_PIN, LASER_MAX_ELEVATION, LASER_MIN_ELEVATION,
    LASER_FLASH_COUNT, LASER_FLASH_DURATION, LASER_FLASH_OFF_DURATION
)


class LaserController:
    """Controls the laser relay and enforces elevation limits."""
    
    def __init__(self, min_elevation=None):
        """
        Initialize laser controller.
        
        Args:
            min_elevation: Minimum elevation angle (degrees). If None, uses default.
        """
        self.min_elevation = min_elevation if min_elevation is not None else LASER_MIN_ELEVATION
        self.max_elevation = LASER_MAX_ELEVATION
        self.laser_on = False
        self.lock = threading.Lock()
        
        # Setup relay pin
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)  # Start with laser OFF
    
    def set_state(self, state):
        """
        Turn laser on or off.
        
        Args:
            state: True to turn on, False to turn off
        """
        with self.lock:
            self.laser_on = state
            # Relay: HIGH = ON, LOW = OFF (based on user's correction)
            GPIO.output(RELAY_PIN, GPIO.HIGH if state else GPIO.LOW)
    
    def turn_on(self):
        """Turn laser on."""
        self.set_state(True)
    
    def turn_off(self):
        """Turn laser off."""
        self.set_state(False)
    
    def toggle(self):
        """Toggle laser state."""
        self.set_state(not self.laser_on)
    
    def is_on(self):
        """Check if laser is currently on."""
        with self.lock:
            return self.laser_on
    
    def check_elevation_range(self, elevation):
        """
        Check if elevation is within allowed range.
        
        Args:
            elevation: Elevation angle in degrees (relative to horizontal plane)
            
        Returns:
            tuple: (is_valid, clamped_elevation)
        """
        clamped = max(self.min_elevation, min(self.max_elevation, elevation))
        is_valid = (self.min_elevation <= elevation <= self.max_elevation)
        return is_valid, clamped
    
    def flash(self, count=None, on_duration=None, off_duration=None):
        """
        Flash the laser a specified number of times.
        
        Args:
            count: Number of flashes (default from config)
            on_duration: Duration laser is on (seconds)
            off_duration: Duration laser is off (seconds)
        """
        if count is None:
            count = LASER_FLASH_COUNT
        if on_duration is None:
            on_duration = LASER_FLASH_DURATION
        if off_duration is None:
            off_duration = LASER_FLASH_OFF_DURATION
        
        was_on = self.is_on()
        
        for _ in range(count):
            self.turn_on()
            time.sleep(on_duration)
            self.turn_off()
            time.sleep(off_duration)
        
        # Restore previous state
        if was_on:
            self.turn_on()
    
    def set_min_elevation(self, min_elevation):
        """
        Set minimum elevation limit.
        
        Args:
            min_elevation: Minimum elevation in degrees
        """
        with self.lock:
            self.min_elevation = min_elevation

