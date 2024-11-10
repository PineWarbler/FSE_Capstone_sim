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

class CommandQueue:
    ''' a priority queue that stores dataEntry objects ranked by date due (soonest to furthest)
    '''
    def __init__(self):
        self.heap = [] # yes, I know it's a list...
        
    def put(self, entry: dataEntry):
        ''' place a dataEntry object onto the heap. It's timestamp determines
        its insertion point in the heap.  A large timestamp will be placed after a 
        smaller timestamp
        This function assumes that the `time` field in the dataEntry is a float (POSIX) or a datetime object
        '''
        time = entry.time
        if isinstance(time, datetime):
            time = time.timestamp() # convert to numerical value for insertion
        heapq.heappush(self.heap, (float(time), entry)) # first element in tuple is priority ranking, second element
        # is object to store
        
    def put_all(self, entries: list[dataEntry]) -> None:
        for d in entries:
            self.put(d)
                
    def pop_due(self) -> Union[dataEntry, None]:
        ''' checks to see if the next entry in the heap is (over)due.  If so, pop and return that entry object.
        Otherwise, return None.'''
        if len(self.heap) == 0:
            return None
        
        if self.heap[0][0] <= time.time(): # remember that first element in tuple is timestamp, second is object
            # if the timestamp on the heap should have been completed earlier
            # return it immediately
            return heapq.heappop(self.heap)[1]
        return None
    
    def pop_all_due(self) -> list[dataEntry]:
        ''' pop all items that are (over)due. May return an empty list if none are (over)due '''
        l = []
        currEl = self.pop_due()
        while currEl is not None:
            l.append(currEl) # keep popping until we reach elements scheduled in the future
            currEl = self.pop_due()
        return l

            
    def __str__(self) -> str:
        return ", ".join([str(ts) + "," + str(e) for ts, e in self.heap]) # each heap element is a tuple of timestamp and element
    
    def __len__(self) -> int:
        return len(self.heap)
        
if __name__ == "__main__":
    d1 = dataEntry("ao", "ch1", 0.901, time=time.time()+20)
    d2 = dataEntry("do", "ch2", 0.501, time=time.time()+200)
    d3 = dataEntry("ai", "ch3", 0.301, time=time.time()-10)
    
    q = CommandQueue()
    q.put_all([d1, d2, d3])
    todo = q.pop_all_due() # should only return the "ch3" entry
    todo_as_str = [str(t) for t in todo]
    print(f"todo is {todo_as_str}")
    