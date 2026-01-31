#!/usr/bin/env python3
"""
Main container shipping simulator.

Simulates containers moving between depots and terminals via vessels,
generating realistic IoT events along the way.
"""
import sys
import time
import signal
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.config import (
    SIMULATION_SPEED, EVENT_INTERVAL_SECONDS,
    ContainerState, VESSEL_SPEED_AVG, TRUCK_SPEED_AVG, RAIL_SPEED_AVG
)
from simulator.models.container import Container, ContainerMetadata
from simulator.models.vessel import Vessel
from simulator.core.database import DatabaseHandler
from simulator.core.geofence_checker import GeofenceChecker
from simulator.core.route_generator import RouteGenerator
from simulator.core.event_generator import EventGenerator, IoTEvent


class ContainerSimulator:
    """
    Main simulator orchestrating container movements and IoT events.
    """

    def __init__(
        self,
        num_containers: int = 50,
        simulation_speed: float = SIMULATION_SPEED,
        start_time: Optional[datetime] = None
    ):
        self.num_containers = num_containers
        self.simulation_speed = simulation_speed
        self.start_time = start_time or datetime.utcnow()
        self.sim_time = self.start_time

        # Components
        self.db_handler = DatabaseHandler()
        self.db = None
        self.geofence_checker: Optional[GeofenceChecker] = None
        self.route_generator: Optional[RouteGenerator] = None
        self.event_generator = EventGenerator()

        # State
        self.containers: List[Container] = []
        self.vessels: List[Vessel] = []
        self.running = False
        self.events_generated = 0

    def setup(self):
        """Initialize database and load geofences."""
        print("=" * 60)
        print("CONTAINER SHIPPING SIMULATOR")
        print("=" * 60)

        # Connect to database
        self.db = self.db_handler.connect()
        self.db_handler.setup_collections()

        # Initialize components
        self.geofence_checker = GeofenceChecker(self.db)
        self.route_generator = RouteGenerator(self.db)

        # Check geofences exist
        geofence_count = self.db["geofences"].count_documents({})
        if geofence_count == 0:
            print("\nWARNING: No geofences found! Run import_geofences.py first.")
            print("Example: python simulator/import_geofences.py")
            return False

        print(f"\nLoaded {geofence_count} geofences")

        # Create initial containers
        print(f"\nCreating {self.num_containers} containers...")
        self._create_containers()

        print(f"\nSimulation ready:")
        print(f"  - Containers: {len(self.containers)}")
        print(f"  - Speed: {self.simulation_speed}x (1 real second = {self.simulation_speed} sim seconds)")
        print(f"  - Start time: {self.sim_time}")

        return True

    def _create_containers(self):
        """Create initial containers with assigned journeys."""
        rail_count = 0
        for i in range(self.num_containers):
            container = Container()

            # Assign a journey
            try:
                journey = self.route_generator.select_journey()
                container.origin_depot = journey["origin_depot"]
                container.origin_rail_ramp = journey.get("origin_rail_ramp")
                container.origin_terminal = journey["origin_terminal"]
                container.destination_terminal = journey["destination_terminal"]
                container.destination_rail_ramp = journey.get("destination_rail_ramp")
                container.destination_depot = journey["destination_depot"]
                container.use_rail = journey.get("use_rail", False)

                if container.use_rail:
                    rail_count += 1

                # Start at origin depot
                if container.origin_depot:
                    centroid = self.geofence_checker.get_centroid(container.origin_depot)
                    container.set_position(centroid[1], centroid[0])  # lat, lon
                    container.current_geofence = container.origin_depot["properties"]["name"]

                # Generate initial route (to rail ramp if using rail, else to terminal)
                if container.origin_depot:
                    if container.use_rail and container.origin_rail_ramp:
                        container.current_route = self.route_generator.generate_land_route(
                            container.origin_depot, container.origin_rail_ramp
                        )
                    elif container.origin_terminal:
                        container.current_route = self.route_generator.generate_land_route(
                            container.origin_depot, container.origin_terminal
                        )

                # Stagger journey start times
                container.journey_start_time = self.sim_time + timedelta(hours=random.randint(0, 48))
                container.last_event_time = container.journey_start_time

                self.containers.append(container)

                # Save to database
                self.db_handler.update_container(container)

                if (i + 1) % 10 == 0:
                    print(f"  Created {i + 1}/{self.num_containers} containers")

            except Exception as e:
                print(f"  Error creating container {i + 1}: {e}")

        if rail_count > 0:
            print(f"  {rail_count}/{self.num_containers} containers will use rail routing")

    def _advance_simulation_time(self, real_elapsed_seconds: float):
        """Advance simulation time based on real elapsed time and speed."""
        sim_elapsed = timedelta(seconds=real_elapsed_seconds * self.simulation_speed)
        self.sim_time += sim_elapsed

    def _update_container(self, container: Container) -> List[IoTEvent]:
        """
        Update a single container's state and generate events.
        Returns list of events generated.
        """
        events = []

        # Skip if journey hasn't started yet
        if container.journey_start_time and self.sim_time < container.journey_start_time:
            return events

        # Calculate time since last event
        if container.last_event_time:
            time_since_last = (self.sim_time - container.last_event_time).total_seconds()
        else:
            time_since_last = EVENT_INTERVAL_SECONDS + 1

        # Generate periodic location updates
        if time_since_last >= EVENT_INTERVAL_SECONDS:
            # Check current geofence
            current_geofence = self.geofence_checker.check_point(
                container.longitude, container.latitude
            )

            # Detect geofence entry/exit
            current_name = current_geofence["properties"]["name"] if current_geofence else None
            if current_name != container.current_geofence:
                # Geofence transition
                if container.current_geofence and not current_name:
                    # Exiting geofence
                    old_geofence = self.geofence_checker.get_geofence_by_name(container.current_geofence)
                    if old_geofence:
                        event = self.event_generator.create_gate_event(
                            container, self.sim_time, is_entry=False, geofence=old_geofence
                        )
                        events.append(event)
                        self.db_handler.write_gate_event(event, old_geofence)

                if current_name and current_name != container.current_geofence:
                    # Entering geofence
                    event = self.event_generator.create_gate_event(
                        container, self.sim_time, is_entry=True, geofence=current_geofence
                    )
                    events.append(event)
                    self.db_handler.write_gate_event(event, current_geofence)

                container.current_geofence = current_name

            # Generate location update
            event = self.event_generator.create_location_update(
                container, self.sim_time, current_geofence
            )
            events.append(event)
            container.last_event_time = self.sim_time

            # Move container along route
            if container.current_route and container.route_index < len(container.current_route) - 1:
                container.route_index += 1
                next_point = container.current_route[container.route_index]
                container.set_position(next_point[1], next_point[0])  # lat, lon

                # Generate motion events at start/end of movement
                if container.route_index == 1:
                    # Starting movement
                    events.append(self.event_generator.create_motion_event(
                        container, self.sim_time, is_start=True, geofence=current_geofence
                    ))
                    container.is_moving = True

            elif container.current_route and container.route_index >= len(container.current_route) - 1:
                # Reached destination
                if container.is_moving:
                    events.extend(self.event_generator.generate_stop_events(
                        container, self.sim_time, current_geofence
                    ))
                    container.is_moving = False

                # Transition to next state
                self._transition_container_state(container)

        return events

    def _transition_container_state(self, container: Container):
        """Transition container to next state and set up new route."""
        current_state = container.state

        try:
            if current_state == ContainerState.AT_ORIGIN_DEPOT:
                # Check if using rail for origin
                if container.use_rail and container.origin_rail_ramp:
                    container.transition_to(ContainerState.IN_TRANSIT_TO_RAIL_RAMP)
                    container.current_route = self.route_generator.generate_land_route(
                        container.origin_depot, container.origin_rail_ramp
                    )
                else:
                    container.transition_to(ContainerState.IN_TRANSIT_TO_TERMINAL)
                    if container.origin_depot and container.origin_terminal:
                        container.current_route = self.route_generator.generate_land_route(
                            container.origin_depot, container.origin_terminal
                        )
                container.route_index = 0

            elif current_state == ContainerState.IN_TRANSIT_TO_RAIL_RAMP:
                container.transition_to(ContainerState.AT_ORIGIN_RAIL_RAMP)
                container.current_route = []
                container.route_index = 0

            elif current_state == ContainerState.AT_ORIGIN_RAIL_RAMP:
                container.transition_to(ContainerState.IN_TRANSIT_RAIL)
                if container.origin_rail_ramp and container.origin_terminal:
                    container.current_route = self.route_generator.generate_rail_route(
                        container.origin_rail_ramp, container.origin_terminal
                    )
                    container.route_index = 0

            elif current_state == ContainerState.IN_TRANSIT_RAIL:
                container.transition_to(ContainerState.IN_TRANSIT_TO_TERMINAL)
                # Short final segment from rail to terminal
                container.current_route = []
                container.route_index = 0

            elif current_state == ContainerState.IN_TRANSIT_TO_TERMINAL:
                container.transition_to(ContainerState.AT_ORIGIN_TERMINAL)
                container.current_route = []
                container.route_index = 0

            elif current_state == ContainerState.AT_ORIGIN_TERMINAL:
                container.transition_to(ContainerState.LOADED_ON_VESSEL)

            elif current_state == ContainerState.LOADED_ON_VESSEL:
                container.transition_to(ContainerState.IN_TRANSIT_OCEAN)
                if container.origin_terminal and container.destination_terminal:
                    container.current_route = self.route_generator.generate_ocean_route(
                        container.origin_terminal, container.destination_terminal
                    )
                    container.route_index = 0

            elif current_state == ContainerState.IN_TRANSIT_OCEAN:
                container.transition_to(ContainerState.AT_DESTINATION_TERMINAL)
                container.current_route = []
                container.route_index = 0

            elif current_state == ContainerState.AT_DESTINATION_TERMINAL:
                # Check if using rail for destination
                if container.use_rail and container.destination_rail_ramp:
                    container.transition_to(ContainerState.IN_TRANSIT_FROM_TERMINAL)
                    container.current_route = self.route_generator.generate_land_route(
                        container.destination_terminal, container.destination_rail_ramp
                    )
                else:
                    container.transition_to(ContainerState.IN_TRANSIT_TO_DEPOT)
                    if container.destination_terminal and container.destination_depot:
                        container.current_route = self.route_generator.generate_land_route(
                            container.destination_terminal, container.destination_depot
                        )
                container.route_index = 0

            elif current_state == ContainerState.IN_TRANSIT_FROM_TERMINAL:
                container.transition_to(ContainerState.AT_DESTINATION_RAIL_RAMP)
                container.current_route = []
                container.route_index = 0

            elif current_state == ContainerState.AT_DESTINATION_RAIL_RAMP:
                container.transition_to(ContainerState.IN_TRANSIT_RAIL_TO_DEPOT)
                if container.destination_rail_ramp and container.destination_depot:
                    container.current_route = self.route_generator.generate_rail_route(
                        container.destination_rail_ramp, container.destination_depot
                    )
                    container.route_index = 0

            elif current_state == ContainerState.IN_TRANSIT_RAIL_TO_DEPOT:
                container.transition_to(ContainerState.IN_TRANSIT_TO_DEPOT)
                container.current_route = []
                container.route_index = 0

            elif current_state == ContainerState.IN_TRANSIT_TO_DEPOT:
                container.transition_to(ContainerState.AT_DESTINATION_DEPOT)
                container.current_route = []
                container.route_index = 0

            elif current_state == ContainerState.AT_DESTINATION_DEPOT:
                # Start new journey
                self._assign_new_journey(container)

            # Update in database
            self.db_handler.update_container(container)

        except ValueError as e:
            # Invalid transition, skip
            pass

    def _assign_new_journey(self, container: Container):
        """Assign a new journey to a container that completed its previous journey."""
        try:
            journey = self.route_generator.select_journey()
            container.origin_depot = journey["origin_depot"]
            container.origin_rail_ramp = journey.get("origin_rail_ramp")
            container.origin_terminal = journey["origin_terminal"]
            container.destination_terminal = journey["destination_terminal"]
            container.destination_rail_ramp = journey.get("destination_rail_ramp")
            container.destination_depot = journey["destination_depot"]
            container.use_rail = journey.get("use_rail", False)
            container.state = ContainerState.AT_ORIGIN_DEPOT
            container.route_index = 0
            container.current_route = []

            if container.origin_depot:
                centroid = self.geofence_checker.get_centroid(container.origin_depot)
                container.set_position(centroid[1], centroid[0])

            container.journey_start_time = self.sim_time + timedelta(hours=random.randint(1, 12))

        except Exception as e:
            print(f"Error assigning new journey: {e}")

    def run(self):
        """Main simulation loop."""
        self.running = True
        print("\n" + "=" * 60)
        print("SIMULATION STARTED")
        print("=" * 60)
        print(f"Press Ctrl+C to stop\n")

        last_status_time = time.time()
        status_interval = 10  # Print status every 10 seconds

        while self.running:
            loop_start = time.time()

            # Update all containers
            all_events = []
            for container in self.containers:
                events = self._update_container(container)
                all_events.extend(events)

            # Write events to database
            if all_events:
                self.db_handler.write_events(all_events)
                self.events_generated += len(all_events)

            # Print periodic status
            if time.time() - last_status_time > status_interval:
                self._print_status()
                last_status_time = time.time()

            # Calculate sleep time to maintain simulation speed
            loop_duration = time.time() - loop_start
            sleep_time = max(0, 1.0 - loop_duration)  # Target 1 second per loop

            time.sleep(sleep_time)

            # Advance simulation time
            self._advance_simulation_time(1.0)

    def _print_status(self):
        """Print current simulation status."""
        states = {}
        rail_count = 0
        for c in self.containers:
            states[c.state] = states.get(c.state, 0) + 1
            if c.use_rail:
                rail_count += 1

        print(f"\n[{self.sim_time.strftime('%Y-%m-%d %H:%M')}] Events: {self.events_generated}")
        print(f"  Container states (rail: {rail_count}):")
        for state, count in sorted(states.items()):
            short_state = state.replace("at_", "").replace("in_transit_", "→").replace("_rail_ramp", "_rail").replace("_to_", "_")
            print(f"    {short_state}: {count}")

    def stop(self):
        """Stop the simulation."""
        self.running = False
        print("\n" + "=" * 60)
        print("SIMULATION STOPPED")
        print("=" * 60)
        print(f"Total events generated: {self.events_generated}")

        # Print final stats
        stats = self.db_handler.get_stats()
        print("\nDatabase statistics:")
        for name, count in stats.items():
            print(f"  - {name}: {count}")

        self.db_handler.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Container Shipping Simulator")
    parser.add_argument(
        "-n", "--num-containers",
        type=int,
        default=50,
        help="Number of containers to simulate (default: 50)"
    )
    parser.add_argument(
        "-s", "--speed",
        type=float,
        default=SIMULATION_SPEED,
        help=f"Simulation speed multiplier (default: {SIMULATION_SPEED})"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for simulation (ISO format, default: now)"
    )

    args = parser.parse_args()

    # Parse start date
    start_time = None
    if args.start_date:
        start_time = datetime.fromisoformat(args.start_date)

    # Create and run simulator
    simulator = ContainerSimulator(
        num_containers=args.num_containers,
        simulation_speed=args.speed,
        start_time=start_time
    )

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\nReceived shutdown signal...")
        simulator.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Setup and run
    if simulator.setup():
        simulator.run()
    else:
        print("\nSetup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
