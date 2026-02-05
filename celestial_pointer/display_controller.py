"""
Display controller for 1602 LCD display on I2C bus.
"""

import time
import threading
import socket
from typing import Optional
from RPLCD.i2c import CharLCD


class DisplayController:
    """Controller for 1602 LCD display on I2C bus."""
    
    def __init__(self, i2c_address: int = 0x27):
        """
        Initialize the display controller.
        
        Args:
            i2c_address: I2C address of the LCD display (default: 0x27)
        """
        self.i2c_address = i2c_address
        self.lcd = None
        self.initialized = False
        
        # Animation state
        self.animation_enabled = False
        self.animation_thread: Optional[threading.Thread] = None
        self.animation_running = False
        self.animation_lock = threading.Lock()
        self.current_line1 = ""
        self.current_line2 = ""
        self.animation_frame = 0
        
        try:
            # Initialize LCD (16 columns, 2 rows, I2C address)
            # Common I2C expander is PCF8574
            self.lcd = CharLCD(
                i2c_expander='PCF8574',
                address=i2c_address,
                port=1,  # I2C port 1 on Raspberry Pi
                cols=16,
                rows=2,
                charmap='A02',
                auto_linebreaks=False,
                backlight_enabled=True
            )
            self.initialized = True
            self.clear()
            print(f"LCD display initialized at I2C address 0x{i2c_address:02x}")
        except ImportError:
            print("Warning: RPLCD library not found. Display functionality will be disabled.")
            print("Install with: pip install RPLCD")
            self.initialized = False
        except Exception as e:
            print(f"Warning: Failed to initialize LCD display: {e}")
            print("Display functionality will be disabled.")
            self.initialized = False
    
    def _write(self, line1: str, line2: str = "", update_cache: bool = True):
        """
        Write text to the display (internal method with error handling).
        
        Args:
            line1: Text for first line (max 16 characters)
            line2: Text for second line (max 16 characters)
            update_cache: Whether to update cached lines for animation
        """
        if not self.initialized or self.lcd is None:
            return
        
        try:
            # Truncate lines to 16 characters and pad if needed
            line1 = line1[:16].ljust(16)
            line2 = line2[:16].ljust(16)
            
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1)
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(line2)
            
            # Update cached lines if requested
            if update_cache:
                with self.animation_lock:
                    self.current_line1 = line1.rstrip()
                    self.current_line2 = line2.rstrip()
        except Exception as e:
            print(f"Error writing to display: {e}")
    
    def _animation_worker(self):
        """Background thread that animates the bottom line."""
        spinner_frames = ["|", "/", "-", "\\"]
        dots_frames = ["", ".", "..", "..."]
        
        while self.animation_running:
            with self.animation_lock:
                if not self.animation_enabled:
                    time.sleep(0.1)
                    continue
                
                # Determine animation based on line 1 content
                line1 = self.current_line1.strip() if self.current_line1 else ""
                
                # Check for booting first (case-insensitive, exact match preferred)
                if line1.lower() == "booting" or (line1 and "booting" in line1.lower() and "tracking" not in line1.lower()):
                    # Animated dots for booting
                    frame_idx = self.animation_frame % len(dots_frames)
                    animated_line2 = dots_frames[frame_idx].center(16)
                elif line1 and line1.lower() != "ready" and line1.lower() != "out of range":  # Has a target (tracking)
                    # Spinner animation for tracking
                    frame_idx = self.animation_frame % len(spinner_frames)
                    animated_line2 = f"Tracking {spinner_frames[frame_idx]}".center(16)
                else:
                    animated_line2 = "".center(16)
                
                # Write to display (don't update cache to avoid recursion)
                try:
                    display_line1 = self.current_line1[:16].ljust(16) if self.current_line1 else "".ljust(16)
                    self.lcd.cursor_pos = (0, 0)
                    self.lcd.write_string(display_line1)
                    self.lcd.cursor_pos = (1, 0)
                    self.lcd.write_string(animated_line2)
                except Exception as e:
                    print(f"Error in animation: {e}")
                
                self.animation_frame += 1
            
            time.sleep(0.3)  # Update animation every 300ms
    
    def _start_animation(self):
        """Start the animation thread if not already running."""
        if self.animation_running:
            return
        
        self.animation_running = True
        self.animation_thread = threading.Thread(target=self._animation_worker, daemon=True)
        self.animation_thread.start()
    
    def _stop_animation(self):
        """Stop the animation."""
        with self.animation_lock:
            self.animation_enabled = False
        self.animation_running = False
        if self.animation_thread is not None:
            self.animation_thread.join(timeout=1.0)
            self.animation_thread = None
    
    def clear(self):
        """Clear the display."""
        if not self.initialized or self.lcd is None:
            return
        
        try:
            self.lcd.clear()
            with self.animation_lock:
                self.current_line1 = ""
                self.current_line2 = ""
        except Exception as e:
            print(f"Error clearing display: {e}")
    
    def show_booting(self, animated: bool = True):
        """
        Display 'booting' message.
        
        Args:
            animated: Whether to show animation on bottom line
        """
        with self.animation_lock:
            self.current_line1 = "Booting"
            self.current_line2 = ""
            self.animation_enabled = animated
        
        if animated:
            self._start_animation()
        else:
            self._write("Booting", "")
    
    def show_ip_address(self, duration: float = 5.0):
        """
        Display the Raspberry Pi's IP address.
        
        Args:
            duration: How long to show the IP address in seconds
        """
        ip_address = self._get_ip_address()
        if not ip_address:
            ip_address = "No Network"
        
        # Format for display - IP addresses can be long, so we might need to split
        # Try to fit on one line first
        if len(ip_address) <= 16:
            line1 = ip_address
            line2 = "Ready"
        else:
            # Split across two lines if needed
            line1 = ip_address[:16]
            line2 = ip_address[16:32] if len(ip_address) > 16 else ""
        
        with self.animation_lock:
            self.animation_enabled = False
            self.current_line1 = line1
            self.current_line2 = line2
        self._write(line1, line2)
        
        # Keep it displayed for the specified duration
        time.sleep(duration)
    
    def _get_ip_address(self) -> Optional[str]:
        """
        Get the Raspberry Pi's IP address.
        Returns the first non-loopback IPv4 address found.
        """
        try:
            # Connect to a remote address to determine the active interface
            # This doesn't actually send data, just determines the route
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Connect to a public DNS server (doesn't actually connect)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                # Fallback: try to get IP from hostname
                ip = socket.gethostbyname(socket.gethostname())
            finally:
                s.close()
            
            # Filter out loopback addresses
            if ip and ip != '127.0.0.1':
                return ip
            
            # If we got loopback, try alternative method
            import subprocess
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                for ip in ips:
                    if ip and ip != '127.0.0.1' and ':' not in ip:  # Exclude IPv6 and loopback
                        return ip
            
            return None
        except Exception as e:
            print(f"Error getting IP address: {e}")
            return None
    
    def show_ready(self):
        """Display 'ready' message."""
        with self.animation_lock:
            self.animation_enabled = False
            self.current_line1 = "Ready"
            self.current_line2 = ""
        self._write("Ready", "")
    
    def show_target(self, target_name: str, animated: bool = True):
        """
        Display target name.
        
        Args:
            target_name: Name of the target to display
            animated: Whether to show animation on bottom line during tracking
        """
        # Truncate if too long
        if len(target_name) > 16:
            target_name = target_name[:13] + "..."
        
        with self.animation_lock:
            self.current_line1 = target_name
            self.current_line2 = ""
            self.animation_enabled = animated
        
        if animated:
            self._start_animation()
        else:
            self._write(target_name, "")
    
    def show_out_of_range(self):
        """Display 'out of range' message."""
        with self.animation_lock:
            self.animation_enabled = False
            self.current_line1 = "Out of Range"
            self.current_line2 = ""
        self._write("Out of Range", "")
    
    def show_message(self, line1: str, line2: str = "", animated: bool = False):
        """
        Display a custom two-line message.
        
        Args:
            line1: First line text (max 16 characters)
            line2: Second line text (max 16 characters)
            animated: Whether to show animation on bottom line
        """
        with self.animation_lock:
            self.current_line1 = line1
            self.current_line2 = line2
            self.animation_enabled = animated
        
        if animated:
            self._start_animation()
        else:
            self._write(line1, line2)
    
    def close(self):
        """Close and cleanup the display."""
        self._stop_animation()
        if self.initialized and self.lcd is not None:
            try:
                self.lcd.close(clear=True)
            except Exception as e:
                print(f"Error closing display: {e}")

