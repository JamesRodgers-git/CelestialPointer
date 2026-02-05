"""
Configuration constants for the Celestial Pointer project.
"""


# GPIO Pin Configuration (BCM numbering)
# Motor 1: Base rotation (physical pins 32, 36, 38, 40)
MOTOR1_PINS = [12, 16, 20, 21]  # GPIO pins for IN1, IN2, IN3, IN4

# Motor 2: Laser z-plane movement (physical pins 29, 31, 33, 35)
MOTOR2_PINS = [5, 6, 13, 19]  # GPIO pins for IN1, IN2, IN3, IN4

# Relay: physical pin 11 = GPIO 17
RELAY_PIN = 17

# IMU: GY9250 (MPU9250)
IMU_SCL_PIN = 5  # Physical pin 5
IMU_SDA_PIN = 3  # Physical pin 3
IMU_I2C_ADDRESS = 0x68  # Default MPU9250 address


# Laser Z stop button: physical pin 8 = GPIO 14
BUTTON_PIN = 14

# Motor Specifications
# 28BYJ-48 + ULN2003
# The RpiMotorLib library performs full sequences internally, so:
# 512 steps = 1 full rotation of external motor shaft (after 64:1 internal gear reduction)
# This is independent of step type (full/half/wave)
MOTOR_STEPS_PER_REVOLUTION = 512  # Steps per external motor shaft revolution
MOTOR_DEGREES_PER_STEP = 360.0 / MOTOR_STEPS_PER_REVOLUTION  # 0.703125 degrees per step

# Gear Specifications
GEAR_MODULE = 1.5  # mm
GEAR_BACKLASH = 0.2  # mm
GEAR_PRESSURE_ANGLE = 20  # degrees
MOTOR_PINION_TEETH = 20
LASER_GEAR_TEETH = 14

# Motor Gear Ratios
# Gear ratio = output_rotation / motor_shaft_rotation
# For example: if motor rotates 2x for 1x output rotation, ratio = 0.5
# If motor rotates 1x for 2x output rotation, ratio = 2.0
MOTOR1_GEAR_RATIO = .6665 / 2  # Motor 1 gear ratio (case rotation). 1.0 = no gearing, <1.0 = reduction, >1.0 = increase
MOTOR2_GEAR_RATIO = 0.645  # 20/14 = 1.4286:1 (motor rotates 1.4286x per laser gear revolution)
MOTOR2_GEAR_OFFSET_STEPS = 12
# Legacy: kept for backward compatibility
GEAR_RATIO = MOTOR2_GEAR_RATIO

# Motor Control Settings
MOTOR_STEP_TYPE = "half"  # "full", "half", "wave"
MOTOR_DEFAULT_DELAY = 0.001  # seconds between steps

# Laser Range Limits (in degrees from IMU plane)
LASER_MAX_ELEVATION = 90.0  # Directly up (degrees)
LASER_MIN_ELEVATION = 20.0  # e.g. 10 degrees below horizontal (default, configurable)
LASER_DEFAULT_MIN_ELEVATION = 20.0

# Calibration Settings
CALIBRATION_BUTTON_DEBOUNCE = 0.05  # seconds
CALIBRATION_STEP_DELAY = 0.01  # seconds (faster for more power during calibration)
CALIBRATION_STEP_TYPE = "half"  # Use full step mode for maximum torque during calibration
LASER_CALIBRATION_STEPS = 128  # Number of steps to move laser up for calibration

# Laser Flash Settings (when body is out of range)
LASER_FLASH_COUNT = 2  # Number of flashes when body below range
LASER_FLASH_DURATION = 0.25  # seconds on
LASER_FLASH_OFF_DURATION = 0.25  # seconds off

# API Settings
API_HOST = "0.0.0.0"  # Listen on all interfaces
API_PORT = 8000

# Observer Location Settings
# Default location (can be overridden via command line arguments or API)
# These values are used if not provided via command line arguments
OBSERVER_LATITUDE = 37.7749  # Default: San Francisco, CA (degrees)
OBSERVER_LONGITUDE = -122.4194  # Default: San Francisco, CA (degrees)
OBSERVER_ALTITUDE = 0.0  # Default altitude in meters

# Body Tracking Settings
TRACKING_UPDATE_FREQUENCY = 2.0  # Update frequency in Hz (updates per second)
TRACKING_ENABLED_BY_DEFAULT = True  # Automatically track moving bodies
TRACKING_MIN_MOVEMENT_THRESHOLD = 0.15  # Minimum degrees of movement before adjusting motors

# Default Target Settings
# Set a default target that can be activated via API
# Format: {"type": "star|planet|satellite|orientation", ...}
# Examples:
#   {"type": "star", "name": "Sirius"}
#   {"type": "planet", "name": "Mars"}
#   {"type": "satellite", "id": "ISS"}
#   {"type": "orientation", "azimuth": 180.0, "elevation": 45.0}
DEFAULT_TARGET = {"type": "satellite", "id": "ISS"}
USE_DEFAULT_TARGET_ON_STARTUP = False  # Set to True to automatically point at default body on startup

# Set default target to a planet
# curl -X POST http://localhost:8000/default-target \
#   -H "Content-Type: application/json" \
#   -d '{
#     "target_type": "planet",
#     "target_value": "Mars"
#   }'

# Star Chart Settings
LOAD_STAR_CHART = True  # Set to False to skip loading star catalog (saves memory and startup time)

# Satellite Group Tracking Settings
# Groups to load from Celestrak for nearest-object tracking
# Format: List of dicts with "group_name" (Celestrak group name) and optional "limit" (max satellites to load)
# Available Celestrak groups: stations, visual, weather, noaa, goes, resource, sarsat, disaster, 
#   dmc, tdrss, argos, iridium, iridium-next, starlink, oneweb, planet, spire, geo, gps-ops, 
#   glonass, galileo, beidou, sbas, nnss, molniya, gnss, engineering, education, amateur, x-comm, 
#   other-comm, satnogs, geodetic, radar, cubesat, other
# Note: "brightest" is not a valid group - use "visual" for brightest/visible satellites
SATELLITE_GROUPS = [
    {"group_name": "stations", "limit": None},  # None = no limit
    {"group_name": "visual", "limit": None},  # Brightest/visible satellites
]

# Sticky body duration for group tracking (seconds)
# After this time, the system will recheck for a better body (more directly above)
GROUP_TRACKING_STICKY_DURATION = 60.0  # seconds

