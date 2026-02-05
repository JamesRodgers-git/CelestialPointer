"""
API server for Celestial Pointer control.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, Tuple, List
from .config import API_HOST, API_PORT, DEFAULT_TARGET, TRACKING_UPDATE_FREQUENCY, TRACKING_ENABLED_BY_DEFAULT, TRACKING_MIN_MOVEMENT_THRESHOLD, USE_DEFAULT_TARGET_ON_STARTUP, SATELLITE_GROUPS, GROUP_TRACKING_STICKY_DURATION
from .target_calculator import TargetCalculator
from .motor_controller import MotorController
from .laser_controller import LaserController
from .display_controller import DisplayController
import math
import threading
import time
import os
import re
import random
import uvicorn

app = FastAPI(title="Celestial Pointer API", version="0.1.0")


# Request models
class OrientationTarget(BaseModel):
    """Target specified as azimuth and elevation."""
    azimuth: float  # degrees (0-360)
    elevation: float  # degrees (-90 to 90)


class StarTarget(BaseModel):
    """Target specified as a star name or HIP number."""
    star_name: str  # Can be a name (e.g., "Sirius") or HIP number (e.g., "HIP32349" or "32349")


class PlanetTarget(BaseModel):
    """Target specified as a planet name."""
    planet_name: str


class SatelliteTarget(BaseModel):
    """Target specified as satellite identifier."""
    satellite_id: str



class LaserToggle(BaseModel):
    """Laser toggle request."""
    state: Optional[bool] = None  # None = toggle, True = on, False = off


class DefaultTarget(BaseModel):
    """Default target specification."""
    target_type: str  # "star", "planet", "satellite", "orientation", "group"
    target_value: Optional[str] = None  # star name, planet name, satellite ID, or "orientation" (not used for "group")
    azimuth: Optional[float] = None  # For orientation type
    elevation: Optional[float] = None  # For orientation type
    groups: Optional[List[Dict[str, Any]]] = None  # For group type: override default groups from config
    min_elevation: Optional[float] = None  # For group type: override minimum elevation


# Global controllers (initialized in main)
target_calculator: Optional[TargetCalculator] = None
motor_controller: Optional[MotorController] = None
laser_controller: Optional[LaserController] = None
display_controller: Optional[DisplayController] = None
current_target: Optional[Dict[str, Any]] = None
default_target: Optional[Dict[str, Any]] = None

# Tracking state
tracking_enabled = TRACKING_ENABLED_BY_DEFAULT
tracking_thread: Optional[threading.Thread] = None
tracking_lock = threading.Lock()
tracking_running = False
group_tracking_active = False  # Whether group tracking mode is active
sticky_target_time = None  # Time when current target was set (for sticky behavior)

# Random tour state
random_tour_active = False  # Whether random tour mode is active
random_tour_thread: Optional[threading.Thread] = None
random_tour_running = False
random_tour_lock = threading.Lock()

# Startup behavior
use_default_on_startup = USE_DEFAULT_TARGET_ON_STARTUP  # Runtime toggleable flag


def initialize_api(calc: TargetCalculator, motor: MotorController,
                   laser: LaserController, display: Optional[DisplayController] = None):
    """Initialize API with controller instances."""
    global target_calculator, motor_controller, laser_controller, display_controller
    global default_target, tracking_thread, current_target
    target_calculator = calc
    motor_controller = motor
    laser_controller = laser
    display_controller = display
    # Set default target from config if specified
    if DEFAULT_TARGET is not None:
        default_target = DEFAULT_TARGET.copy()
    else:
        default_target = None
    
    # Start tracking thread if enabled
    if TRACKING_ENABLED_BY_DEFAULT:
        _start_tracking_thread()
    

    print("\n" + "=" * 60)
    print("Laser HOME CALIBRATION")
    print("=" * 60)
    display_controller.show_message(line1="point laser north...", line2="10 seconds...")
    # turn on laser and move down 45 degrees
    laser_controller.turn_on()
    motor_controller.move_motor2_degrees(45.0, clockwise=None)

    for i in range(10):
        display_controller.show_message(line1="Point north...", line2=f"{10 - i} seconds...")
        time.sleep(1)
    laser_controller.turn_off()
    
    # Reset motor 1 position to 0 (this is now the "north" position)
    motor_controller.reset_motor1_position()
    print("✓ Motor 1 home position set to 0 (north)")
    print("=" * 60 + "\n")


def _update_display():
    """
    Update the display based on current target and status.
    Should be called whenever current_target changes or status changes.
    """
    global display_controller, current_target, laser_controller, tracking_enabled
    
    if display_controller is None or not display_controller.initialized:
        return
    
    if current_target is None:
        display_controller.show_ip_address()
        return
    
    # Check if target is out of range
    elevation = current_target.get("elevation")
    if elevation is not None and laser_controller is not None:
        is_valid, _ = laser_controller.check_elevation_range(elevation)
        if not is_valid:
            display_controller.show_out_of_range()
            return
    
    # Format target name for display
    target_type = current_target.get("type")
    target_name = "Unknown"
    
    if target_type == "star":
        target_name = current_target.get("name", "Unknown Star")
    elif target_type == "planet":
        planet_name = current_target.get("name", "Unknown Planet")
        if planet_name.lower() == "moon":
            target_name = "Moon"
        else:
            target_name = planet_name
    elif target_type == "satellite":
        satellite_id = current_target.get("id", "Unknown")
        satellite_name = current_target.get("satellite_name")
        
        # Try to get name from preloaded satellites if not already set
        if not satellite_name and target_calculator is not None:
            preloaded = target_calculator.get_preloaded_satellites()
            for sat in preloaded:
                if sat.get("norad_id") == str(satellite_id) or sat.get("name", "").upper() == str(satellite_id).upper():
                    satellite_name = sat.get("norad_id")
                    break
        
        # Format display name (prefer name, fallback to ID)
        # if satellite_name:
        #     # Truncate if too long, but try to show name
        #     if len(satellite_name) <= 16:
        #         target_name = satellite_name
        #     else:
        #         target_name = satellite_name[:13] + "..."
        # else:
        target_name = f"Sat {satellite_id}" if len(str(satellite_id)) <= 12 else f"Sat {str(satellite_id)[:9]}..."
    elif target_type == "group":
        satellite_name = current_target.get("satellite_name", "Unknown")
        norad_id = current_target.get("id")
        
        if norad_id:
            target_name = f"Sat {norad_id}" if len(str(norad_id)) <= 12 else f"Sat {str(norad_id)[:9]}..."
        else:
            target_name = "Group Track"
    elif target_type == "orientation":
        azimuth = current_target.get("azimuth", 0)
        elevation = current_target.get("elevation", 0)
        target_name = f"Az:{azimuth:.0f} El:{elevation:.0f}"
    
    # Update display with target name
    # Enable animation if tracking is enabled and target is trackable
    is_trackable = _is_trackable_target(current_target) if current_target else False
    animated = tracking_enabled and is_trackable
    display_controller.show_target(target_name, animated=animated)


def _calculate_default_target_position(default_target: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Calculate azimuth and elevation for a default body specification.
    
    Args:
        default_target: Body specification dictionary
        
    Returns:
        tuple: (azimuth, elevation) or None if calculation fails
    """
    if target_calculator is None:
        return None
    
    target_type = default_target.get("type")
    
    try:
        if target_type == "orientation":
            return (default_target["azimuth"], default_target["elevation"])
        
        elif target_type == "star":
            position = target_calculator.get_star_position(default_target["name"])
            return position
        
        elif target_type == "planet":
            # Check if it's the moon
            if default_target["name"].lower() == "moon":
                position = target_calculator.get_moon_position()
            else:
                position = target_calculator.get_planet_position(default_target["name"])
            return position
        
        elif target_type == "satellite":
            position = target_calculator.get_satellite_position(default_target["id"])
            return position
        
        elif target_type == "group":
            # Find nearest visible satellite from groups
            if laser_controller is None:
                return None
            
            groups = default_target.get("groups", SATELLITE_GROUPS)
            min_elevation = default_target.get("min_elevation")
            if min_elevation is None:
                min_elevation = laser_controller.min_elevation if laser_controller else 0.0
            
            result = target_calculator.find_nearest_visible_satellite(groups, min_elevation=min_elevation)
            if result is not None:
                norad_id, satellite_name, azimuth, elevation = result
                return (azimuth, elevation)
            return None
        
        else:
            return None
    except Exception as e:
        print(f"Error calculating default body position: {e}")
        return None


