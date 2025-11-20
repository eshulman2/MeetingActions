"""Singleton metaclass for common usage"""

import threading


class SingletonMeta(type):
    """Thread-safe metaclass for implementing singleton pattern

    Uses double-checked locking pattern for thread safety while
    maintaining performance for the common case (instance already exists).
    Each singleton class gets its own lock to prevent deadlocks when
    one singleton's __init__ creates another singleton.
    """

    _instances: dict[type, object] = {}
    _locks: dict[type, threading.Lock] = {}
    _locks_lock: threading.Lock = threading.Lock()  # Lock for _locks dict access

    def __call__(cls, *args, **kwargs):
        # Fast path: if instance already exists, return immediately (no lock needed)
        if cls in cls._instances:
            return cls._instances[cls]

        # Get or create a lock for this specific class
        if cls not in cls._locks:
            with cls._locks_lock:
                if cls not in cls._locks:
                    cls._locks[cls] = threading.Lock()

        # Slow path: acquire lock for instance creation (per-class lock)
        with cls._locks[cls]:
            # Double-check: another thread might have created it while we waited
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]

    @classmethod
    def reset_instance(mcs, cls):
        """Reset a specific singleton instance for testing purposes.

        Args:
            cls: The class whose singleton instance should be reset

        Warning:
            This method is intended for testing only. Do not use in production code.
        """
        # Use the per-class lock if it exists
        if cls in mcs._locks:
            with mcs._locks[cls]:
                if cls in mcs._instances:
                    del mcs._instances[cls]
        else:
            # If no lock exists yet, use the locks_lock to safely access _instances
            with mcs._locks_lock:
                if cls in mcs._instances:
                    del mcs._instances[cls]
