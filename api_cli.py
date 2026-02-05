#!/usr/bin/env python3
"""
Command-line GUI for Celestial Pointer API.
Allows interactive selection and execution of API endpoints.
"""

import requests
import json
import sys
from typing import Optional, Dict, Any

# Default API configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000
BASE_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_section(text: str):
    """Print a formatted section."""
    print(f"\n--- {text} ---")


def print_response(response: requests.Response):
    """Pretty print API response."""
    try:
        if response.headers.get('content-type', '').startswith('application/json'):
            data = response.json()
            print(json.dumps(data, indent=2))
        else:
            print(response.text)
    except Exception as e:
        print(f"Error formatting response: {e}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")


def get_input(prompt: str, default: Optional[str] = None, input_type: type = str) -> Any:
    """Get user input with optional default value."""
    if default is not None:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    
    while True:
        try:
            value = input(prompt).strip()
            if not value and default is not None:
                return default
            if not value:
                print("This field is required.")
                continue
            if input_type == float:
                return float(value)
            elif input_type == int:
                return int(value)
            elif input_type == bool:
                return value.lower() in ('true', '1', 'yes', 'y', 'on')
            else:
                return value
        except ValueError:
            print(f"Invalid input. Please enter a valid {input_type.__name__}.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return None


def get_optional_input(prompt: str, input_type: type = str) -> Optional[Any]:
    """Get optional user input."""
    prompt = f"{prompt} (press Enter to skip): "
    while True:
        try:
            value = input(prompt).strip()
            if not value:
                return None
            if input_type == float:
                return float(value)
            elif input_type == int:
                return int(value)
            elif input_type == bool:
                return value.lower() in ('true', '1', 'yes', 'y', 'on')
            else:
                return value
        except ValueError:
            print(f"Invalid input. Please enter a valid {input_type.__name__}.")
        except KeyboardInterrupt:
            return None


def call_endpoint(method: str, endpoint: str, data: Optional[Dict] = None) -> requests.Response:
    """Make API call and return response."""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        return response
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Could not connect to API at {url}")
        print("   Make sure the API server is running.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error making request: {e}")
        sys.exit(1)


def show_menu():
    """Display main menu."""
    print_header("Celestial Pointer API CLI")
    print("\nPointing Endpoints:")
    print("  1.  Point at Orientation (azimuth/elevation)")
    print("  2.  Point at Star")
    print("  3.  Point at Planet")
    print("  4.  Point at Satellite")
    print("  5.  Point at Nearest Group")
    print("  6.  Detarget (stop pointing)")
    print("  7.  Start Random Tour")
    print("  8.  Stop Random Tour")
    print("  9.  Get Random Tour Status")
    
    print("\nLaser Control:")
    print("  10. Toggle Laser")
    print("  11. Get Laser Status")
    
    print("\nDefault Target:")
    print("  12. Set Default Target")
    print("  13. Get Default Target")
    print("  14. Clear Default Target")
    print("  15. Point at Default Target")
    
    print("\nStartup Behavior:")
    print("  16. Get Startup Behavior")
    print("  17. Set Startup Behavior")
    
    print("\nLocation:")
    print("  18. Get Location")
    print("  19. Update Location")
    
    print("\nTracking:")
    print("  20. Enable Tracking")
    print("  21. Disable Tracking")
    print("  22. Get Tracking Status")
    
    print("\nInformation:")
    print("  23. Get Status")
    print("  24. Get Satellites List")
    print("  25. Get Root Info")
    
    print("\n  0.  Exit")
    print()


def handle_orientation():
    """Handle orientation endpoint."""
    print_section("Point at Orientation")
    azimuth = get_input("Azimuth (degrees, 0-360)", input_type=float)
    if azimuth is None:
        return
    elevation = get_input("Elevation (degrees, -90 to 90)", input_type=float)
    if elevation is None:
        return
    
    data = {"azimuth": azimuth, "elevation": elevation}
    response = call_endpoint("POST", "/target/orientation", data)
    print_response(response)


def handle_star():
    """Handle star endpoint."""
    print_section("Point at Star")
    star_name = get_input("Star name or HIP number (e.g., 'Sirius' or 'HIP32349')")
    if not star_name:
        return
    
    data = {"star_name": star_name}
    response = call_endpoint("POST", "/target/star", data)
    print_response(response)


def handle_planet():
    """Handle planet endpoint."""
    print_section("Point at Planet")
    planet_name = get_input("Planet name (e.g., 'Mars', 'Jupiter', 'Moon')")
    if not planet_name:
        return
    
    data = {"planet_name": planet_name}
    response = call_endpoint("POST", "/target/planet", data)
    print_response(response)


def handle_satellite():
    """Handle satellite endpoint."""
    print_section("Point at Satellite")
    satellite_id = get_input("Satellite ID (e.g., 'ISS' or NORAD ID like '25544')")
    if not satellite_id:
        return
    
    data = {"satellite_id": satellite_id}
    response = call_endpoint("POST", "/target/satellite", data)
    print_response(response)


def handle_nearest_group():
    """Handle nearest group endpoint."""
    print_section("Point at Nearest Group")
    print("Using default groups from config.")
    print("(Optional: You can override min_elevation)")
    
    min_elevation = get_optional_input("Min elevation (degrees, optional)", input_type=float)
    
    data = {}
    if min_elevation is not None:
        data["min_elevation"] = min_elevation
    
    response = call_endpoint("POST", "/target/nearest-group", data if data else None)
    print_response(response)


def handle_detarget():
    """Handle detarget endpoint."""
    print_section("Detarget")
    confirm = get_input("Stop pointing and turn off laser? (y/n)", default="y", input_type=bool)
    if confirm:
        response = call_endpoint("POST", "/detarget")
        print_response(response)


def handle_random_tour_start():
    """Handle random tour start."""
    print_section("Start Random Tour")
    response = call_endpoint("POST", "/target/random-tour")
    print_response(response)


def handle_random_tour_stop():
    """Handle random tour stop."""
    print_section("Stop Random Tour")
    response = call_endpoint("POST", "/target/random-tour/stop")
    print_response(response)


def handle_random_tour_status():
    """Handle random tour status."""
    print_section("Random Tour Status")
    response = call_endpoint("GET", "/target/random-tour/status")
    print_response(response)


def handle_laser_toggle():
    """Handle laser toggle."""
    print_section("Toggle Laser")
    print("Options:")
    print("  1. Toggle (current state)")
    print("  2. Turn On")
    print("  3. Turn Off")
    choice = get_input("Choice (1-3)", default="1", input_type=int)
    
    if choice == 1:
        data = None  # Toggle
    elif choice == 2:
        data = {"state": True}
    elif choice == 3:
        data = {"state": False}
    else:
        print("Invalid choice.")
        return
    
    response = call_endpoint("POST", "/laser/toggle", data)
    print_response(response)


def handle_laser_status():
    """Handle laser status."""
    print_section("Laser Status")
    response = call_endpoint("GET", "/laser/status")
    print_response(response)


def handle_set_default_target():
    """Handle set default target."""
    print_section("Set Default Target")
    print("Target types: star, planet, satellite, orientation, group")
    target_type = get_input("Target type")
    if not target_type:
        return
    
    data = {"target_type": target_type}
    
    if target_type == "orientation":
        azimuth = get_input("Azimuth (degrees)", input_type=float)
        elevation = get_input("Elevation (degrees)", input_type=float)
        if azimuth is None or elevation is None:
            return
        data["azimuth"] = azimuth
        data["elevation"] = elevation
    elif target_type in ["star", "planet", "satellite"]:
        target_value = get_input(f"{target_type.capitalize()} name/ID")
        if not target_value:
            return
        data["target_value"] = target_value
    elif target_type == "group":
        print("Group type uses default groups from config.")
        min_elevation = get_optional_input("Min elevation (degrees)", input_type=float)
        if min_elevation is not None:
            data["min_elevation"] = min_elevation
    else:
        print(f"Invalid target type: {target_type}")
        return
    
    response = call_endpoint("POST", "/default-target", data)
    print_response(response)


def handle_get_default_target():
    """Handle get default target."""
    print_section("Get Default Target")
    response = call_endpoint("GET", "/default-target")
    print_response(response)


def handle_clear_default_target():
    """Handle clear default target."""
    print_section("Clear Default Target")
    confirm = get_input("Clear default target? (y/n)", default="y", input_type=bool)
    if confirm:
        response = call_endpoint("DELETE", "/default-target")
        print_response(response)


def handle_point_at_default():
    """Handle point at default target."""
    print_section("Point at Default Target")
    response = call_endpoint("POST", "/target/default")
    print_response(response)


def handle_get_startup_behavior():
    """Handle get startup behavior."""
    print_section("Get Startup Behavior")
    response = call_endpoint("GET", "/startup-behavior")
    print_response(response)


def handle_set_startup_behavior():
    """Handle set startup behavior."""
    print_section("Set Startup Behavior")
    use_default = get_input("Use default target on startup? (y/n)", input_type=bool)
    if use_default is None:
        return
    
    data = {"use_default_on_startup": use_default}
    response = call_endpoint("POST", "/startup-behavior", data)
    print_response(response)


def handle_get_location():
    """Handle get location."""
    print_section("Get Location")
    response = call_endpoint("GET", "/location")
    print_response(response)


def handle_update_location():
    """Handle update location."""
    print_section("Update Location")
    latitude = get_input("Latitude (degrees, -90 to 90)", input_type=float)
    if latitude is None:
        return
    longitude = get_input("Longitude (degrees, -180 to 180)", input_type=float)
    if longitude is None:
        return
    altitude = get_optional_input("Altitude (meters)", input_type=float)
    
    data = {"latitude": latitude, "longitude": longitude}
    if altitude is not None:
        data["altitude"] = altitude
    
    response = call_endpoint("POST", "/location", data)
    print_response(response)


def handle_enable_tracking():
    """Handle enable tracking."""
    print_section("Enable Tracking")
    response = call_endpoint("POST", "/tracking/enable")
    print_response(response)


def handle_disable_tracking():
    """Handle disable tracking."""
    print_section("Disable Tracking")
    response = call_endpoint("POST", "/tracking/disable")
    print_response(response)


def handle_get_tracking_status():
    """Handle get tracking status."""
    print_section("Tracking Status")
    response = call_endpoint("GET", "/tracking/status")
    print_response(response)


def handle_get_status():
    """Handle get status."""
    print_section("System Status")
    response = call_endpoint("GET", "/status")
    print_response(response)


def handle_get_satellites():
    """Handle get satellites."""
    print_section("Satellites List")
    format_choice = get_input("Format (table/json)", default="json")
    if format_choice == "table":
        url = f"{BASE_URL}/satellites?format=table"
        response = requests.get(url, timeout=10)
        print(response.text)
    else:
        response = call_endpoint("GET", "/satellites")
        print_response(response)


def handle_get_root():
    """Handle root endpoint."""
    print_section("API Root Info")
    response = call_endpoint("GET", "/")
    print_response(response)


def main():
    """Main CLI loop."""
    global BASE_URL
    
    # Allow override of host/port via command line args
    if len(sys.argv) > 1:
        host = sys.argv[1]
        if len(sys.argv) > 2:
            port = int(sys.argv[2])
        else:
            port = DEFAULT_PORT
        BASE_URL = f"http://{host}:{port}"
        print(f"Using API at: {BASE_URL}")
    
    while True:
        try:
            show_menu()
            choice = input("Select an option: ").strip()
            
            if choice == "0":
                print("\nGoodbye!")
                break
            elif choice == "1":
                handle_orientation()
            elif choice == "2":
                handle_star()
            elif choice == "3":
                handle_planet()
            elif choice == "4":
                handle_satellite()
            elif choice == "5":
                handle_nearest_group()
            elif choice == "6":
                handle_detarget()
            elif choice == "7":
                handle_random_tour_start()
            elif choice == "8":
                handle_random_tour_stop()
            elif choice == "9":
                handle_random_tour_status()
            elif choice == "10":
                handle_laser_toggle()
            elif choice == "11":
                handle_laser_status()
            elif choice == "12":
                handle_set_default_target()
            elif choice == "13":
                handle_get_default_target()
            elif choice == "14":
                handle_clear_default_target()
            elif choice == "15":
                handle_point_at_default()
            elif choice == "16":
                handle_get_startup_behavior()
            elif choice == "17":
                handle_set_startup_behavior()
            elif choice == "18":
                handle_get_location()
            elif choice == "19":
                handle_update_location()
            elif choice == "20":
                handle_enable_tracking()
            elif choice == "21":
                handle_disable_tracking()
            elif choice == "22":
                handle_get_tracking_status()
            elif choice == "23":
                handle_get_status()
            elif choice == "24":
                handle_get_satellites()
            elif choice == "25":
                handle_get_root()
            else:
                print("\n❌ Invalid option. Please try again.")
            
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()

