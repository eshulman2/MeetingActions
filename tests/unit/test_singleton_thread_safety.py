"""Tests for singleton thread safety."""

import threading

from src.shared.common.singleton_meta import SingletonMeta


class TestSingleton(metaclass=SingletonMeta):
    """Test class using singleton pattern."""

    def __init__(self):
        """Initialize with a unique identifier."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.id = id(self)


def test_singleton_thread_safety():
    """Test that singleton is thread-safe under concurrent access."""
    instances = []
    num_threads = 100

    def create_instance():
        """Create an instance in a thread."""
        instance = TestSingleton()
        instances.append(instance)

    # Create multiple threads that all try to create instances simultaneously
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=create_instance)
        threads.append(thread)

    # Start all threads at once
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify all instances are the same object
    assert len(instances) == num_threads
    first_instance = instances[0]
    for instance in instances:
        assert instance is first_instance, "All instances should be the same object"


def test_singleton_reset_for_testing():
    """Test that reset_for_testing works correctly."""
    # Create first instance
    instance1 = TestSingleton()
    id1 = id(instance1)

    # Reset singleton
    SingletonMeta.reset_instance(TestSingleton)

    # Create new instance
    instance2 = TestSingleton()
    id2 = id(instance2)

    # Should be different instances
    assert instance1 is not instance2
    assert id1 != id2


def test_singleton_double_checked_locking():
    """Test the double-checked locking pattern works correctly."""
    # Reset first
    SingletonMeta.reset_instance(TestSingleton)

    instances_from_threads = []
    barrier = threading.Barrier(50)  # Synchronize 50 threads

    def create_with_barrier():
        """Create instance after all threads are ready."""
        barrier.wait()  # Wait for all threads to reach this point
        instance = TestSingleton()
        instances_from_threads.append(instance)

    threads = []
    for _ in range(50):
        thread = threading.Thread(target=create_with_barrier)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # All instances should be identical
    assert len(set(id(inst) for inst in instances_from_threads)) == 1
