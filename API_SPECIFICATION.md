# Celestial Pointer API Specification

**Version:** 1.1  
**Base URL:** `http://localhost:8000` (default)  
**API Type:** RESTful JSON API  
**Documentation:** Interactive API docs available at `http://localhost:8000/docs`

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Common Response Formats](#common-response-formats)
4. [Status & Information Endpoints](#status--information-endpoints)
5. [Pointing Endpoints](#pointing-endpoints)
6. [Laser Control Endpoints](#laser-control-endpoints)
7. [Default Body Management](#default-body-management)
8. [Startup Behavior Control](#startup-behavior-control)
9. [Location Management](#location-management)
10. [Tracking Control](#tracking-control)
11. [Satellite Management](#satellite-management)
12. [Error Handling](#error-handling)
13. [Data Models](#data-models)

---

## Overview

The Celestial Pointer API provides control over a laser pointing system that can point at stars, planets, satellites, and arbitrary orientations. The system uses stepper motors for base rotation and laser elevation control, with an IMU for orientation sensing.

### Base URL
```
http://localhost:8000
```

### Content Type
All requests and responses use `application/json`.

---

## Authentication

Currently, the API does not require authentication. All endpoints are accessible without credentials.

---

## Common Response Formats

### Success Response
Most endpoints return a JSON object with status information:
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

### Error Response
Errors return HTTP status codes and JSON error details:
```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `200 OK` - Request successful
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

---

## Status & Information Endpoints

### GET `/`
Get API information.

**Response:**
```json
{
  "name": "Celestial Pointer API",
  "version": "0.1.0",
  "status": "running"
}
```

### GET `/status`
Get current system status.

**Response:**
```json
{
  "laser_on": false,
  "current_target": {
    "type": "satellite",
    "id": "25544",
    "azimuth": 180.5,
    "elevation": 45.2
  },
  "default_target": {
    "type": "satellite",
    "id": "ISS"
  },
  "tracking_enabled": true,
  "is_trackable": true,
  "motor1_angle": 180.0,
  "motor2_angle": 45.0,
  "elevation_range": {
    "min": -50.0,
    "max": 90.0
  }
}
```

**Response (if system not initialized):**
```json
{
  "status": "not_initialized"
}
```

---

## Pointing Endpoints

### POST `/target/orientation`
Point at a specific azimuth and elevation.

**Request Body:**
```json
{
  "azimuth": 180.0,    // degrees (0-360)
  "elevation": 45.0    // degrees (-90 to 90)
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.0,
  "elevation": 45.0,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

### POST `/target/star`
Point at a star by name or HIP number.

**Request Body:**
```json
{
  "star_name": "Sirius"  // or "HIP32349" or "32349"
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

**Note:** The star name and HIP number are stored in `current_target` (visible via `/status`), but are not included in this response.

### POST `/target/planet`
Point at a planet by name.

**Request Body:**
```json
{
  "planet_name": "Mars"  // or "Moon", "Jupiter", etc.
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

### POST `/target/satellite`
Point at a satellite by ID (NORAD ID or name).

**Request Body:**
```json
{
  "satellite_id": "25544"  // or "ISS", or satellite name
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

**Note:** The satellite must be in the preloaded satellite list. Use `GET /satellites` to see available satellites.


### POST `/target/nearest-group`
Find and track the nearest visible satellite above horizon from configured groups.

**Request Body:**
```json
{
  "groups": [  // optional, uses config default if not provided
    {
      "group_name": "stations",
      "limit": null
    },
    {
      "group_name": "visual",
      "limit": null
    }
  ],
  "min_elevation": 0.0  // optional, minimum elevation in degrees
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1,
  "group_tracking": true,
  "satellite_id": "25544",
  "sticky_duration": 60.0
}
```

**Note:** This enables group tracking mode, which will automatically switch to better bodies after the sticky duration expires.

### POST `/target/default`
Point at the currently set default body.

**Response (for star/planet/satellite/orientation):**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

**Response (for group type):**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1,
  "group_tracking": true,
  "satellite_id": "25544",
  "sticky_duration": 60.0
}
```

**Error:** Returns `404` if no default body is set.

**Note:** When the default body type is "group", this enables group tracking mode automatically, similar to `/target/nearest-group`.

### POST `/detarget`
Stop pointing and turn off laser.

**Response:**
```json
{
  "status": "detargeted",
  "laser_off": true
}
```

---

## Laser Control Endpoints

### POST `/laser/toggle`
Toggle laser on/off or set specific state.

**Request Body:**
```json
{
  "state": null  // null = toggle, true = on, false = off
}
```

**Response:**
```json
{
  "laser_on": true
}
```

### GET `/laser/status`
Get current laser status.

**Response:**
```json
{
  "laser_on": true,
  "elevation_range": {
    "min": -50.0,
    "max": 90.0
  }
}
```

---

## Default Body Management

### POST `/default-target`
Set a default body that can be activated later.

**Request Body:**
```json
{
  "target_type": "satellite",  // "star", "planet", "satellite", "orientation", "group"
  "target_value": "ISS",      // star name, planet name, satellite ID (not used for "group" or "orientation")
  "azimuth": null,             // required for "orientation" type
  "elevation": null,           // required for "orientation" type
  "groups": null,              // optional, for "group" type: override default groups from config
  "min_elevation": null        // optional, for "group" type: override minimum elevation
}
```

**Example for satellite:**
```json
{
  "target_type": "satellite",
  "target_value": "ISS"
}
```

**Example for orientation:**
```json
{
  "target_type": "orientation",
  "target_value": "orientation",
  "azimuth": 180.0,
  "elevation": 45.0
}
```

**Example for group (nearest visible satellite):**
```json
{
  "target_type": "group"
}
```

**Example for group with custom groups and elevation:**
```json
{
  "target_type": "group",
  "groups": [
    {
      "group_name": "stations",
      "limit": null
    },
    {
      "group_name": "visual",
      "limit": 50
    }
  ],
  "min_elevation": 10.0
}
```

**Response:**
```json
{
  "status": "default_target_set",
  "default_target": {
    "type": "satellite",
    "id": "ISS"
  }
}
```

### GET `/default-target`
Get the currently set default body.

**Response:**
```json
{
  "default_target": {
    "type": "satellite",
    "id": "ISS"
  },
  "has_default": true
}
```

**Response (if no default body):**
```json
{
  "default_target": null,
  "has_default": false
}
```

### DELETE `/default-target`
Clear the default body.

**Response:**
```json
{
  "status": "default_target_cleared"
}
```

---

## Startup Behavior Control

### GET `/startup-behavior`
Get the current startup behavior configuration.

**Response:**
```json
{
  "use_default_on_startup": false,
  "has_default_target": true,
  "default_target": {
    "type": "group"
  }
}
```

### POST `/startup-behavior`
Set whether to use the default body on startup.

**Request Body:**
```json
{
  "use_default_on_startup": true  // true = point at default body on startup, false = wait for API input
}
```

**Response:**
```json
{
  "status": "startup_behavior_updated",
  "use_default_on_startup": true
}
```

**Note:** This setting can be changed at runtime without restarting the server. When `use_default_on_startup` is `true` and a default body is set, the system will automatically point at the default body after the API server starts. If the default body type is "group", it will find and track the nearest visible satellite from the configured groups.

---

## Location Management

### GET `/location`
Get the current observer location.

**Response:**
```json
{
  "latitude": 37.7749,
  "longitude": -122.4194,
  "altitude": 0.0
}
```

### POST `/location`
Update the observer location (latitude, longitude, and optionally altitude).

**Request Body:**
```json
{
  "latitude": 40.7128,    // Latitude in degrees (-90 to 90)
  "longitude": -74.0060,  // Longitude in degrees (-180 to 180)
  "altitude": 0.0         // Altitude in meters (optional)
}
```

**Response:**
```json
{
  "status": "location_updated",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "altitude": 0.0
}
```

**Error Responses:**

- `400 Bad Request`: Invalid latitude or longitude values (out of range)
- `409 Conflict`: Device is currently targeting a body (must detarget first)
- `500 Internal Server Error`: Target calculator not initialized or error updating location

**Note:** 
- Location changes are saved to `config.py` and persist across restarts
- The location update immediately affects all target calculations
- Location cannot be changed while the device is actively targeting a body (to prevent incorrect calculations)
- Use `POST /detarget` first if you need to change location while targeting

---

## Tracking Control

### POST `/tracking/enable`
Enable automatic body tracking.

**Response:**
```json
{
  "status": "tracking_enabled",
  "tracking": true
}
```

### POST `/tracking/disable`
Disable automatic body tracking.

**Response:**
```json
{
  "status": "tracking_disabled",
  "tracking": false
}
```

### GET `/tracking/status`
Get current tracking status.

**Response:**
```json
{
  "tracking_enabled": true,
  "tracking_running": true,
  "current_target_trackable": true,
  "update_frequency": 2.0
}
```

---

## Satellite Management

### GET `/satellites`
Get list of all preloaded satellites with their names, pointing information, and current visibility.

**Query Parameters:**
- `format` (optional): `"table"` for formatted table output, `"json"` for JSON (default)

**Response (JSON format):**
```json
{
  "count": 100,
  "satellites": [
    {
      "name": "ISS (ZARYA)",
      "norad_id": "25544",
      "elevation": 75.30,
      "azimuth": 120.45,
      "visible": true,
      "endpoint": "/target/satellite",
      "method": "POST",
      "payload": {
        "satellite_id": "25544"
      },
      "example_curl": "curl -X POST http://localhost:8000/target/satellite -H \"Content-Type: application/json\" -d '{\"satellite_id\": \"25544\"}'"
    }
  ]
}
```

**Response (Table format):**
When `?format=table` is used, returns a plain text formatted table suitable for command-line viewing. Satellites are sorted by elevation with the most visible (highest elevation) at the bottom.

---

## Error Handling

### Common Error Responses

**404 Not Found:**
```json
{
  "detail": "Star 'InvalidStar' not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "System not initialized"
}
```

**503 Service Unavailable:**
```json
{
  "detail": "Satellite '25544' position not available"
}
```

### Error Scenarios

1. **Body Not Found**: When requesting a star, planet, or satellite that doesn't exist
2. **System Not Initialized**: When the system hasn't finished starting up
3. **Position Unavailable**: When a satellite's position can't be calculated (network issues, TLE data unavailable)
4. **Out of Range**: When a body is below the minimum elevation range

---

## Data Models

### OrientationTarget
```typescript
{
  azimuth: number;      // 0-360 degrees
  elevation: number;    // -90 to 90 degrees
}
```

### StarTarget
```typescript
{
  star_name: string;    // Star name or HIP number (e.g., "Sirius", "HIP32349", "32349")
}
```

### PlanetTarget
```typescript
{
  planet_name: string;  // Planet name (e.g., "Mars", "Moon", "Jupiter")
}
```

### SatelliteTarget
```typescript
{
  satellite_id: string; // NORAD ID or satellite name (e.g., "25544", "ISS")
}
```

### LaserToggle
```typescript
{
  state?: boolean | null; // null = toggle, true = on, false = off
}
```

### DefaultTarget
```typescript
{
  target_type: "star" | "planet" | "satellite" | "orientation" | "group";
  target_value?: string;  // star name, planet name, satellite ID (not used for "group" or "orientation")
  azimuth?: number;        // Required for "orientation" type
  elevation?: number;      // Required for "orientation" type
  groups?: Array<{         // Optional, for "group" type: override default groups from config
    group_name: string;
    limit?: number | null;
  }>;
  min_elevation?: number;   // Optional, for "group" type: override minimum elevation
}
```

### StartupBehavior
```typescript
{
  use_default_on_startup: boolean;  // Whether to use default body on startup
}
```

### LocationUpdate
```typescript
{
  latitude: number;      // Latitude in degrees (-90 to 90)
  longitude: number;    // Longitude in degrees (-180 to 180)
  altitude?: number;    // Altitude in meters (optional)
}
```

### GroupTarget
```typescript
{
  groups?: Array<{
    group_name: string;
    limit?: number | null;
  }>;
  min_elevation?: number;
}
```

---

## Usage Examples

### Point at a Star
```bash
curl -X POST http://localhost:8000/target/star \
  -H "Content-Type: application/json" \
  -d '{"star_name": "Sirius"}'
```

### Point at a Satellite
```bash
curl -X POST http://localhost:8000/target/satellite \
  -H "Content-Type: application/json" \
  -d '{"satellite_id": "25544"}'
```

### Get Available Satellites (Formatted Table)
```bash
curl http://localhost:8000/satellites?format=table
```

### Enable Tracking
```bash
curl -X POST http://localhost:8000/tracking/enable
```

### Toggle Laser
```bash
curl -X POST http://localhost:8000/laser/toggle \
  -H "Content-Type: application/json" \
  -d '{"state": null}'
```

### Set Default Target (Satellite)
```bash
curl -X POST http://localhost:8000/default-target \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "satellite",
    "target_value": "ISS"
  }'
```

### Set Default Target (Nearest Group)
```bash
curl -X POST http://localhost:8000/default-target \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "group"
  }'
```

### Enable Default Target on Startup
```bash
curl -X POST http://localhost:8000/startup-behavior \
  -H "Content-Type: application/json" \
  -d '{
    "use_default_on_startup": true
  }'
```

### Get Startup Behavior
```bash
curl http://localhost:8000/startup-behavior
```

### Get System Status
```bash
curl http://localhost:8000/status
```

---

## Notes for Frontend Developers

1. **Tracking Updates**: When tracking is enabled, the system automatically updates motor positions at the configured frequency (default: 2 Hz). The frontend should poll `/status` periodically to get current state.

2. **Motor Movement**: Motor movements may take time to complete. The system prevents overlapping movements, so rapid successive commands may be queued.

3. **Satellite Availability**: Only preloaded satellites are available. Use `GET /satellites` to see what's available. Satellites are preloaded on startup from the "visual" group (100 brightest satellites).

4. **Group Tracking**: The `/target/nearest-group` endpoint enables automatic body switching. The system will stick to a body for a configurable duration (default: 60 seconds) before rechecking for better bodies. You can also set a default body with type "group" to automatically track the nearest visible satellite.

5. **Startup Behavior**: Use `POST /startup-behavior` to configure whether the system should automatically point at the default body on startup. This can be toggled at runtime without restarting the server. When enabled with a "group" type default body, the system will automatically find and track the nearest visible satellite after startup.

6. **Error Recovery**: If a target position can't be calculated (e.g., satellite below horizon, network issues), the API will return appropriate error codes. The frontend should handle these gracefully.

7. **Real-time Updates**: For real-time updates, consider using WebSockets or polling `/status` at regular intervals (e.g., every 200-500ms).

---

## Interactive API Documentation

FastAPI provides interactive API documentation at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

These provide interactive testing interfaces and detailed schema information.

---

## Version History

- **v1.2** - Location management
  - Added location management endpoints (`GET/POST /location`)
  - Location changes are saved to config file and persist across restarts
  - Location updates immediately affect all target calculations
  - Location cannot be changed while device is actively targeting (prevents incorrect calculations)

- **v1.1** - Enhanced default body and startup behavior
  - Added "group" type support for default body (nearest visible satellite tracking)
  - Added startup behavior control endpoints (`GET/POST /startup-behavior`)
  - Default body can now be set to automatically track nearest visible satellite from groups
  - Runtime toggle for using default body on startup (no restart required)

- **v1.0** - Initial API specification
  - All pointing endpoints
  - Laser control
  - Tracking control
  - Satellite management
  - Default body management

