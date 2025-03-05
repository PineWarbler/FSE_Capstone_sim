# -*- coding: utf-8 -*-
"""
Created on Sat Nov  9 20:08:55 2024

@author: REYNOLDSPG21
"""

import heapq
from datetime import datetime
from typing import Union
import time
from PacketBuilder import dataEntry
import copy

# this class is designed to run on the master laptop in a separate thread that sends out interpolated
# packets at the right times
# the timestamp of any entry can be in the future, and this queue will send out those elements
# at the right times
class CommandQueue:
    ''' a priority queue that stores dataEntry objects ranked by date due (soonest to furthest)
    '''
    def __init__(self):
        self.heap = [] # yes, I know it's a list...
        
    def put(self, entry: dataEntry):
        ''' place a dataEntry object onto the heap. Its timestamp determines
        its insertion point in the heap.  A large timestamp (future) will be placed after a 
        smaller timestamp (past)
        This function assumes that the `time` field in the dataEntry is a float (POSIX) or a datetime object
        '''
        time = entry.time
        if isinstance(time, datetime):
            time = time.timestamp() # convert to numerical value for insertion
        heapq.heappush(self.heap, entry) # note that the dataEntry class has __lt__ defined as comparing the `time` elements
        # first element in tuple is priority ranking, second element
        # is object to store
        
    def put_all(self, entries: list[dataEntry]) -> None:
        for d in entries:
            self.put(d)
    
    # def get_num_due(self) -> int:
    #     ''' returns the number of elements that are (over)due. Useful to call before `pop_all_due` in a multi-threaded
    #     context where a mutex lock is required
    #     '''
    #     if len(self.heap) == 0:
    #         return 0
        
    #     refTime = time.time() 
    #     n = 0
    #     for i in range(0, len(self.heap)):
    #         if self.heap[i][0] <= refTime:
    #             n += 1
    #         else:
    #             break
            
    #     return n
                
    def pop_due(self) -> Union[dataEntry, None]:
        ''' checks to see if the next entry in the heap is (over)due.  If so, pop and return that entry object.
        Otherwise, return None.'''
        if len(self.heap) == 0:
            return None
        
        refTime = time.time()
        if self.heap[0].time <= refTime: # remember that first element in tuple is timestamp, second is object
            # if the timestamp on the heap should have been completed earlier
            # return it immediately
            return heapq.heappop(self.heap)
        return None
    
    def pop_all_due(self) -> list[dataEntry]:
        ''' pop all items that are (over)due. May return an empty list if none are (over)due '''
        l = []
        currEl = self.pop_due()
        while currEl is not None:
            l.append(currEl) # keep popping until we reach elements scheduled in the future
            currEl = self.pop_due()
        return l
    
    def clear_all(self) -> None:
        ''' clears the heap without returning any of the popped values'''
        self.heap.clear()


    def pop_all(self) -> list[dataEntry]:
        ''' 
        pops all items in the heap, regardless of their timestamp priority, sorted newest to oldest.
        '''
        if len(self.heap) == 0:
            return []
        beforeRemoveAll = copy.deepcopy(self.heap)
        
        self.heap.clear() # remove all items from heap
        
        reversedHeap = beforeRemoveAll[::-1]
        return [h for h in reversedHeap] # return only the object, not the timestamp

    def pop_all_with_gpio_str(self, gpio_str:str) -> int:
        # finds all heap entries having the given gpio_str, and deletes them from the heap
        # returns the number popped
        if len(self.heap) == 0:
            return 0
        indicesToRemove = []
        for i in range(len(self.heap)):
            if self.heap[i].gpio_str == gpio_str:
                indicesToRemove.append(i)
        # now iterate from larger indices to smaller indices, removing values
        for i in sorted(indicesToRemove, reverse=True):
            del self.heap[i]
        
        heapq.heapify(self.heap)
        return len(indicesToRemove)
    
    def _heapsort(self, iterable):
        # this code from https://docs.python.org/3/library/heapq.html
        h = []
        for value in iterable:
            heapq.heappush(h, value)
        return [heapq.heappop(h) for i in range(len(h))]
            
    def __str__(self) -> str:
        sortedH = self._heapsort(self.heap)
        return ", ".join([str(e) for e in sortedH]) # each heap element is a tuple of timestamp and element
    
    def __len__(self) -> int:
        return len(self.heap)
        
if __name__ == "__main__":
    d1 = dataEntry(chType = "ao", gpio_str = "GPIO26", val = 18.50, time = time.time()+5)
    d2 = dataEntry(chType = "ai", gpio_str = "GPIO23", val = 0.00, time = time.time()+10)
    d3 = dataEntry(chType = "di", gpio_str = "GPIO24", val = int(1), time = time.time()-10)
    
    q = CommandQueue()
    q.put_all([d1, d2, d3])
    while len(q) > 0:
        todo = q.pop_all_due() # should only return the "ch3" entry
        if len(todo) != 0:
            todo_as_str = [str(t) for t in todo]
            print(f"todo is {todo_as_str}")
    