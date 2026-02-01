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
    ContainerState, VESSEL_SPEED_AVG, TRUCK_SPEED_AVG, RAIL_SPEED_AVG,
    STAGGER_SLOTS, LOOP_INTERVAL_SECONDS, DEFAULT_NUM_CONTAINERS
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
        num_containers: int = DEFAULT_NUM_CONTAINERS,
        simulation_speed: float = SIMULATION_SPEED,
        start_time: Optional[datetime] = None,
        num_slots: int = STAGGER_SLOTS
    ):
        self.num_containers = num_containers
        self.simulation_speed = simulation_speed
        self.start_time = start_time or datetime.utcnow()
        self.sim_time = self.start_time
        self.num_slots = num_slots

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

        # Staggered processing
        self.current_slot = 0
        self.containers_by_slot: dict[int, List[Container]] = {i: [] for i in range(self.num_slots)}

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
        batch_size = 1000  # Batch DB writes for performance
        container_batch = []

        print(f"  Creating {self.num_containers:,} containers across {self.num_slots} time slots...")
        print(f"  (~{self.num_containers // self.num_slots:,} containers per slot)")

        for i in range(self.num_containers):
            container = Container()

            # Assign report slot (distribute evenly across all slots)
            container.report_slot = i % self.num_slots

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

                # Stagger journey start times (0-4 hours spread for faster startup)
                container.journey_start_time = self.sim_time + timedelta(hours=random.randint(0, 4))
                container.last_event_time = container.journey_start_time

                self.containers.append(container)
                self.containers_by_slot[container.report_slot].append(container)
                container_batch.append(container)

                # Batch save to database
                if len(container_batch) >= batch_size:
                    self.db_handler.update_containers_batch(container_batch)
                    container_batch = []

                if (i + 1) % 10000 == 0:
                    print(f"  Created {i + 1:,}/{self.num_containers:,} containers")

            except Exception as e:
                print(f"  Error creating container {i + 1}: {e}")

        # Save remaining batch
        if container_batch:
            self.db_handler.update_containers_batch(container_batch)

        if rail_count > 0:
            print(f"  {rail_count:,}/{self.num_containers:,} containers will use rail routing")

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

                # Update position in DB (for live map tracking)
                self.db_handler.update_container(container)

            elif container.current_route and container.route_index >= len(container.current_route) - 1:
                # Reached destination
                if container.is_moving:
                    events.extend(self.event_generator.generate_stop_events(
                        container, self.sim_time, current_geofence
                    ))
                    container.is_moving = False
                    # Save movement state to DB
                    self.db_handler.update_container(container)

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
        """Main simulation loop with staggered container processing."""
        self.running = True
        print("\n" + "=" * 60)
        print("SIMULATION STARTED (Staggered Mode)")
        print("=" * 60)
        print(f"  Total containers: {len(self.containers):,}")
        print(f"  Time slots: {self.num_slots}")
        print(f"  Containers per slot: ~{len(self.containers) // self.num_slots:,}")
        print(f"  Event interval: {EVENT_INTERVAL_SECONDS // 60} minutes (sim time)")
        print(f"Press Ctrl+C to stop\n")

        last_status_time = time.time()
        status_interval = 10  # Print status every 10 seconds

        while self.running:
            loop_start = time.time()

            # Update only containers in current slot (staggered processing)
            all_events = []
            slot_containers = self.containers_by_slot.get(self.current_slot, [])

            for container in slot_containers:
                events = self._update_container(container)
                all_events.extend(events)

            # Write events to database
            if all_events:
                self.db_handler.write_events(all_events)
                self.events_generated += len(all_events)

            # Advance to next slot (wrap around)
            self.current_slot = (self.current_slot + 1) % self.num_slots

            # Print periodic status
            if time.time() - last_status_time > status_interval:
                self._print_status()
                last_status_time = time.time()

            # Calculate sleep time to maintain target loop interval
            loop_duration = time.time() - loop_start
            sleep_time = max(0, LOOP_INTERVAL_SECONDS - loop_duration)

            time.sleep(sleep_time)

            # Advance simulation time
            self._advance_simulation_time(LOOP_INTERVAL_SECONDS)

    def _print_status(self):
        """Print current simulation status."""
        states = {}
        rail_count = 0
        moving_count = 0
        for c in self.containers:
            states[c.state] = states.get(c.state, 0) + 1
            if c.use_rail:
                rail_count += 1
            if c.is_moving:
                moving_count += 1

        print(f"\n[{self.sim_time.strftime('%Y-%m-%d %H:%M')}] Slot: {self.current_slot}/{self.num_slots}")
        print(f"  Total events: {self.events_generated:,} | Containers: {len(self.containers):,} | Moving: {moving_count:,}")
        print(f"  Rail routing: {rail_count:,}")
        print(f"  Container states:")
        for state, count in sorted(states.items()):
            short_state = state.replace("at_", "").replace("in_transit_", "→").replace("_rail_ramp", "_rail").replace("_to_", "_")
            print(f"    {short_state}: {count:,}")

    def load_state(self, filepath: str = "simulation_state.json") -> bool:
        """Load simulation state from a JSON file."""
        import json
        from pathlib import Path

        if not Path(filepath).exists():
            print(f"State file not found: {filepath}")
            return False

        print(f"\nLoading simulation state from: {filepath}")

        with open(filepath, 'r') as f:
            state = json.load(f)

        self.sim_time = datetime.fromisoformat(state["sim_time"])
        self.current_slot = state["current_slot"]
        self.events_generated = state["events_generated"]
        self.num_slots = state.get("num_slots", self.num_slots)
        self.simulation_speed = state.get("simulation_speed", self.simulation_speed)

        # Rebuild containers_by_slot
        self.containers_by_slot = {i: [] for i in range(self.num_slots)}

        # Restore container states from saved data
        container_map = {c["container_id"]: c for c in state["containers"]}

        for container in self.containers:
            saved = container_map.get(container.metadata.container_id)
            if saved:
                container.state = saved["state"]
                container.report_slot = saved["report_slot"]
                container.latitude = saved["latitude"]
                container.longitude = saved["longitude"]
                container.is_moving = saved["is_moving"]
                container.route_index = saved["route_index"]
                container.use_rail = saved["use_rail"]
                container.current_geofence = saved["current_geofence"]
                if saved["journey_start_time"]:
                    container.journey_start_time = datetime.fromisoformat(saved["journey_start_time"])
                if saved["last_event_time"]:
                    container.last_event_time = datetime.fromisoformat(saved["last_event_time"])

            self.containers_by_slot[container.report_slot].append(container)

        print(f"  - Restored {len(self.containers):,} containers")
        print(f"  - Sim time: {self.sim_time}")
        print(f"  - Current slot: {self.current_slot}")
        print(f"  - Events generated: {self.events_generated:,}")

        return True

    def save_state(self, filepath: str = "simulation_state.json"):
        """Save simulation state to a JSON file for later resumption."""
        import json

        state = {
            "sim_time": self.sim_time.isoformat(),
            "current_slot": self.current_slot,
            "events_generated": self.events_generated,
            "num_slots": self.num_slots,
            "simulation_speed": self.simulation_speed,
            "containers": []
        }

        for c in self.containers:
            container_state = {
                "container_id": c.metadata.container_id,
                "tracker_id": c.metadata.tracker_id,
                "asset_id": c.metadata.asset_id,
                "state": c.state,
                "report_slot": c.report_slot,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "is_moving": c.is_moving,
                "route_index": c.route_index,
                "use_rail": c.use_rail,
                "current_geofence": c.current_geofence,
                "journey_start_time": c.journey_start_time.isoformat() if c.journey_start_time else None,
                "last_event_time": c.last_event_time.isoformat() if c.last_event_time else None,
            }
            state["containers"].append(container_state)

        with open(filepath, 'w') as f:
            json.dump(state, f)

        print(f"\nSimulation state saved to: {filepath}")
        print(f"  - Containers: {len(state['containers']):,}")
        print(f"  - Sim time: {self.sim_time}")
        print(f"  - Events generated: {self.events_generated:,}")

    def stop(self, save_state: bool = False, state_file: str = "simulation_state.json"):
        """Stop the simulation."""
        self.running = False
        print("\n" + "=" * 60)
        print("SIMULATION STOPPED")
        print("=" * 60)
        print(f"Total events generated: {self.events_generated}")

        # Save state if requested
        if save_state:
            self.save_state(state_file)

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
        default=DEFAULT_NUM_CONTAINERS,
        help=f"Number of containers to simulate (default: {DEFAULT_NUM_CONTAINERS:,})"
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
    parser.add_argument(
        "--slots",
        type=int,
        default=STAGGER_SLOTS,
        help=f"Number of time slots for staggered processing (default: {STAGGER_SLOTS})"
    )
    parser.add_argument(
        "--save-state",
        action="store_true",
        help="Save simulation state on exit (for resuming later)"
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default="simulation_state.json",
        help="File path for saving/loading simulation state"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from a previously saved simulation state"
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
        start_time=start_time,
        num_slots=args.slots
    )

    # Handle Ctrl+C gracefully - save state if requested
    def signal_handler(sig, frame):
        print("\n\nReceived shutdown signal...")
        simulator.stop(save_state=args.save_state, state_file=args.state_file)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Setup and run
    if simulator.setup():
        # Resume from saved state if requested
        if args.resume:
            if not simulator.load_state(args.state_file):
                print("Warning: Could not load state, starting fresh")

        simulator.run()
    else:
        print("\nSetup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
