#!/bin/bash

# Copyright 2020 Cortex Labs, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import threading as td


# TODO might have to implement a writer-preference RW lock.


class ReadWriteLock:
    """
    Locking object allowing for write once, read many operations.

    The lock cannot be acquired multiple times in a single thread without paired release calls.

    Can set different priority policies: "r" for read-preferring RW lock allowing for maximum concurrency
    or can be set to "w" for write-preferring RW lock to prevent from starving the writer.
    """

    def __init__(self, prefer: str):
        """
        "r" for read-preferring RW lock.
        
        "w" for write-preferring RW lock.
        """
        self._prefer = prefer
        self._write_preferred = td.Event()
        self._write_preferred.set()
        self._read_allowed = td.Condition(td.RLock())
        self._readers = []
        self._writers = []

    def acquire(self, mode: str) -> bool:
        """
        Acquire a lock.

        Args:
            mode: "r" for read lock, "w" for write lock.

        Returns:
            Whether the mode was valid or not.
        """
        if mode == "r":
            # wait until "w" has been released
            if self._prefer == "w":
                self._write_preferred.wait()

            # finish acquiring once all writers have released
            self._read_allowed.acquire()
            if self._prefer == "r":
                while len(self._writers) > 0:
                    self._read_allowed.wait()
            self._readers.append(td.get_ident())
            self._read_allowed.release()

        elif mode == "w":
            # stop "r" acquirers from acquiring
            if self._prefer == "w":
                self._write_preferred.clear()

            # acquire once all readers have released
            self._read_allowed.acquire()
            while len(self._readers) > 0:
                self._read_allowed.wait()
            self._writers.append(td.get_ident())
        else:
            return False

        return True

    def release(self, mode: str) -> bool:
        """
        Releases a lock.

        Args:
            mode: "r" for read lock, "w" for write lock.

        Returns:
            Whether the mode was valid or not.
        """
        if mode == "r":
            # release and let writers acquire
            self._read_allowed.acquire()
            if not len(self._readers) - 1:
                self._read_allowed.notifyAll()
            self._readers.remove(td.get_ident())
            self._read_allowed.release()

        elif mode == "w":
            # release and let readers acquire
            self._writers.remove(td.get_ident())
            if self._prefer == "r":
                self._read_allowed.notifyAll()
            self._read_allowed.release()

            # let "r" acquirers acquire again
            if self._prefer == "w":
                self._write_preferred.set()
        else:
            return False

        return True


class ReadLock:
    """
    To be used as:

    ```python
    rw_lock = ReadWriteLock()
    with ReadLock(rw_lock):
        # code
    ```
    """

    def __init__(self, lock: ReadWriteLock):
        self._lock = lock

    def __enter__(self):
        self._lock.acquire("r")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self_lock.release("r")
        return False


class WriteLock:
    """
    To be used as:

    ```python
    rw_lock = ReadWriteLock()
    with WriteLock(rw_lock):
        # code
    ```
    """

    def __init__(self, lock: ReadWriteLock):
        self._lock = lock

    def __enter__(self):
        self._lock.acquire("w")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self_lock.release("w")
        return False