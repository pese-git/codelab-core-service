"""Task graph builder for planning and validation."""

from typing import Optional


class TaskGraphBuilder:
    """Builds, validates, and optimizes task execution graphs."""

    @staticmethod
    def validate_graph(
        tasks: list[dict],
        dependencies: list[dict]
    ) -> tuple[bool, Optional[str]]:
        """Validate task graph for correctness.

        Checks:
        - All task references are valid (no missing task IDs)
        - No cyclic dependencies
        - Valid dependency format

        Args:
            tasks: List of task dictionaries with at least 'task_id'
            dependencies: List of dependency dicts with 'from' and 'to' fields

        Returns:
            Tuple of (is_valid, error_message)

        Example:
            >>> tasks = [{"task_id": "t0"}, {"task_id": "t1"}]
            >>> deps = [{"from": "t0", "to": "t1"}]
            >>> valid, error = TaskGraphBuilder.validate_graph(tasks, deps)
            >>> valid
            True
            >>> error
            None
        """
        if not tasks:
            return False, "No tasks provided"

        # Build set of valid task IDs
        task_ids = {task.get("task_id") for task in tasks}

        # Check all dependency references exist
        for dep in dependencies:
            from_task = dep.get("from")
            to_task = dep.get("to")

            if from_task not in task_ids:
                return False, f"Task '{from_task}' in dependency not found"
            if to_task not in task_ids:
                return False, f"Task '{to_task}' in dependency not found"

        # Check for cycles using DFS
        has_cycle, cycle_path = TaskGraphBuilder._detect_cycle(
            task_ids, dependencies
        )
        if has_cycle:
            return False, f"Cyclic dependency detected: {' -> '.join(cycle_path)}"

        return True, None

    @staticmethod
    def _detect_cycle(
        task_ids: set[str],
        dependencies: list[dict]
    ) -> tuple[bool, list[str]]:
        """Detect cycles in task graph using DFS.

        Args:
            task_ids: Set of all task IDs
            dependencies: List of dependency dicts

        Returns:
            Tuple of (has_cycle, cycle_path)
        """
        # Build adjacency list
        graph = {task_id: [] for task_id in task_ids}
        for dep in dependencies:
            graph[dep["from"]].append(dep["to"])

        # DFS to detect cycle
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        for task_id in task_ids:
            if task_id not in visited:
                if dfs(task_id):
                    # Return partial cycle path
                    return True, path[-3:] if len(path) >= 3 else path

        return False, []

    @staticmethod
    def topological_sort(
        tasks: list[dict],
        dependencies: list[dict]
    ) -> list[list[str]]:
        """Sort tasks for parallel execution respecting dependencies.

        Groups tasks into levels where tasks at the same level can run
        in parallel. Tasks in level N+1 depend on tasks in level N.

        Args:
            tasks: List of task dictionaries with 'task_id'
            dependencies: List of dependency dicts with 'from' and 'to'

        Returns:
            List of levels, where each level is a list of task_ids.
            Example: [["t0"], ["t1", "t2"], ["t3"]]

        Example:
            >>> tasks = [
            ...     {"task_id": "t0"},
            ...     {"task_id": "t1"},
            ...     {"task_id": "t2"}
            ... ]
            >>> deps = [
            ...     {"from": "t0", "to": "t1"},
            ...     {"from": "t0", "to": "t2"}
            ... ]
            >>> levels = TaskGraphBuilder.topological_sort(tasks, deps)
            >>> levels
            [["t0"], ["t1", "t2"]]
        """
        # Build in-degree map and adjacency list
        task_ids = {task.get("task_id") for task in tasks}
        in_degree = {task_id: 0 for task_id in task_ids}
        graph = {task_id: [] for task_id in task_ids}

        for dep in dependencies:
            from_task = dep["from"]
            to_task = dep["to"]
            graph[from_task].append(to_task)
            in_degree[to_task] += 1

        # Find all tasks with no dependencies
        current_level = [task_id for task_id in task_ids if in_degree[task_id] == 0]
        levels = []

        while current_level:
            levels.append(current_level)
            next_level = []

            # Process all tasks in current level
            for task_id in current_level:
                # Remove edges from this task
                for neighbor in graph[task_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_level.append(neighbor)

            current_level = sorted(next_level)  # Sort for deterministic order

        return levels

    @staticmethod
    def calculate_total_cost(tasks: list[dict]) -> float:
        """Calculate total estimated cost of all tasks.

        Args:
            tasks: List of task dictionaries with optional 'estimated_cost'

        Returns:
            Total cost as float

        Example:
            >>> tasks = [
            ...     {"task_id": "t0", "estimated_cost": 0.05},
            ...     {"task_id": "t1", "estimated_cost": 0.03}
            ... ]
            >>> cost = TaskGraphBuilder.calculate_total_cost(tasks)
            >>> cost
            0.08
        """
        total = 0.0
        for task in tasks:
            cost = task.get("estimated_cost", 0.0)
            if isinstance(cost, (int, float)):
                total += cost
        return round(total, 4)

    @staticmethod
    def calculate_total_duration(tasks: list[dict]) -> float:
        """Calculate total estimated duration of all tasks.

        For sequential tasks, this is the sum of all durations.
        For parallel tasks, use topological sort to get actual duration.

        Args:
            tasks: List of task dictionaries with optional 'estimated_duration'

        Returns:
            Total duration in seconds

        Example:
            >>> tasks = [
            ...     {"task_id": "t0", "estimated_duration": 10.0},
            ...     {"task_id": "t1", "estimated_duration": 20.0}
            ... ]
            >>> duration = TaskGraphBuilder.calculate_total_duration(tasks)
            >>> duration
            30.0
        """
        total = 0.0
        for task in tasks:
            duration = task.get("estimated_duration", 0.0)
            if isinstance(duration, (int, float)):
                total += duration
        return round(total, 1)

    @staticmethod
    def get_task_by_id(
        tasks: list[dict],
        task_id: str
    ) -> Optional[dict]:
        """Get task from list by task_id.

        Args:
            tasks: List of task dictionaries
            task_id: ID to search for

        Returns:
            Task dictionary or None if not found
        """
        for task in tasks:
            if task.get("task_id") == task_id:
                return task
        return None

    @staticmethod
    def get_dependencies_for_task(
        task_id: str,
        dependencies: list[dict],
        incoming: bool = True
    ) -> list[str]:
        """Get tasks that this task depends on (or that depend on it).

        Args:
            task_id: Task ID to query
            dependencies: List of dependency dicts
            incoming: If True, return tasks this task depends on.
                     If False, return tasks that depend on this task.

        Returns:
            List of task IDs

        Example:
            >>> deps = [
            ...     {"from": "t0", "to": "t1"},
            ...     {"from": "t0", "to": "t2"}
            ... ]
            >>> TaskGraphBuilder.get_dependencies_for_task("t0", deps, False)
            ["t1", "t2"]
            >>> TaskGraphBuilder.get_dependencies_for_task("t1", deps, True)
            ["t0"]
        """
        result = []
        for dep in dependencies:
            if incoming and dep["to"] == task_id:
                result.append(dep["from"])
            elif not incoming and dep["from"] == task_id:
                result.append(dep["to"])
        return result
