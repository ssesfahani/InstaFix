import asyncio
from typing import Any, Callable, Coroutine, Dict, Generic, TypeVar

# Define generic type variables for Key and Return types
KT = TypeVar("KT")
RT = TypeVar("RT")


class Singleflight(Generic[KT, RT]):
    """
    Implements the singleflight pattern for async functions.

    Ensures that for a given key, an expensive async function `fn` is
    called only once, even if `do` is called multiple times concurrently
    with the same key. Concurrent callers for the same key will wait for
    the single execution to complete and share its result or exception.
    """

    def __init__(self):
        # Stores the ongoing asyncio.Task for each key
        self._calls: Dict[KT, asyncio.Task[RT]] = {}
        # Lock to protect access to the _calls dictionary
        self._lock = asyncio.Lock()

    async def do(
        self,
        key: KT,
        fn: Callable[..., Coroutine[Any, Any, RT]],
        *args: Any,
        **kwargs: Any,
    ) -> RT:
        """
        Executes the async function `fn` for the given `key`.

        If another call with the same `key` is already in progress, this
        call will wait for the ongoing call to complete and return its
        result or raise its exception.

        If no call is in progress for `key`, `fn(*args, **kwargs)` will be
        executed. Its result or exception will be returned to this caller
        and any other concurrent callers for the same `key`.

        Args:
            key: The key identifying the operation.
            fn: The async function to execute.
            *args: Positional arguments for `fn`.
            **kwargs: Keyword arguments for `fn`.

        Returns:
            The result of `fn(*args, **kwargs)`.

        Raises:
            The exception raised by `fn(*args, **kwargs)`.
        """
        task: asyncio.Task[RT] | None = None
        is_owner = False

        async with self._lock:
            if key in self._calls:
                # Another call is already in flight, get its task
                task = self._calls[key]
            else:
                # No call in flight, we are the owner, create a new task
                is_owner = True
                # We wrap the actual function call and the cleanup logic
                # in a new coroutine managed by this task.
                async def task_wrapper():
                    try:
                        return await fn(*args, **kwargs)
                    finally:
                        # --- Cleanup ---
                        # This cleanup runs regardless of whether fn succeeded or failed.
                        # We need the lock again to safely modify the dictionary.
                        async with self._lock:
                            # Delete the entry *only if* it's still our task.
                            # This guards against rare race conditions where the key
                            # might have been quickly forgotten and reused.
                            if self._calls.get(key) is task:
                                del self._calls[key]
                        # --- End Cleanup ---

                # Create the task but don't await it inside the lock
                task = asyncio.create_task(task_wrapper())
                self._calls[key] = task

        # Assert task is not None (should always be assigned in the lock)
        assert task is not None, "Task should have been assigned"

        # Wait for the task to complete and get the result/exception.
        # This happens *outside* the initial lock acquisition, allowing
        # other concurrent calls for *different* keys to proceed.
        # If multiple callers wait on the *same* task, asyncio handles that efficiently.
        try:
            # `await task` will return the result or raise the exception
            return await task
        except asyncio.CancelledError:
            # If the task was cancelled, propagate the cancellation.
            # If we were the owner, the cleanup might have already run or
            # will run shortly. If we were a waiter, the owner handles cleanup.
            print(f"Call for key '{key}' was cancelled.")
            raise
        except Exception as e:
            # If the underlying function `fn` raised an exception,
            # `await task` re-raises it here.
            # The cleanup in task_wrapper ensures the state is cleared.
            # No special handling needed here unless you want to log.
            # print(f"Call for key '{key}' failed: {e}") # Optional logging
            raise  # Re-raise the original exception

    async def forget(self, key: KT) -> bool:
        """
        Removes a key from the internal map. If a call is in progress for this
        key, it is cancelled.

        Returns:
            True if the key was found and removed/cancelled, False otherwise.
        """
        task_to_cancel: asyncio.Task[RT] | None = None
        removed = False
        async with self._lock:
            if key in self._calls:
                task_to_cancel = self._calls.pop(key)
                removed = True

        if task_to_cancel:
            # Cancel the task outside the lock
            task_to_cancel.cancel()
            try:
                # Give the task a chance to handle cancellation and cleanup
                await asyncio.wait_for(task_to_cancel, timeout=1.0)
            except asyncio.CancelledError:
                # Expected outcome
                pass
            except asyncio.TimeoutError:
                print(f"Warning: Timeout waiting for cancelled task '{key}' to finish.")
            except Exception:
                # Ignore other exceptions during forced cleanup
                pass
        return removed