def _is_trackable_target(target: Optional[Dict[str, Any]]) -> bool:
    """
    Check if a body should be continuously tracked.
    
    Args:
        target: Current body dictionary
        
    Returns:
        bool: True if body should be tracked (moving objects)
    """
    if target is None:
        return False
    
    target_type = target.get("type")
    # Track moving objects: satellites, planets, moon, group targets
    # Don't track static objects: stars, fixed orientations
    trackable_types = ["satellite", "planet", "moon", "group"]
    return target_type in trackable_types


def _recalculate_target_position(target: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Recalculate the current position of a body.
    
    Args:
        target: Body dictionary
        
    Returns:
        tuple: (azimuth, elevation) or None if calculation fails
    """
    if target_calculator is None:
        return None
    
    target_type = target.get("type")
    
    try:
        if target_type == "star":
            return target_calculator.get_star_position(target.get("name"))
        elif target_type == "planet":
            name = target.get("name")
            if name and name.lower() == "moon":
                return target_calculator.get_moon_position()
            else:
                return target_calculator.get_planet_position(name)
        elif target_type == "moon":
            return target_calculator.get_moon_position()
        elif target_type == "satellite":
            return target_calculator.get_satellite_position(target.get("id"))
        elif target_type == "group":
            # Group targets are tracked as satellites using their ID
            return target_calculator.get_satellite_position(target.get("id"))
        elif target_type == "orientation":
            # Fixed orientation, return as-is
            return target.get("azimuth"), target.get("elevation")
    except Exception as e:
        print(f"Error recalculating body position: {e}")
        return None
    
    return None


def _tracking_worker():
    """Background thread that continuously updates body position."""
    global tracking_running, current_target, group_tracking_active, sticky_target_time
    
    while tracking_running:
        with tracking_lock:
            if not tracking_enabled or current_target is None:
                time.sleep(TRACKING_UPDATE_FREQUENCY)
                continue
            
            # Handle group tracking mode with sticky behavior
            if group_tracking_active and current_target.get("type") == "group":
                current_time = time.time()
                
                # Check if sticky duration has elapsed
                if sticky_target_time is not None:
                    elapsed = current_time - sticky_target_time
                    if elapsed >= GROUP_TRACKING_STICKY_DURATION or current_target.get("elevation") < laser_controller.min_elevation:
                        # Recheck for a better body (more directly above)
                        try:
                            groups = current_target.get("groups", SATELLITE_GROUPS)
                            min_elevation = laser_controller.min_elevation if laser_controller else 0.0
                            
                            result = target_calculator.find_nearest_visible_satellite(
                                groups, min_elevation=min_elevation
                            )
                            
                            if result is not None:
                                new_norad_id, new_name, new_azimuth, new_elevation = result
                                
                                # Only switch if new body is significantly better (higher elevation)
                                current_elevation = current_target.get("elevation", -90)
                                if new_elevation > current_elevation + 5.0:  # At least 5 degrees better
                                    # Update to new body
                                    current_target["id"] = new_norad_id
                                    current_target["satellite_name"] = new_name
                                    current_target["azimuth"] = new_azimuth
                                    current_target["elevation"] = new_elevation
                                    sticky_target_time = current_time
                                    print(f"GROUP TRACKING: Switched to better body - {new_name} (NORAD {new_norad_id}) at {new_elevation:.2f}° elevation")
                                else:
                                    # Keep current body, reset sticky timer
                                    sticky_target_time = current_time
                        except Exception as e:
                            print(f"Error rechecking group bodies: {e}")
            
            # Check if target is trackable
            if not _is_trackable_target(current_target):
                time.sleep(TRACKING_UPDATE_FREQUENCY)
                continue
            
            # Recalculate body position
            position = _recalculate_target_position(current_target)
            
            if position is None:
                # Failed to recalculate, wait and try again
                time.sleep(TRACKING_UPDATE_FREQUENCY)
                continue
            
            azimuth, elevation = position
            
            # Update current body with new position
            current_target["azimuth"] = azimuth
            current_target["elevation"] = elevation
            
            # Check if body is below elevation range and output position
            if laser_controller is not None:
                is_valid, _ = laser_controller.check_elevation_range(elevation)
                if not is_valid and elevation < laser_controller.min_elevation:
                    print(f"TRACKING: Body below range - azimuth: {azimuth:.2f}°, elevation: {elevation:.2f}° (min: {laser_controller.min_elevation:.2f}°)")
            
            # Update display (will show out of range if needed)
            _update_display()
            
            # Check if motors are currently moving - skip this update if they are
            if motor_controller is not None and motor_controller.are_motors_moving():
                # Motors are still moving from previous command, skip this update
                time.sleep(TRACKING_UPDATE_FREQUENCY)
                continue
            
            # Point at updated position (without turning on laser if already on)
            try:
                _point_at_body(azimuth, elevation, update_laser=True)
            except Exception as e:
                print(f"Error in tracking update: {e}")
        
        # Sleep for update interval
        time.sleep(TRACKING_UPDATE_FREQUENCY)


def _start_tracking_thread():
    """Start the background tracking thread."""
    global tracking_thread, tracking_running
    
    if tracking_thread is not None and tracking_thread.is_alive():
        return  # Already running
    
    tracking_running = True
    tracking_thread = threading.Thread(target=_tracking_worker, daemon=True)
    tracking_thread.start()


def _stop_tracking_thread():
    """Stop the background tracking thread."""
    global tracking_running, tracking_thread
    
    tracking_running = False
    if tracking_thread is not None:
        tracking_thread.join(timeout=2.0)
        tracking_thread = None


def _point_at_body(azimuth: float, elevation: float, update_laser: bool = True) -> Dict[str, Any]:
    """
    Point the laser at a celestial body.
    
    Args:
        azimuth: Body azimuth in degrees
        elevation: Body elevation in degrees
        
    Returns:
        dict: Result information
    """
    if motor_controller is None or laser_controller is None:
        raise HTTPException(status_code=500, detail="System not initialized")
    
    
    # Calculate relative angles needed
    # Motor 1 controls azimuth (base rotation)
    # Motor 2 controls elevation (Z-axis)
    
    # Check elevation range
    is_valid, clamped_elevation = laser_controller.check_elevation_range(elevation)
    
    if not is_valid:
        laser_controller.turn_off()
        return {
            "status": "out_of_range",
            "message": f"Body elevation {elevation}° is outside allowed range",
            "clamped_elevation": clamped_elevation,
            "laser_flashed": True
        }
    
    # Calculate motor movements needed
    # Motor 1 now uses magnetometer for current angle (via motor_controller.get_motor1_angle())
    current_motor1_angle = motor_controller.get_motor1_angle()
    current_motor2_angle = motor_controller.get_motor2_angle()
    
    # Motor 1: rotate to azimuth
    
    target_motor1_angle = azimuth
    
    motor1_delta = target_motor1_angle - current_motor1_angle
    
    # Normalize to -180 to 180 for shortest path
    while motor1_delta > 180:
        motor1_delta -= 360
    while motor1_delta < -180:
        motor1_delta += 360
    
    # Show body name at the top if available
    body_name = "Unknown"
    if current_target is not None:
        if current_target.get("type") == "satellite":
            satellite_id = current_target.get("id", "Unknown Satellite")
            # Try to get NORAD ID and name
            norad_id = None
            satellite_name = None
            
            # Check if ID is already a NORAD ID (numeric)
            if satellite_id.isdigit():
                norad_id = satellite_id
                # Try to find the name from preloaded satellites
                if target_calculator is not None:
                    preloaded = target_calculator.get_preloaded_satellites()
                    for sat in preloaded:
                        if sat.get("norad_id") == norad_id:
                            satellite_name = sat.get("name")
                            break
            else:
                # ID is a name (like "ISS"), try to find NORAD ID
                if target_calculator is not None:
                    preloaded = target_calculator.get_preloaded_satellites()
                    for sat in preloaded:
                        if sat.get("name", "").upper() == satellite_id.upper() or satellite_id.upper() in sat.get("name", "").upper():
                            norad_id = sat.get("norad_id")
                            satellite_name = sat.get("name")
                            break
            
            # Format display with name and NORAD ID
            if satellite_name and norad_id:
                body_name = f"{satellite_name} (NORAD {norad_id})"
            elif norad_id:
                body_name = f"NORAD {norad_id}"
            else:
                body_name = satellite_id
        elif current_target.get("type") == "star":
            body_name = current_target.get("name", "Unknown Star")
        elif current_target.get("type") == "planet":
            body_name = current_target.get("name", "Unknown Planet")
        elif current_target.get("type") == "moon":
            body_name = "Moon"
        elif current_target.get("type") == "orientation":
            body_name = f"Orientation ({azimuth:.1f}°, {elevation:.1f}°)"
        elif current_target.get("type") == "group":
            satellite_name = current_target.get("satellite_name", "Unknown")
            norad_id = current_target.get("id")
            if norad_id:
                body_name = f"Group: {satellite_name} (NORAD {norad_id})"
            else:
                body_name = f"Group: {satellite_name}"
    
    print(f"BODY: {body_name}")
    print(f"target_motor1_angle: {target_motor1_angle:.2f}°, current_motor1_angle: {current_motor1_angle:.2f}°, motor1_delta: {motor1_delta:.2f}°")
    

    target_motor2_angle = 90.0 - clamped_elevation
    motor2_delta = target_motor2_angle - current_motor2_angle

    print(f"target_motor2_angle: {target_motor2_angle}, current_motor2_angle: {current_motor2_angle}, motor2_delta: {motor2_delta}")
    print("--------------------------------")
    print("--------------------------------")
    # Ensure motor2_angle stays within valid range (0 to 120 degrees)
    # 0 = 90° elevation (up), 120 = -30° elevation (down limit)
    max_motor2_angle = 90.0 - laser_controller.min_elevation  # 90 - (-30) = 120
    if target_motor2_angle < 0:
        target_motor2_angle = 0
        motor2_delta = 0 - current_motor2_angle
    elif target_motor2_angle > max_motor2_angle:
        target_motor2_angle = max_motor2_angle
        motor2_delta = max_motor2_angle - current_motor2_angle
    
    # Move motors (only if movement exceeds threshold)
    # Pass clockwise=None to let the motor controller determine direction from sign of degrees
    if abs(motor1_delta) > TRACKING_MIN_MOVEMENT_THRESHOLD:
        motor_controller.move_motor1_degrees(motor1_delta, clockwise=None)
    
    if abs(motor2_delta) > TRACKING_MIN_MOVEMENT_THRESHOLD:
        motor_controller.move_motor2_degrees(motor2_delta, clockwise=None)
    
    # Turn on laser (only if update_laser is True)
    if update_laser:
        laser_controller.turn_on()
    
    # Update display (will show target name or out of range if needed)
    _update_display()
    
    return {
        "status": "pointing",
        "azimuth": azimuth,
        "elevation": clamped_elevation,
        "motor1_delta": motor1_delta,
        "motor2_delta": motor2_delta
    }


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "Celestial Pointer API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/status")
def get_status():
    """Get current system status."""
    if motor_controller is None or laser_controller is None:
        return {"status": "not_initialized"}
    
    
    with tracking_lock:
        is_trackable = _is_trackable_target(current_target)

    
    return {
        "laser_on": laser_controller.is_on(),
        "current_target": current_target,
        "default_target": default_target,
        "tracking_enabled": tracking_enabled,
        "is_trackable": is_trackable,
        "motor1_angle": motor_controller.get_motor1_angle(),
        "motor2_angle": motor_controller.get_motor2_angle(),
        "elevation_range": {
            "min": laser_controller.min_elevation,
            "max": laser_controller.max_elevation
        }
    }


@app.post("/target/orientation")
def target_orientation(target: OrientationTarget):
    """Point at a body specified by azimuth and elevation."""
    global current_target, group_tracking_active
    
    with tracking_lock:
        group_tracking_active = False  # Disable group tracking when pointing at specific object
        result = _point_at_body(target.azimuth, target.elevation)
        current_target = {
            "type": "orientation",
            "azimuth": target.azimuth,
            "elevation": target.elevation
        }
        _update_display()
    
    return result


@app.post("/target/star")
def target_star(target: StarTarget):
    """Point at a star by name or HIP number (e.g., "Sirius" or "HIP32349" or "32349")."""
    global current_target, group_tracking_active
    
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    position = target_calculator.get_star_position(target.star_name)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Star '{target.star_name}' not found")
    
    azimuth, elevation = position
    
    with tracking_lock:
        group_tracking_active = False  # Disable group tracking when pointing at specific object
        result = _point_at_body(azimuth, elevation)
        
        # Determine if it's a HIP number for the response
        is_hip = target.star_name.strip().upper().startswith('HIP') or target.star_name.strip().isdigit()
        
        current_target = {
            "type": "star",
            "name": target.star_name,
            "hip_number": int(target.star_name.replace("HIP", "").strip()) if is_hip else None,
            "azimuth": azimuth,
            "elevation": elevation
        }
        _update_display()
    
    return result


@app.post("/target/planet")
def target_planet(target: PlanetTarget):
    """Point at a planet by name."""
    global current_target, group_tracking_active
    
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    # Check if it's the moon
    if target.planet_name.lower() == "moon":
        position = target_calculator.get_moon_position()
        target_type = "moon"
    else:
        position = target_calculator.get_planet_position(target.planet_name)
        target_type = "planet"
    
    if position is None:
        raise HTTPException(status_code=404, detail=f"Planet/Moon '{target.planet_name}' not found")
    
    azimuth, elevation = position
    
    with tracking_lock:
        group_tracking_active = False  # Disable group tracking when pointing at specific object
        result = _point_at_body(azimuth, elevation)
        current_target = {
            "type": target_type,
            "name": target.planet_name,
            "azimuth": azimuth,
            "elevation": elevation
        }
        _update_display()
    
    return result


@app.post("/target/satellite")
def target_satellite(target: SatelliteTarget):
    """Point at a satellite by ID (e.g., "ISS" or NORAD ID like "25544")."""
    global current_target, group_tracking_active
    
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    # Use the new get_satellite_position method which handles both ISS and NORAD IDs
    position = target_calculator.get_satellite_position(target.satellite_id)
    
    if position is None:
        raise HTTPException(status_code=503, detail=f"Satellite '{target.satellite_id}' position not available")
    
    azimuth, elevation = position
    
    with tracking_lock:
        group_tracking_active = False  # Disable group tracking when pointing at specific object
        result = _point_at_body(azimuth, elevation)
        current_target = {
            "type": "satellite",
            "id": target.satellite_id,
            "azimuth": azimuth,
            "elevation": elevation
        }
        _update_display()
    
    return result


@app.get("/satellites")
def get_preloaded_satellites(format: Optional[str] = Query(None, description="Output format: 'table' for formatted table, 'json' for JSON (default)")):
    """Get list of all preloaded satellites with their names, pointing information, and current visibility.
    
    Satellites are sorted by elevation with the most visible (highest elevation) at the bottom.
    
    Use ?format=table for a command-line friendly formatted table.
    """
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    satellites = target_calculator.get_preloaded_satellites()
    
    # Format response with visibility information
    result = {
        "count": len(satellites),
        "satellites": [
            {
                "name": sat["name"],
                "norad_id": sat["norad_id"],
                "elevation": round(sat["elevation"], 2) if sat["elevation"] is not None else None,
                "azimuth": round(sat["azimuth"], 2) if sat["azimuth"] is not None else None,
                "visible": sat["elevation"] is not None and sat["elevation"] > 0,
                "endpoint": "/target/satellite",
                "method": "POST",
                "payload": {
                    "satellite_id": sat["id"]
                },
                "example_curl": f'curl -X POST http://localhost:8000/target/satellite -H "Content-Type: application/json" -d \'{{"satellite_id": "{sat["id"]}"}}\''
            }
            for sat in satellites
        ]
    }
    
    # Return formatted table if requested
    if format and format.lower() == "table":
        return _format_satellites_table(result)
    
    return result


def _format_satellites_table(result: Dict[str, Any]) -> Response:
    """Format satellite list as a readable table for command line."""
    satellites = result["satellites"]
    count = result["count"]
    
    # Calculate column widths
    max_name_len = max(len(sat["name"]) for sat in satellites) if satellites else 10
    max_name_len = max(max_name_len, 20)  # Minimum width
    
    # Build table header
    lines = []
    lines.append("=" * 100)
    lines.append(f"PRELOADED SATELLITES ({count} total)")
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"{'Name':<{max_name_len}} {'NORAD ID':<12} {'Elevation':<12} {'Azimuth':<12} {'Status':<10}")
    lines.append("-" * 100)
    
    # Add satellite rows
    visible_count = 0
    for sat in satellites:
        name = sat["name"][:max_name_len] if len(sat["name"]) <= max_name_len else sat["name"][:max_name_len-3] + "..."
        norad_id = sat["norad_id"]
        
        if sat["elevation"] is not None:
            elevation = f"{sat['elevation']:>7.2f}°"
            azimuth = f"{sat['azimuth']:>7.2f}°"
            if sat["visible"]:
                status = "VISIBLE"
                visible_count += 1
            else:
                status = "Below"
        else:
            elevation = "N/A"
            azimuth = "N/A"
            status = "Error"
        
        lines.append(f"{name:<{max_name_len}} {norad_id:<12} {elevation:<12} {azimuth:<12} {status:<10}")
    
    lines.append("-" * 100)
    lines.append(f"Visible above horizon: {visible_count}")
    lines.append("")
    lines.append("To point at a satellite, use:")
    lines.append("  curl -X POST http://localhost:8000/target/satellite \\")
    lines.append("    -H 'Content-Type: application/json' \\")
    lines.append("    -d '{\"satellite_id\": \"<NORAD_ID>\"}'")
    lines.append("")
    lines.append("Example (highest elevation satellite):")
    if satellites:
        # Get the satellite with highest elevation (last in list, sorted by elevation)
        example = satellites[-1]
        elevation_str = f"{example['elevation']:.2f}°" if example['elevation'] is not None else "N/A"
        lines.append(f"  # {example['name']} (Elevation: {elevation_str})")
        lines.append(f"  curl -X POST http://localhost:8000/target/satellite \\")
        lines.append(f"    -H 'Content-Type: application/json' \\")
        lines.append(f"    -d '{{\"satellite_id\": \"{example['norad_id']}\"}}'")
    lines.append("=" * 100)
    
    return Response(content="\n".join(lines), media_type="text/plain")


class GroupTarget(BaseModel):
    """Group tracking target specification."""
    groups: Optional[List[Dict[str, Any]]] = None  # Override default groups from config
    min_elevation: Optional[float] = None  # Override minimum elevation (default: laser min)


@app.post("/target/nearest-group")
def target_nearest_group(target: GroupTarget):
    """Find and track the nearest visible satellite above horizon from configured groups."""
    global current_target, group_tracking_active, sticky_target_time
    
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    if laser_controller is None:
        raise HTTPException(status_code=500, detail="Laser controller not initialized")
    
    # Use provided groups or default from config
    groups = target.groups if target.groups is not None else SATELLITE_GROUPS
    min_elevation = target.min_elevation if target.min_elevation is not None else laser_controller.min_elevation
    
    # Find nearest visible satellite
    result = target_calculator.find_nearest_visible_satellite(groups, min_elevation=min_elevation)
    
    if result is None:
        display_controller.show_message(line1="Waiting for satellite...")
        result = (1, "waiting", 0, -90)

        current_target = {
            "type": "group",
            "id": 1,
            "satellite_name": 1,
            "groups": groups,
            "azimuth": azimuth,
            "elevation": elevation,
            "min_elevation": min_elevation
        }

        result_dict = {
            "status": "pointing",
            "azimuth": azimuth,
            "elevation": elevation,
            "motor1_delta": 0,
            "motor2_delta": 0,
            "group_tracking": True,
            "satellite_id": 1,
            "sticky_duration": GROUP_TRACKING_STICKY_DURATION
        }

        _update_display()

        return result_dict
        
    
    norad_id, satellite_name, azimuth, elevation = result
    
    with tracking_lock:
        # Enable group tracking mode
        group_tracking_active = True
        sticky_target_time = time.time()
        
        # Set current_target before calling _point_at_body so the body name is available
        current_target = {
            "type": "group",
            "id": norad_id,
            "satellite_name": satellite_name,
            "groups": groups,
            "azimuth": azimuth,
            "elevation": elevation,
            "min_elevation": min_elevation
        }
        
        result_dict = _point_at_body(azimuth, elevation)
        
        result_dict["group_tracking"] = True
        result_dict["satellite_id"] = norad_id
        result_dict["sticky_duration"] = GROUP_TRACKING_STICKY_DURATION
        
        # Update display with target name
        _update_display()
    
    return result_dict


@app.post("/detarget")
def detarget():
    """Stop pointing, turn off laser, and stop random tour if active."""
    global current_target, group_tracking_active, sticky_target_time, random_tour_active
    
    if laser_controller is None:
        raise HTTPException(status_code=500, detail="System not initialized")
    
    # Stop random tour if active
    was_random_tour_active = random_tour_active
    if random_tour_active:
        _stop_random_tour()
    
    with tracking_lock:
        laser_controller.turn_off()
        current_target = None
        group_tracking_active = False
        sticky_target_time = None
    
    # Update display to show ready state
    _update_display()
    
    return {
        "status": "detargeted", 
        "laser_off": True,
        "random_tour_stopped": was_random_tour_active
    }


@app.post("/laser/toggle")
def toggle_laser(toggle: Optional[LaserToggle] = None):
    """Toggle laser on/off or set specific state."""
    if laser_controller is None:
        raise HTTPException(status_code=500, detail="System not initialized")
    
    if toggle is None or toggle.state is None:
        laser_controller.toggle()
    else:
        laser_controller.set_state(toggle.state)
    
    return {
        "laser_on": laser_controller.is_on()
    }


@app.get("/laser/status")
def get_laser_status():
    """Get laser status."""
    if laser_controller is None:
        raise HTTPException(status_code=500, detail="System not initialized")
    
    return {
        "laser_on": laser_controller.is_on(),
        "elevation_range": {
            "min": laser_controller.min_elevation,
            "max": laser_controller.max_elevation
        }
    }


@app.post("/default-target")
def set_default_target(target: DefaultTarget):
    """Set the default target."""
    global default_target
    
    # Validate target type
    valid_types = ["star", "planet", "satellite", "orientation", "group"]
    if target.target_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target_type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Validate based on type
    if target.target_type == "orientation":
        if target.azimuth is None or target.elevation is None:
            raise HTTPException(
                status_code=400,
                detail="azimuth and elevation are required for orientation type"
            )
        default_target = {
            "type": "orientation",
            "azimuth": target.azimuth,
            "elevation": target.elevation
        }
    elif target.target_type == "star":
        if not target.target_value:
            raise HTTPException(status_code=400, detail="target_value (star_name) is required")
        default_target = {
            "type": "star",
            "name": target.target_value
        }
    elif target.target_type == "planet":
        if not target.target_value:
            raise HTTPException(status_code=400, detail="target_value (planet_name) is required")
        default_target = {
            "type": "planet",
            "name": target.target_value
        }
    elif target.target_type == "satellite":
        if not target.target_value:
            raise HTTPException(status_code=400, detail="target_value (satellite_id) is required")
        default_target = {
            "type": "satellite",
            "id": target.target_value
        }
    elif target.target_type == "group":
        # For group type, groups and min_elevation are optional (will use config defaults)
        default_target = {
            "type": "group"
        }
        if target.groups is not None:
            default_target["groups"] = target.groups
        if target.min_elevation is not None:
            default_target["min_elevation"] = target.min_elevation
    
    return {
        "status": "default_target_set",
        "default_target": default_target
    }


@app.get("/default-target")
def get_default_target():
    """Get the current default target."""
    global default_target
    return {
        "default_target": default_target,
        "has_default": default_target is not None
    }


@app.delete("/default-target")
def clear_default_target():
    """Clear the default target."""
    global default_target
    default_target = None
    return {
        "status": "default_target_cleared"
    }


class StartupBehavior(BaseModel):
    """Startup behavior configuration."""
    use_default_on_startup: bool  # Whether to use default body on startup


class LocationUpdate(BaseModel):
    """Location update request."""
    latitude: float  # Latitude in degrees (-90 to 90)
    longitude: float  # Longitude in degrees (-180 to 180)
    altitude: Optional[float] = None  # Altitude in meters (optional)


@app.get("/startup-behavior")
def get_startup_behavior():
    """Get the current startup behavior setting."""
    global use_default_on_startup
    return {
        "use_default_on_startup": use_default_on_startup,
        "has_default_target": default_target is not None,
        "default_target": default_target
    }


@app.post("/startup-behavior")
def set_startup_behavior(behavior: StartupBehavior):
    """Set whether to use default body on startup."""
    global use_default_on_startup
    use_default_on_startup = behavior.use_default_on_startup
    return {
        "status": "startup_behavior_updated",
        "use_default_on_startup": use_default_on_startup
    }


def _update_config_file(latitude: float, longitude: float, altitude: Optional[float] = None):
    """
    Update latitude and longitude in config.py file.
    
    Args:
        latitude: New latitude value
        longitude: New longitude value
        altitude: New altitude value (optional)
    """
    # config.py is in the same directory as api.py
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Update latitude
        content = re.sub(
            r'(OBSERVER_LATITUDE\s*=\s*)[-+]?\d*\.?\d+',
            f'\\g<1>{latitude}',
            content
        )
        
        # Update longitude
        content = re.sub(
            r'(OBSERVER_LONGITUDE\s*=\s*)[-+]?\d*\.?\d+',
            f'\\g<1>{longitude}',
            content
        )
        
        # Update altitude if provided
        if altitude is not None:
            content = re.sub(
                r'(OBSERVER_ALTITUDE\s*=\s*)[-+]?\d*\.?\d+',
                f'\\g<1>{altitude}',
                content
            )
        
        with open(config_path, 'w') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error updating config file: {e}")
        return False


@app.post("/location")
def update_location(location: LocationUpdate):
    """Update observer location (latitude, longitude, and optionally altitude)."""
    global target_calculator, current_target
    
    # Validate latitude and longitude ranges
    if not -90 <= location.latitude <= 90:
        raise HTTPException(
            status_code=400,
            detail=f"Latitude must be between -90 and 90 degrees, got {location.latitude}"
        )
    
    if not -180 <= location.longitude <= 180:
        raise HTTPException(
            status_code=400,
            detail=f"Longitude must be between -180 and 180 degrees, got {location.longitude}"
        )
    
    # Check if device is currently targeting something
    with tracking_lock:
        if current_target is not None:
            raise HTTPException(
                status_code=409,
                detail="Cannot update location while device is targeting a body. Please detarget first."
            )
    
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    # Update location in target calculator
    try:
        target_calculator.update_location(
            location.latitude,
            location.longitude,
            location.altitude
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating location in target calculator: {str(e)}"
        )
    
    # Save to config file
    if not _update_config_file(location.latitude, location.longitude, location.altitude):
        # Location was updated in calculator but config save failed
        # This is not critical, but we should warn
        print(f"Warning: Location updated in calculator but failed to save to config file")
    
    return {
        "status": "location_updated",
        "latitude": location.latitude,
        "longitude": location.longitude,
        "altitude": location.altitude if location.altitude is not None else target_calculator.altitude
    }


@app.get("/location")
def get_location():
    """Get current observer location."""
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    return {
        "latitude": target_calculator.latitude,
        "longitude": target_calculator.longitude,
        "altitude": target_calculator.altitude
    }


@app.post("/target/default")
def target_default():
    """Point at the default body."""
    global current_target, default_target
    
    if default_target is None:
        raise HTTPException(status_code=404, detail="No default target set")
    
    # Route to appropriate target handler based on type
    target_type = default_target.get("type")
    
    if target_type == "orientation":
        result = _point_at_body(default_target["azimuth"], default_target["elevation"])
        current_target = {
            "type": "orientation",
            "azimuth": default_target["azimuth"],
            "elevation": default_target["elevation"],
            "source": "default"
        }
        _update_display()
        return result
    
    elif target_type == "star":
        if target_calculator is None:
            raise HTTPException(status_code=500, detail="Target calculator not initialized")
        position = target_calculator.get_star_position(default_target["name"])
        if position is None:
            raise HTTPException(status_code=404, detail=f"Star '{default_target['name']}' not found")
        azimuth, elevation = position
        result = _point_at_body(azimuth, elevation)
        current_target = {
            "type": "star",
            "name": default_target["name"],
            "azimuth": azimuth,
            "elevation": elevation,
            "source": "default"
        }
        _update_display()
        return result
    
    elif target_type == "planet":
        if target_calculator is None:
            raise HTTPException(status_code=500, detail="Target calculator not initialized")
        # Check if it's the moon
        if default_target["name"].lower() == "moon":
            position = target_calculator.get_moon_position()
            target_type_actual = "moon"
        else:
            position = target_calculator.get_planet_position(default_target["name"])
            target_type_actual = "planet"
        if position is None:
            raise HTTPException(status_code=404, detail=f"Planet/Moon '{default_target['name']}' not found")
        azimuth, elevation = position
        result = _point_at_body(azimuth, elevation)
        current_target = {
            "type": target_type_actual,
            "name": default_target["name"],
            "azimuth": azimuth,
            "elevation": elevation,
            "source": "default"
        }
        _update_display()
        return result
    
    elif target_type == "satellite":
        if target_calculator is None:
            raise HTTPException(status_code=500, detail="Target calculator not initialized")
        position = target_calculator.get_satellite_position(default_target["id"])
        if position is None:
            raise HTTPException(status_code=503, detail=f"Satellite '{default_target['id']}' position not available")
        azimuth, elevation = position
        result = _point_at_body(azimuth, elevation)
        current_target = {
            "type": "satellite",
            "id": default_target["id"],
            "azimuth": azimuth,
            "elevation": elevation,
            "source": "default"
        }
        _update_display()
        return result
    
    elif target_type == "group":
        # Use the same logic as /target/nearest-group endpoint
        global group_tracking_active, sticky_target_time
        
        if target_calculator is None:
            raise HTTPException(status_code=500, detail="Target calculator not initialized")
        
        if laser_controller is None:
            raise HTTPException(status_code=500, detail="Laser controller not initialized")
        
        # Use provided groups or default from config
        groups = default_target.get("groups", SATELLITE_GROUPS)
        min_elevation = default_target.get("min_elevation")
        if min_elevation is None:
            min_elevation = laser_controller.min_elevation if laser_controller else 0.0
        
        # Find nearest visible satellite
        result = target_calculator.find_nearest_visible_satellite(groups, min_elevation=min_elevation)
        
        if result is None:
            raise HTTPException(
                status_code=404, 
                detail=f"No visible satellites found above {min_elevation}° elevation in configured groups"
            )
        
        norad_id, satellite_name, azimuth, elevation = result
        
        with tracking_lock:
            # Enable group tracking mode
            group_tracking_active = True
            sticky_target_time = time.time()
            
            # Set current_target before calling _point_at_body so the body name is available
            current_target = {
                "type": "group",
                "id": norad_id,
                "satellite_name": satellite_name,
                "groups": groups,
                "azimuth": azimuth,
                "elevation": elevation,
                "min_elevation": min_elevation,
                "source": "default"
            }
            
            result_dict = _point_at_body(azimuth, elevation)
            
            result_dict["group_tracking"] = True
            result_dict["satellite_id"] = norad_id
            result_dict["sticky_duration"] = GROUP_TRACKING_STICKY_DURATION
            
            # Update display with target name
            _update_display()
        
        return result_dict
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown target type: {target_type}")


@app.post("/tracking/enable")
def enable_tracking():
    """Enable continuous body tracking."""
    global tracking_enabled
    
    with tracking_lock:
        tracking_enabled = True
    
    return {"status": "tracking_enabled", "tracking": True}


@app.post("/tracking/disable")
def disable_tracking():
    """Disable continuous body tracking."""
    global tracking_enabled
    
    with tracking_lock:
        tracking_enabled = False
    
    return {"status": "tracking_disabled", "tracking": False}


@app.get("/tracking/status")
def get_tracking_status():
    """Get tracking status."""
    with tracking_lock:
        is_trackable = _is_trackable_target(current_target)
    
    return {
        "tracking_enabled": tracking_enabled,
        "tracking_running": tracking_running,
        "current_target_trackable": is_trackable,
        "update_frequency": TRACKING_UPDATE_FREQUENCY
    }


def _get_visible_targets() -> List[Dict[str, Any]]:
    """
    Get list of visible targets (planets, moon, Polaris, ISS) that are above horizon.
    
    Returns:
        list: List of target dictionaries with 'type', 'name', 'id' (if applicable)
    """
    if target_calculator is None:
        return []
    
    visible_targets = []
    
    # List of planets to check
    planets = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
    
    # Check each planet
    for planet_name in planets:
        try:
            position = target_calculator.get_planet_position(planet_name)
            if position is not None:
                azimuth, elevation = position
                # Only include if above horizon (elevation > 0)
                if elevation > 0:
                    visible_targets.append({
                        "type": "planet",
                        "name": planet_name,
                        "azimuth": azimuth,
                        "elevation": elevation
                    })
        except Exception as e:
            print(f"Error checking planet {planet_name}: {e}")
            continue
    
    # Check Moon
    try:
        moon_position = target_calculator.get_moon_position()
        if moon_position is not None:
            azimuth, elevation = moon_position
            if elevation > 0:
                visible_targets.append({
                    "type": "moon",
                    "name": "Moon",
                    "azimuth": azimuth,
                    "elevation": elevation
                })
    except Exception as e:
        print(f"Error checking Moon: {e}")
    
    # Check Polaris (North Star)
    try:
        polaris_position = target_calculator.get_star_position("Polaris")
        if polaris_position is not None:
            azimuth, elevation = polaris_position
            if elevation > 0:
                visible_targets.append({
                    "type": "star",
                    "name": "Polaris",
                    "azimuth": azimuth,
                    "elevation": elevation
                })
    except Exception as e:
        print(f"Error checking Polaris: {e}")
    
    # Check ISS
    try:
        iss_position = target_calculator.get_iss_position()
        if iss_position is not None:
            azimuth, elevation = iss_position
            if elevation > 0:
                visible_targets.append({
                    "type": "satellite",
                    "name": "ISS",
                    "id": "ISS",
                    "azimuth": azimuth,
                    "elevation": elevation
                })
    except Exception as e:
        print(f"Error checking ISS: {e}")
    
    return visible_targets


def _random_tour_worker():
    """Background thread that randomly selects and changes targets."""
    global random_tour_running, current_target, group_tracking_active, sticky_target_time
    
    while random_tour_running:
        try:
            # Get visible targets
            visible_targets = _get_visible_targets()
            
            if not visible_targets:
                print("RANDOM TOUR: No visible targets found, waiting...")
                time.sleep(GROUP_TRACKING_STICKY_DURATION)
                continue
            
            # Randomly select a target
            selected_target = random.choice(visible_targets)
            
            target_type = selected_target["type"]
            target_name = selected_target["name"]
            azimuth = selected_target["azimuth"]
            elevation = selected_target["elevation"]
            
            print(f"RANDOM TOUR: Selected {target_name} ({target_type}) at {azimuth:.2f}°, {elevation:.2f}°")
            
            # Point at the selected target
            with tracking_lock:
                group_tracking_active = False  # Disable group tracking in random tour mode
                
                # Set current_target based on type
                if target_type == "planet":
                    current_target = {
                        "type": "planet",
                        "name": target_name,
                        "azimuth": azimuth,
                        "elevation": elevation,
                        "source": "random_tour"
                    }
                elif target_type == "moon":
                    current_target = {
                        "type": "moon",
                        "name": "Moon",
                        "azimuth": azimuth,
                        "elevation": elevation,
                        "source": "random_tour"
                    }
                elif target_type == "star":
                    current_target = {
                        "type": "star",
                        "name": target_name,
                        "azimuth": azimuth,
                        "elevation": elevation,
                        "source": "random_tour"
                    }
                elif target_type == "satellite":
                    current_target = {
                        "type": "satellite",
                        "id": selected_target.get("id", "ISS"),
                        "name": target_name,
                        "satellite_name": target_name,  # For display compatibility
                        "azimuth": azimuth,
                        "elevation": elevation,
                        "source": "random_tour"
                    }
                
                # Point at the target
                try:
                    _point_at_body(azimuth, elevation)
                    # Update display with target name
                    _update_display()
                    print(f"RANDOM TOUR: Now pointing at {target_name}")
                except Exception as e:
                    print(f"RANDOM TOUR: Error pointing at {target_name}: {e}")
            
            # Wait for sticky duration before changing to next target
            time.sleep(GROUP_TRACKING_STICKY_DURATION)
            
        except Exception as e:
            print(f"Error in random tour worker: {e}")
            time.sleep(5.0)  # Wait a bit before retrying


def _start_random_tour():
    """Start the random tour thread."""
    global random_tour_thread, random_tour_running, random_tour_active
    
    if random_tour_thread is not None and random_tour_thread.is_alive():
        return  # Already running
    
    random_tour_active = True
    random_tour_running = True
    random_tour_thread = threading.Thread(target=_random_tour_worker, daemon=True)
    random_tour_thread.start()
    print("Random tour started")


def _stop_random_tour():
    """Stop the random tour thread."""
    global random_tour_running, random_tour_thread, random_tour_active
    
    random_tour_active = False
    random_tour_running = False
    if random_tour_thread is not None:
        random_tour_thread.join(timeout=2.0)
        random_tour_thread = None
    print("Random tour stopped")


@app.post("/target/random-tour")
def start_random_tour():
    """Start random tour mode - randomly cycles through visible planets, moon, Polaris, and ISS.
    
    Changes targets every GROUP_TRACKING_STICKY_DURATION seconds.
    """
    global random_tour_active
    
    if target_calculator is None:
        raise HTTPException(status_code=500, detail="Target calculator not initialized")
    
    if random_tour_active:
        return {
            "status": "already_running",
            "message": "Random tour is already active"
        }
    
    # Get visible targets first to verify we have options
    visible_targets = _get_visible_targets()
    if not visible_targets:
        raise HTTPException(
            status_code=404,
            detail="No visible targets found. Cannot start random tour."
        )
    
    # Start the random tour
    _start_random_tour()
    
    return {
        "status": "random_tour_started",
        "visible_targets_count": len(visible_targets),
        "sticky_duration": GROUP_TRACKING_STICKY_DURATION,
        "targets": [{"name": t["name"], "type": t["type"]} for t in visible_targets]
    }


@app.post("/target/random-tour/stop")
def stop_random_tour():
    """Stop random tour mode."""
    global random_tour_active
    
    if not random_tour_active:
        return {
            "status": "not_running",
            "message": "Random tour is not active"
        }
    
    _stop_random_tour()
    
    return {
        "status": "random_tour_stopped"
    }


@app.get("/target/random-tour/status")
def get_random_tour_status():
    """Get random tour status."""
    visible_targets = _get_visible_targets() if target_calculator is not None else []
    
    return {
        "active": random_tour_active,
        "visible_targets_count": len(visible_targets),
        "sticky_duration": GROUP_TRACKING_STICKY_DURATION,
        "visible_targets": [{"name": t["name"], "type": t["type"]} for t in visible_targets]
    }


@app.on_event("shutdown")
def shutdown_event():
    """Run when API server is shutting down."""
    global laser_controller, display_controller
    
    print("API server shutting down, cleaning up...")
    
    # Turn off laser
    if laser_controller is not None:
        try:
            laser_controller.turn_off()
            print("Laser turned off")
        except Exception as e:
            print(f"Error turning off laser: {e}")
    
    # Clear and close display
    if display_controller is not None:
        try:
            display_controller.clear()
            display_controller.close()
            print("Display cleaned up")
        except Exception as e:
            print(f"Error cleaning up display: {e}")
    
    print("Shutdown cleanup complete")


@app.on_event("startup")
def startup_event():
    """Run after API server starts listening."""
    global default_target, current_target, use_default_on_startup, group_tracking_active, sticky_target_time
    
    # Small delay to ensure server is fully ready
    time.sleep(2.5)
    
    # Point at default body after server is ready (if enabled)
    if use_default_on_startup and default_target is not None:
        target_type = default_target.get("type")
        
        if target_type == "group":
            # For group type, use the same logic as /target/nearest-group
            if target_calculator is None or laser_controller is None:
                print("Warning: Target calculator or laser controller not initialized, cannot point at default group")
                return
            
            groups = default_target.get("groups", SATELLITE_GROUPS)
            min_elevation = default_target.get("min_elevation")
            if min_elevation is None:
                min_elevation = laser_controller.min_elevation if laser_controller else 0.0
            
            result = target_calculator.find_nearest_visible_satellite(groups, min_elevation=min_elevation)
            if result is not None:
                norad_id, satellite_name, azimuth, elevation = result
                print(f"Pointing at default group body after server startup: {satellite_name} (NORAD {norad_id}) at {azimuth:.2f}°, {elevation:.2f}°")
                _point_at_body(azimuth, elevation)
                # Set current_target for tracking
                with tracking_lock:
                    group_tracking_active = True
                    sticky_target_time = time.time()
                    current_target = {
                        "type": "group",
                        "id": norad_id,
                        "satellite_name": satellite_name,
                        "groups": groups,
                        "azimuth": azimuth,
                        "elevation": elevation,
                        "min_elevation": min_elevation,
                        "source": "default_startup"
                    }
                    _update_display()
            else:
                print(f"Warning: No visible satellites found for default group body")
        else:
            # For other types, use the existing calculation
            position = _calculate_default_target_position(default_target)
            if position is not None:
                azimuth, elevation = position
                print(f"Pointing at default body after server startup: {target_type} at {azimuth:.2f}°, {elevation:.2f}°")
                _point_at_body(azimuth, elevation)
                # Set current_target for tracking
                with tracking_lock:
                    current_target = {
                        "type": target_type,
                        "azimuth": azimuth,
                        "elevation": elevation,
                        "source": "default_startup",
                        **{k: v for k, v in default_target.items() if k != "type"}
                    }
                    _update_display()
            else:
                print(f"Warning: Could not calculate position for default body: {default_target}")
                if target_type == "satellite":
                    print("  This may be due to:")
                    print("  - Network connectivity issues")
                    print("  - Celestrak TLE service temporarily unavailable")
                    print("  - Satellite TLE data not yet loaded")
                    print("  The satellite will be retried when tracking starts or when manually pointed at.")


def run_api():
    """Run the API server."""
    try:
        uvicorn.run(app, host=API_HOST, port=API_PORT)
    except Exception as e:
        print(f"Error running API server: {e}")

    finally:
        # Stop tracking thread on shutdown
        _stop_tracking_thread()
        # Stop random tour thread on shutdown
        _stop_random_tour()

