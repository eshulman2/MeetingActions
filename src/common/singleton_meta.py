"""Singleton metaclass for common usage"""

import threading


class SingletonMeta(type):
    """Thread-safe metaclass for implementing singleton pattern

    Uses double-checked locking pattern for thread safety while
    maintaining performance for the common case (instance already exists).
    """

    _instances: dict[type, object] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # Fast path: if instance already exists, return immediately (no lock needed)
        if cls in cls._instances:
            return cls._instances[cls]

        # Slow path: acquire lock for instance creation
        with cls._lock:
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
        with mcs._lock:
            if cls in mcs._instances:
                del mcs._instances[cls]
